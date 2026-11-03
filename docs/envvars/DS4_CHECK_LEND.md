# `DS4_CHECK_LEND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

借用していた expert slot を GPU に戻す際、ファイルから読み込んで GPU にコピーした expert の内容を、GPU から host に読み戻して照合する診断用スイッチです。expert slot を貸し出す機能自体は有効化せず、照合結果によって通常の処理成否も変えません。

この処理は DeepSeek-V4.1 用の `strata-dsv41` 経路にあります。CMake では `STRATA_BUILD_DSV41` が既定 OFF で、HIP gfx906 以外のビルドで有効にした場合に同実行ファイルへ `src/dsv41/ds4_model.cu` が含まれます（`CMakeLists.txt:931-945`）。

## 値と判定

値の内容は parse されず、`std::getenv("DS4_CHECK_LEND") != nullptr` で設定有無だけを判定します。したがって、空文字を含む任意の値で照合が有効になります。未設定なら無効です。CLI 引数や別の環境変数による上書き・優先順位はありません。

判定結果は関数内の `static const bool` に保存されます。`borrow_end()` が最初に呼ばれた時点で `jobs` が空なら関数は先に return し、まだ読み取りません。最初に `jobs` が空でない呼び出しで判定した後はプロセス内で固定され、環境を変更しても再評価されません（`src/dsv41/ds4_model.cu:12691-12728`）。

## 有効になる条件

`DS4_CHECK_LEND` は貸し出し経路とは独立です。照合が実行されるには、まず `borrow_end()` による返却処理が走り、返却対象の expert がある必要があります。

- prompt の chunk 処理では、`file_experts`、`one_gpu_or("DS4_BORROW")`、`DS4_FLOW` が未設定または `atoi` の結果が非 0 であることを条件に借用を構成します。さらに該当 device の layer が単独配置の MXFP4 expert で、slot stride が正である場合に `Chunk::borrow` が立ちます。`DS4_BORROW` が未設定なら CUDA/HIP は単一 GPU の場合に有効、Metal は既定で無効です（`src/dsv41/ds4_model.cu:1990-2007,4043-4047,4109-4123`）。prompt 処理は `borrow_begin()` 後に RAII cleanup と明示呼び出しの両方から返却します（`src/dsv41/ds4_model.cu:12952-12957,13043-13060`）。
- vision tower では、lazy tower の場合だけ lender を登録します。画像 encode 時に tower が自身の device allocation を確保できないと lender が呼ばれ、借用 room を返却した後に `borrow_end()` が呼ばれます（`src/dsv41/ds4_model.cu:7732-7737,12660-12686`; `src/dsv41/ds4_vision.cuh:40-42,52-59`）。
- 借用 room の返却対象が空なら `borrow_end()` は照合判定前に終了します。各 expert についても、ファイル読み込みと host-to-device copy が成功した場合だけ照合します（`src/dsv41/ds4_model.cu:12703-12709,12740-12748`）。

## 実行時の詳細

`borrow_end()` は返却対象 expert をファイル位置順に並べ、最大 8 個の staging buffer でファイルから読み込み、借用されていた VRAM slot へコピーします。変数が有効なら、成功した各コピーを `cudaMemcpyDeviceToHost` で読み戻し、読み込み元 staging buffer と `memcmp` します。読み戻しコピーが失敗するか内容が異なる場合は差分カウンタを増やします（`src/dsv41/ds4_model.cu:12710-12727,12730-12753`）。

照合の不一致は expert を CPU lane に退避させず、処理を失敗扱いにもせず、戻り値にも反映しません。通常の返却コピーが失敗した場合の `bad` 判定・CPU lane への退避は別処理です（`src/dsv41/ds4_model.cu:12740-12753,12756-12769`）。

照合が有効なら `verbose` の設定によらず stderr に返却ログが出ます。照合差分がなければ末尾は `; each matches the model file`、1 件以上なら `; MISMATCH` です。未設定で、かつ他のログ条件（`verbose` または返却失敗）がなければ、この返却ログは出ません（`src/dsv41/ds4_model.cu:12772-12776`）。

## 根拠

- 唯一の完全一致参照と設定有無判定: `src/dsv41/ds4_model.cu:12727`。リポジトリ全体の完全一致検索で他の参照はありません。
- 借用 room の prompt / vision 経路: `src/dsv41/ds4_model.cu:12621-12686,12952-12957,13055`; `src/dsv41/ds4_vision.cuh:40-59`。
- expert の読み戻し照合とログ: `src/dsv41/ds4_model.cu:12740-12753,12756-12776`。
- ビルド対象と既定値: `CMakeLists.txt:931-945`。
