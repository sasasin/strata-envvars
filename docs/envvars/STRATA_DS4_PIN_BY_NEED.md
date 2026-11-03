# `STRATA_DS4_PIN_BY_NEED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 用の独立実行ファイル `strata-dsv41` で、RAM にコピーした CPU lane の expert を GPU が直接読めるよう登録（pin）する順序を制御します。通常は全コピーを登録し、一つでも失敗すると登録済みの領域を解除して staging 経由へ戻ります。有効にすると、ルーティング profile で使われる頻度をコピー容量で割った値の高い順に登録し、登録失敗または `STRATA_DS4_PIN_GB` の上限で止めます。登録済みコピーは GPU がその場所から読み、残りは pinned staging を通ります。

## 値と判定

主判定はモデル初期化時に `env_f("STRATA_DS4_PIN_BY_NEED", 0.0f)` で読み、`std::atof` の結果が `0.0f` でないかを調べます。文字列全体の検証や値域制限はありません。

| 値 | 通常の判定 | Windows CUDA の単一 GPU 経路 |
|---|---|---|
| unset | 無効 | 有効（既定） |
| 空文字 | `atof("")` が 0 のため無効 | unset と同様に有効 |
| 数値として 0 | 無効 | 無効（空文字ではない明示値） |
| 数値として非 0 | 有効。負数や小数も非 0 なら有効 | 有効 |
| 数値変換できない文字列 | `atof` が 0 を返すため無効 | 無効 |
| 数値の後ろに文字が続く値 | `atof` が変換した数値部分が非 0 なら有効 | 同左 |

たとえば `1tail` は有効、`0tail` と `true` は無効です。`1` だけを許す判定ではありません。Windows CUDA の既定判定は環境変数の先頭が未設定または空文字かを別途見るため、空文字は通常の `atof` 判定と異なります。根拠: `src/dsv41/ds4_model.cu:1352,6058-6066`。

## 有効になる条件

- この実装は CMake の `STRATA_BUILD_DSV41` が有効なときに追加される独立 target `strata-dsv41` 内にあり、この CMake option は既定で OFF です。`STRATA_DS4_PIN_BY_NEED` は通常の `strata` executable にはこの箇所から適用されません（`CMakeLists.txt:931-945`）。
- RAM copy 経路が必要です。`copy_experts()` は `--mmap-experts` が有効（値が 0 より大きい）または候補 expert が空ならコピーを行わず、`zc_pin()` も呼ばれません（`src/dsv41/ds4_model.cu:5834-5843,6044-6045`）。コピー対象がある通常の入口は、GGUF で GPU に載らない expert があり、`--mmap-experts off` 等でコピー方式になった場合です（同 `:5760-5767`）。
- `zc_pin()` は NUMA part 数 `NH` が 1、かつ RAM chunk が存在するときだけ続行します。`DS4_STREAM_ZC` が数値変換で 0 になる値なら無効、PCIe lane が無効、または GGUF 以外でも無効です。統合 GPU が lane device に含まれる場合も無効です（同 `:6176-6186`）。
- ゼロコピー可否は、登録済み host address を device が直接使える場合、またはこの変数が有効で GPU が 1 台の場合に成立します。複数 GPU で host pointer を直接使えない場合は、この変数を有効にしても `zc_pin()` は開始しません（同 `:6071-6084,6176-6186`）。
- Windows CUDA（`_WIN32` かつ `STRATA_USE_HIP` ではないビルド）では、one-GPU 経路が有効で変数が unset または空文字なら既定で有効です。`one_gpu_plan()` が PCIe lane から何も stream しないと判断すると `ln_one` を解除するので、この既定有効条件も失われます（同 `:6061-6066,6104-6129,6140-6158`）。HIP ではこの Windows 既定値分岐はコンパイルされません。明示値の通常判定自体にはこの Windows 専用分岐がありません。
- `STRATA_DS4_PIN_GB` が正なら、その容量を超える次の chunk の前で登録を止めます。0 以下ならこの上限による停止はありません（同 `:6068,6212-6224`）。

## 実行時の詳細

環境変数の数値判定はモデルオブジェクトのメンバー初期化で行われ、結果を `pin_by_need_env` に保持します。Windows CUDA の `pin_by_need()` は unset/empty を単一 GPU 経路の既定値にするため、その判定時には `getenv` を再度呼びます。その他の環境変数は同じオブジェクト初期化時に `pin_cap_gb` として読み取られます。実行中に環境を変えた場合、保持済みの数値判定・上限には反映されません（同 `:6058-6068`）。

`zc_pin()` は profile の各 expert の利用回数を、その expert の入る RAM chunk 容量で割った値が高い順に並べます。通常の pin-by-need 経路では `cudaHostRegister` を一 chunk ずつ試し、登録に失敗した時点で後続の試行を止めます。`STRATA_DS4_PIN_GB` の上限を超える場合も同様に止めます（同 `:6185-6207,6212-6224`）。

`DS4_COPY_PIN` によって先に RAM copy 全体が登録されていた場合はその登録を引き継ぐため、pin-by-need の容量順登録・上限処理は行いません（同 `:6027-6044,6209-6212`）。部分登録後は、device pointer の取得に失敗した chunk を解除し、成功分だけ `zc_slot` に反映します。成功したコピーは `zc_ok()` / `zc_mat()` を通じて device に直接渡され、他の expert は従来どおり staging を使います（同 `:6245-6278,6281-6287,9811-9829,9885-9894`）。

pin-by-need 経路の結果は stderr に `ds4: PCIe lane: pin by need: ...` として、登録できたコピー量・総コピー量・所要時間を出します。登録に失敗してもこの経路ではエラー終了せず、登録できた分を使い、残りは staging 経由にします。pin-by-need 無効時に全コピー登録の一つでも失敗した場合は、成功分を解除して `ds4: PCIe lane: pinning the copied experts failed - streamed ones pass the staging (STRATA_DS4_PIN_BY_NEED=1 pins the ones it can)` を stderr に出して戻ります（同 `:6235-6243,6270-6278`）。

## 根拠

- `src/dsv41/ds4_model.cu:1352` — `env_f` の実装（`getenv` と `atof`）。
- `src/dsv41/ds4_model.cu:6053-6068` — 変数の既定値分岐と pin 上限。
- `src/dsv41/ds4_model.cu:5834-5843,6044-6045` — RAM copy 経路と `zc_pin()` の呼び出し。
- `src/dsv41/ds4_model.cu:6176-6287` — 適用条件、優先順、pin 登録、失敗処理、直接参照用ポインタ。
- `CMakeLists.txt:931-945` — DeepSeek-V4.1 target が独立 executable で、ビルド option が既定 OFF。
