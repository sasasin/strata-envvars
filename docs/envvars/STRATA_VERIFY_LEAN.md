# `STRATA_VERIFY_LEAN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の command graph から、device plan と `STRATA_VERIFY_NO_HOST` が有効なときにホストが応答しない doorbell の publish、plan 用待機・コピー、および空の PCIe expert group launch を省く。値の既定は on だが、この省略が働くのは `record_window` の `lean` 条件がすべて成立するときだけである。コメントは VRAM/mirror group、combine、answers は同じ kernel・同じデータとしている（`engine/sycl/src/core/verify.cpp:1022-1031`）。

## 値と判定

`record_window` 内の関数ローカル `static const bool` 初期化子が `std::getenv` で一度読み、値が未設定か、先頭文字が `'0'` でなければ有効とする。文字列全体の parse、数値検査、trim、大文字小文字変換はしない（`engine/sycl/src/core/verify.cpp:1018,1026`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `record_window` | 有効（`getenv` が null なら `!(v && ...)` は true） | 空文字、`1`、`true`、`false`、`on`、` 0`。いずれも先頭文字が `0` ではない | `0`、`00`、`0anything`。先頭文字が `0` なら後続を問わず無効 |

## 有効になる条件

- 対象は `engine/sycl/src/core/verify.cpp` の SYCL verifier 経路。CUDA/HIP の実装でこの名前を読む箇所は見つからない。
- `STRATA_VERIFY_NO_HOST` が有効で、`device_plan_` が true であること。lean 判定内の `no_host_env` は未設定・空文字・文字列全体が `0` の場合に無効、それ以外で有効（`engine/sycl/src/core/verify.cpp:1027`）。別の `env_on("STRATA_VERIFY_NO_HOST")` 呼び出しは空でなく先頭が `0` でない値を有効とする（同 `:151-154,978`）。`device_plan_` は all-resident でなく、`always_publish_` でもなく、かつ `STRATA_VERIFY_DEVICE_PLAN` が設定され `atoi(value) != 0` の場合に true になる（同 `:897-925,1031`）。`atoi` は整数として読める先頭部分を使うため、例として `1junk` は非 0、`0junk` は 0 となる。
- batch window（`batch_rec_`）、stepped の hook（`step_hook_` / `step_hook2_`）、remote expert optimization、`always_publish_`、または `STRATA_VERIFY_STEPPED` が有効な場合は lean にならない（`engine/sycl/src/core/verify.cpp:1031`）。stepped mode は `g_stepped` にプロセス初期化時 `env_on` の結果を保持する（同 `:191-194`）。batch capture は `record_window` 呼び出し中に `batch_rec_` を true にする（同 `:3329-3343`）。
- `all_resident_` の場合、device plan は `!all_resident_` の条件で無効となるため、この変数による省略は適用されない（`engine/sycl/src/core/verify.cpp:897-925`）。
- この判定に関する別の CLI 引数、モデル状態、server mode の分岐は確認できない。CLI の batch や stepped 等が上記の内部状態を作る場合は lean が無効になる。

## 実行時の詳細

`STRATA_VERIFY_LEAN` の読み取りは `record_window` が初めて実行されたときの関数ローカル static 初期化で、その後の window では cache 値を使う。プロセス中に環境を書き換えても反映されない（`engine/sycl/src/core/verify.cpp:1018,1026`）。

lean が true のとき、各 layer の router 結果から device plan を作り、通常の `doorbell_publish_res` を省略する（`engine/sycl/src/core/verify.cpp:1617-1636`）。device plan 経路の flag A/B/M 待ち、plan copy、PCIe group kernel も省かれる。CPU/mirror miss rows は device plan の `skip_` 状態を使った `copy_or_zero_from_mapped` に進み、その後 combine する（同 `:1760-1801`）。lean でない経路では通常の doorbell、必要な待ちやコピーを行う。

## ログと測定値

この変数専用の有効・無効ログはない。通常の verifier 初期化では `strata verify: window up to ...` を stderr に出す（`engine/sycl/src/core/verify.cpp:995-998`）。graph launch の失敗は `verify: launch: ...` をエラー文字列にする（同 `:2603-2608`）。ソースコメントは削減量を「約9 nodes」「layer-window あたり約1.4 ms」と記すが、当該コメントには機種・OS・測定条件の説明がないため、一般的な性能値としては扱えない（同 `:1022-1025`）。

## 根拠

- 環境変数の唯一の実読み取り、値規則、static cache、および lean 条件: `engine/sycl/src/core/verify.cpp:1018-1031`。
- device plan と all-resident 条件: `engine/sycl/src/core/verify.cpp:897-925`。
- lean 時に省略される処理と後続の行コピー・combine: `engine/sycl/src/core/verify.cpp:1617-1636,1760-1801`。
- `STRATA_VERIFY_NO_HOST` を解釈する `env_on` helper: `engine/sycl/src/core/verify.cpp:151-154`。
- batch capture が `batch_rec_` を立てる箇所: `engine/sycl/src/core/verify.cpp:3329-3343`。
- docs との照合: `docs/INTEL.md:457` は既定 on と `=0` で off の概要を記す。細かな条件は実装に基づき本書で補足した。
