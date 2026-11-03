# `DS4_TEST_PIN_FAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-dsv41` のモデルロード時に、CPU lane の expert 用 host memory の CUDA pin 登録を指定位置で意図的に止める診断用フックです。コメントにも「tests: part N's pin fails」とあります。GPU や OS の実際の pin 上限に達しなくても pinning 失敗時の fallback を通せます。通常の性能設定や pin 量の指定ではありません。参照は `src/dsv41/ds4_model.cu:3630-3643`。

## 値と判定

値は `std::atol` で `long` に変換され、結果を `host_maps` の 0 始まり index と比較します。変換値と各ロード時の結果は次のとおりです (`src/dsv41/ds4_model.cu:3637-3645`)。

| 環境値 | 結果 |
|---|---|
| 未設定 | `fail_at = -1`。通常の `cudaHostRegister` を各 part で試す。 |
| 空文字、数値に変換できない文字列 | `atol` の結果は `0`。最初の part (index 0) を意図的に失敗させる。 |
| 数値 `N` の prefix | `N >= 0` かつ `N < host_maps.size()` なら index `N` の登録前に止める。警告の part 番号は 1 始まりなので `N + 1`。例: `5tail` は index 5 で止まる。 |
| 負数、または map 数以上の数値 | 通常の index と一致せず、意図的な失敗は発生しない。実際の `cudaHostRegister` 失敗は別途あり得る。 |

`atol` は整数の prefix を読むため、先頭空白と符号は受け付け、数字の後ろは検査しません。小数点や空白以外から始まる文字列のように数字 prefix がない場合は 0 になります。全体の parse 成功、errno、範囲エラーの検査や clamp はありません。

## 有効になる条件

- ビルドに CUDA または HIP backend が必要です。`strata-dsv41` 自体は `STRATA_BUILD_DSV41` が ON のときだけ追加され、同 option の既定値は OFF です。`STRATA_HIP_GFX906` build では target が追加されません (`CMakeLists.txt:80-93, 931-945`)。
- モデルロードで最終的な `chunk > 0` の場合にだけ環境値を読みます。chunk は `--prefill-chunk` と prompt path の選択で決まり、`DS4_CHUNK` が設定されると prompt path が有効な場合は CLI / 既定値から得た chunk を上書きします。VRAM の空きなどで後段が `chunk = 0` にすると pin 処理自体がありません (`src/dsv41/ds4_model.cu:2719-2725,2788-2805,5512-5520,3630-3639`)。
- `host_maps` は、file-backed でない expert が VRAM に収まらず `n_host > 0` となる層について確保されます。`--mmap-experts` / 自動配置で `file_experts` 経路になれば、この RAM copy 用 map は作られません。その場合 `host_maps` が空なら loop は実行されず、この変数による失敗は起きません (`src/dsv41/ds4_model.cu:2750-2771,5606-5639,3641-3645`)。
- `DS4_TEST_PIN_FAIL` と CLI option の優先順位は、pin 失敗位置について CLI 指定がなく、この環境変数の `fail_at` と各 index の直接比較だけです。`--prefill-chunk` は処理ブロックに到達する条件に関わり、`DS4_CHUNK` はその chunk 値を上書きし得ます。別の変数による pin-failure index の上書きは確認できません (`src/dsv41/ds4_model.cu:2788-2796,3637-3643`)。

## 実行時の詳細

値は `Model::Impl::load()` 内の `if (chunk > 0)` に入るたびに読み直されます。`static` cache ではありません。通常の `strata-dsv41` 起動では `main` が `m.load(o, err)` を呼んでから serve / 推論経路へ進みます (`src/dsv41/ds4_model.cu:2651-2654,3630-3643`; `src/dsv41/ds4_main.cpp:2621-2629`)。子プロセスへの転送や、ロード後の各 prompt / request での再評価はこの箇所にはありません。

対象 index に達すると、条件式の短絡でその part の `cudaHostRegister` は呼ばれません。直前までに登録した map があればすべて `cudaHostUnregister` し、`host_pinned` を false にします。Strata は stderr に `ds4: WARNING: pinning the CPU lane's experts in RAM failed at part ...` を出し、その後も `load()` を続けます。ここで `err` を設定したり失敗 return したりはせず、コメントと警告文が説明する通り CPU lane の RAM は unpinned のままとなり、prompt 時の転送は driver staging 経由になります。これは Strata が選ぶ fallback の説明であり、driver 内部の動作は対象外です (`src/dsv41/ds4_model.cu:3641-3659`)。`Model::load()` が false を返す別のエラーは `ds4_main.cpp` が `maya-ds4: <error>` として stderr に出し終了コード 1 を返しますが、この環境変数による pin fallback 自体はその終了経路を取りません (`src/dsv41/ds4_main.cpp:2621-2625`)。

## 根拠

- 候補名の全参照: `src/dsv41/ds4_model.cu:3635-3639`。コメントと実読み取りは同じ箇所で、他の直接参照や動的 helper 経由の参照はありません。
- host map の作成条件と格納単位: `src/dsv41/ds4_model.cu:5606-5639`。
- DSV41 target の build option と除外条件: `CMakeLists.txt:931-945`。
- `000_envvers.md` に候補として掲載されています (`docs/envvars/000_envvers.md:423`)。実装はテスト用の失敗注入であることをコードで確認しました。
