# `DS4_VISION_FORCE_MPP_FAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 の Metal 画像 vision tower が Metal 4 tensor-op GEMM（MPP）を使うか選ぶ際、MPP の採用判定を強制的に不合格にします。通常の非 MPP GEMM に切り替えるためのテスト用フックです。環境変数を設定しても、画像処理を失敗させたり、アプリケーション全体を終了させたりする処理ではありません。

この変数を読むのは `metal/src/engine/ds4_vision_metal.cpp` の `choose_mpp()` のみです。同ファイルのコメントもテスト用途としています（同ファイル:82-85）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | この変数による不合格指定なし。後続の Metal 4 対応確認、MPP shader のコンパイル、plain kernel との自己検査に進む |
| 空文字を含む任意の設定値 | 不合格指定あり。MPP shader のコンパイルと自己検査をスキップし、plain kernel を選ぶ |

`std::getenv(...) != nullptr` による設定有無だけの判定で、文字列の内容、数値変換、空白、大文字小文字は調べません。したがって `=0` や空文字でも指定は有効です（`metal/src/engine/ds4_vision_metal.cpp:196-198`）。

## 有効になる条件

- この読み取り箇所は Metal vision tower の実装にあります。Metal CMake 構成は `src/engine/*.cpp` をカーネルライブラリに含め（`metal/CMakeLists.txt:110-127`）、DeepSeek-V4.1 用に vision tower のソースを組み込みます（`metal/CMakeLists.txt:132-146`）。CUDA/HIP 側の `ds4_vision.cu` には、この環境変数の読み取りはありません。
- 画像 tower の encode が実行されると `encode()` が呼ばれ、その中で MPP の選択が初回に評価されます。モデルに vision tower がない、または vision が無効なら画像 encode に進まず、この判定も行われません（`src/dsv41/ds4_model.cu:7756-7763`、`src/dsv41/ds4_vision.cu:551-570`）。
- `DS4_VISION_NO_MPP` または `DS4_VISION_REF_GEMM` が設定されていれば、先にそちらを理由として plain kernel を選び、この変数の分岐には到達しません。また、Metal 4 非対応の判定もこの変数より先です。その場合も plain kernel ですが、ログ理由はこの変数名になりません（`metal/src/engine/ds4_vision_metal.cpp:189-198`）。
- これらの先行条件に該当しない場合、未設定なら MPP shader のコンパイルと自己検査を試み、コンパイルまたは検査が失敗した場合も plain kernel へフォールバックします（同ファイル:199-212）。

## 実行時の詳細

Metal vision tower の `encode()` は通常の vision shader をコンパイルした後、関数内の `static const MppChoice` 初期化で `choose_mpp()` を一度だけ呼びます。初回の画像 encode 時に環境を読み、その結果をプロセス内で再利用するため、初回判定後に環境を変更しても再判定されません（`metal/src/engine/ds4_vision_metal.cpp:217-228`）。通常 shader のコンパイルに失敗した場合は、その前に `vision: compiling ds4_vision.metal failed` を返し、MPP 選択には進みません（同ファイル:217-226）。

この変数が設定され、先行条件に遮られず分岐に到達すると `why` が `DS4_VISION_FORCE_MPP_FAIL (test)` になります。選択結果 `use=false` により MPP pipeline は取得されず、条件に合う GEMM も含めて plain GEMM が使われます（同ファイル:196-212, 227-248, 261-276）。stderr には `ds4: vision tower GEMM: plain kernel (DS4_VISION_FORCE_MPP_FAIL (test))` が出ます（同ファイル:208-212）。この選択は通常の vision encode の成功・失敗とは別で、encode はその後の処理を続けます（同ファイル:250-354）。

## 根拠

- `metal/src/engine/ds4_vision_metal.cpp:82-85,189-212` — MPP 選択条件、優先順位、テスト用理由文字列、選択ログ。
- `metal/src/engine/ds4_vision_metal.cpp:217-248,261-276` — 初回選択の static cache、選択結果による pipeline と GEMM の分岐。
- `metal/CMakeLists.txt:110-146` — Metal engine source の組み込みと DeepSeek-V4.1 vision source の Metal 構成。
- `src/dsv41/ds4_vision.cu:551-574` — Metal build の vision encode 呼び出し。
- `src/dsv41/ds4_model.cu:7756-7763` — vision tower がない／無効な場合の画像 encode 経路。
