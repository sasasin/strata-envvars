# `STRATA_PARTIAL_PIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PARTIAL_PIN` は、RAM に作る expert cache complement の先頭部分を GPU にマップする部分登録経路の opt-in です。プロファイル順で高温の expert が先に並ぶ complement のうち、上限までを CUDA の `cudaHostRegister` で登録し、残りはホスト側の `lock_resident` に渡します。全 complement を通常の pinned allocation にできた場合、この変数による追加登録は行われません。実装は CUDA 系と SYCL 系それぞれの `FileExpertSource::pin_cache_complement` にあります（`engine/src/core/expert_source.cpp:4431-4449,4528-4566`、`engine/sycl/src/core/expert_source.cpp:1938-1956,1957-2018`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoi` に渡し、結果が 0 以外なら有効とします。文字列全体の妥当性検査はありません。未設定と空文字は無効です。`atoi` が読む先頭の数値部分で判定するため、`1`、`+1`、` 1`、`1tail`、`-1` は有効、`0`、`0tail`、`true`、`false`、数値で始まらない文字列は無効です。大文字小文字は判定に影響しません。`atoi` の整数範囲を超える入力はコードで安全に扱われていません（同上の `partial_on` 初期化箇所）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA 系・SYCL 系の部分登録分岐 | `partial_on=false` | `atoi` が 0 以外を返す文字列（例: `1`, `-1`, `1tail`） | `atoi` が 0 を返す文字列（例: 空文字, `0`, `0tail`, `true`） |

## 有効になる条件

- `FileExpertSource::pin_cache_complement` が resident complement を構築し、引数 `pin` が true である必要があります。呼び出し元は `--resident-experts`、正の `--resident-budget-gib`、または resident RAM fallback からこの処理へ進みます。`--ssd-experts` と `--resident-budget-gib 0` は resident copy / pin を無効にします（`engine/src/program/generate.cpp:4220-4257,12077-12080`、`engine/sycl/src/program/generate.cpp:2182-2203,7098-7099`）。
- その時点で expert mapping が開いており、complement が未構築で、GPU expert cache が有効かつ全 slot filled である必要があります。CUDA 系では device synchronize が成功することも前提です。不成立時は関数が false を返し、部分登録の判定には進みません（`engine/src/core/expert_source.cpp:3991-4003`、SYCL: `engine/sycl/src/core/expert_source.cpp:1668-1675`）。
- 既定で有効になる `STRATA_RESIDENT_PIN` とは別のスイッチです。`STRATA_RESIDENT_PIN=0` などで呼び出し側の `pin` が false なら、この変数を有効値にしても部分登録経路には入りません（同上）。
- complement の通常の pinned allocation が失敗し、pageable arena への fallback に進む必要があります。通常の allocation に成功した場合はこの分岐を通りません（`engine/src/core/expert_source.cpp:4374-4397,4398-4432`、`engine/sycl/src/core/expert_source.cpp:1871-1929,1938-1947`）。
- CUDA 系では Linux 上で `STRATA_PIN_GUARD=2`、または実際に動作する `STRATA_NUMA_SPLIT` により RAM を段階的に確保する `paced` 経路が選ばれた場合、変数の値にかかわらず別の登録処理を行います。その経路は `partial_on` 分岐を通らないため、この変数は登録量を切り替えません（`engine/src/core/expert_source.cpp:4328-4367,4450-4528`）。
- 非 paced 経路では `budget_bytes > 0` も必要です。登録サイズは complement のサイズと `STRATA_PARTIAL_PIN_GIB` 上限以下で、2 GiB 刻みで試行し、expert blob の境界に切り下げます。上限変数が未設定・無効値なら 24 GiB、正の数値として読めればその GiB 値です（`engine/src/core/expert_source.cpp:4444-4449,4528-4549`、SYCL: `engine/sycl/src/core/expert_source.cpp:1951-1956,1957-2007`）。
- 値は関数内の `static const bool` として最初に該当分岐へ到達した時に読み込まれ、そのプロセス内では cache されます。起動後に環境を変更しても反映されません。同じ分岐で `STRATA_PARTIAL_PIN_GIB` も static cache されます（上記 `partial_on` / `pin_cap` 初期化箇所）。

## 実行時の詳細

CUDA 系では fallback arena の先頭から、上限と complement サイズの小さい方を開始点として登録を試し、登録失敗時は 2 GiB ずつ小さくします。候補範囲が expert blob の途中で切れる場合は、その blob の開始位置まで縮めます。登録と device alias の取得に成功すると、その範囲を `partial_pin` として記録し、残りの arena を `lock_resident` に渡します（lock の成否は別途 `LockResult` に記録されます）。後続の `pinned()` 判定は部分登録の範囲に収まる expert だけを pinned 扱いし、`device_alias()` はその expert の device pointer を返します（`engine/src/core/expert_source.cpp:4528-4566,5248-5260`）。

SYCL 系にも同名の判定と上限ループがありますが、既存 host memory を登録する CUDA 呼び出しは生成済み実装で no-op に置き換えられています。ループは `arena` を alias として採用できると `partial_pin` を設定し、その後の pinned 判定にも渡します。したがって、このコードから実際の SYCL host memory 登録が行われるとは言えません。SYCL 側の現行挙動は `engine/sycl/src/core/expert_source.cpp:1968-2018,2141-2149,2402-2418` に限って記述しています。

## ログと測定値

CUDA 系の非 paced 分岐は、登録試行の成否にかかわらず完了ログに `%.2f GiB of it registered for the GPU (the hottest)` を note として加えます。部分登録されなかった場合は 0.00 GiB です。最後に `FileExpertSource: ... cache complement ready: resident ... GiB, pinned ... GiB in ... s` が stderr に出ます（`engine/src/core/expert_source.cpp:4555-4558,4733-4738`）。SYCL 系は note に `%.2f GiB of it registered for the GPU (the hottest)` を加え、同様の完了ログを出しますが、上記のとおり登録呼び出し自体は no-op です（`engine/sycl/src/core/expert_source.cpp:2009-2018,2153-2157`）。

ソースコメントには RTX 5070 PC での比較値（24 / 16 GiB 登録時 7.30 / 7.44 tok/s、40 GiB budget の未登録時 7.05–7.74 tok/s）が記載され、「no faster」とされています。ただし、そのコメントだけでは OS、backend、モデル・量子化、測定回数などの条件が揃わないため、一般的な性能値としては扱えません（`engine/src/core/expert_source.cpp:4437-4439`、同内容の SYCL ソースコメント: `engine/sycl/src/core/expert_source.cpp:1944-1946`）。設計資料 `docs/UNSLOTH_Q4.md:234` も opt-in と上限の説明を記載していますが、現在の値判定と実行条件は上記ソースを根拠にしています。

## 根拠

- `engine/src/core/expert_source.cpp:3985-4003,4431-4449,4528-4566,4719-4738,5248-5270` — CUDA 系の呼び出し条件、値読み取り、登録、cache 状態とログ。
- `engine/sycl/src/core/expert_source.cpp:1661-1669,1938-2018,2141-2157,2402-2418` — SYCL 系の値読み取り、no-op 登録経路と後続状態。
- `engine/src/program/generate.cpp:4220-4257,12077-12080`、`engine/sycl/src/program/generate.cpp:2182-2203,7098-7099` — CLI / resident mode からの呼び出しと `pin` 条件。
- `docs/UNSLOTH_Q4.md:228-236` — 設計資料の設定説明（実装挙動の根拠ではない）。
