# `LLAMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`LLAMA` は実行時設定ではなく、Linux HIP エンジン用パッケージを作る `tools/packaging/build_hip_linux.sh` が読むビルド時の互換 override です。空でなければ `-DSTRATA_GGML_DIR=<値>` としてエンジンの CMake configure に渡し、CMake が ggml のソースルートを vendored tree から指定 checkout に切り替えられるようにします。Strata の起動後に読む箇所はなく、通常の CPU/CUDA/SYCL/Metal ビルドや `strata-vision` の configure にはこの変数を渡しません（`tools/packaging/build_hip_linux.sh:10,24-25,63-80`）。

## 値と判定

シェルで `${LLAMA:-}` により読みます。未設定と空文字はどちらも空文字になり、override の CMake 引数を作りません。空でない値は文字列を parse・正規化せず、配列の 1 引数 `-DSTRATA_GGML_DIR=<値>` として渡します。シェル配列なので値中の空白も引数分割されません（`tools/packaging/build_hip_linux.sh:24-25,63-65`）。

| 条件 | unset | 設定時に CMake へ渡す値 | CMake で override になる値 |
|---|---|---|---|
| `build_hip_linux.sh` がエンジンを configure する場合 | 空として扱い、引数を省略。新規 cache では vendored `engine/third_party/strata-ggml` | 空でない値をそのまま `STRATA_GGML_DIR` に渡す | CMake の `if(STRATA_GGML_DIR)` が真になる値（checkout のルート）。`0`、`OFF` など CMake の false 定数は引数としては渡るが、override にはならず vendored tree が選ばれる（`engine/cmake/strata_ggml.cmake:11-16`） |

このシェル側では有効パスかどうかを検査しません。CMake は真の値を ggml root とし、その下の `ggml` を `add_subdirectory` するため、必要な tree がない場合は configure が失敗します（`engine/cmake/strata_ggml.cmake:12-16,59`）。`LLAMA` には CLI 引数からの直接優先規則はありませんが、同じ configure 呼び出しの後段に `${STRATA_CMAKE_EXTRA:-}` も展開されるため、そこから同じ CMake cache 変数を指定する構成ではコマンドライン上に両方が渡り得ます（`tools/packaging/build_hip_linux.sh:63-65`）。

## 有効になる条件

- Linux HIP 用パッケージスクリプト `tools/packaging/build_hip_linux.sh` を使うこと。スクリプト自体が `VARIANT` と ROCm root `HP` を必須にします（同:22,26）。
- `VISION_ONLY` が空であること。設定されているとエンジン configure/build 部分を丸ごと飛ばし、この値は参照されません（同:60-70）。
- `LLAMA` が空でないことに加え、CMake 条件で真と評価されること。そうでなければ vendored tree が選ばれます（同:24-25; `engine/cmake/strata_ggml.cmake:11-16`）。
- 指定 tree を実際に ggml の subproject として追加するには `STRATA_NATIVE_EXPERTS` が ON で、かつ `STRATA_BUILD_TESTS` が ON または `STRATA_OWN_CPU_QUANT` が OFF である必要があります。`STRATA_NATIVE_EXPERTS` と `STRATA_OWN_CPU_QUANT` の既定値は ON です。スクリプトは `STRATA_BUILD_TESTS=OFF` を渡すため、既定構成では root を解決しても ggml subproject を追加しません。`STRATA_CMAKE_EXTRA` などで条件を変えない限り、`LLAMA` override は既定の release engine build に実体として使われません（`engine/CMakeLists.txt:154-162,176-184,641-650`; `tools/packaging/build_hip_linux.sh:63-65`）。

## 実行時の詳細

スクリプト開始時に一度シェル変数へ取り込み、エンジンの CMake configure 呼び出しでだけ引き渡します。Strata 実行ファイルへの設定転送や実行時再読込はありません。`VISION_ONLY` の場合は読み取った値を引数に使う経路がありません（`tools/packaging/build_hip_linux.sh:24-25,60-65,71-80`）。

CMake 側では `STRATA_GGML_DIR` を cache PATH として宣言し、真ならその値、そうでなければ `engine/third_party/strata-ggml` を root に選びます（`engine/cmake/strata_ggml.cmake:11-16`）。スクリプトは `$OUT/b` を configure build directory として使い、既存の build directory を先に消しません。そのため同じ `$OUT/b` の CMake cache に過去の `STRATA_GGML_DIR` が残っている場合、`LLAMA` が未設定でも CMake 側の選択に残る可能性があります。新規 cache では未指定時に vendored root が選ばれます（`tools/packaging/build_hip_linux.sh:29,63-65`; `engine/cmake/strata_ggml.cmake:11-16`）。

## ログと測定値

`LLAMA` 専用の status / 警告はありません。エンジン configure の stdout/stderr は `$OUT/cfg.log` に記録され、終了コードは `build.status` に `engine configured rc=<値>` として記録されます。configure が失敗すると同ファイルに `ABORT engine configured failed (rc=<値>)` を追記してスクリプトが終了コード 1 で止まります（`tools/packaging/build_hip_linux.sh:44-47,63-68`）。値を指定した場合の性能・正確性測定値は Strata ソース資料に見つかりません。

## 根拠

- `tools/packaging/build_hip_linux.sh:10,21-25,60-80` — 変数の宣言・空値判定・CMake 引き渡し・適用範囲。
- `engine/CMakeLists.txt:154-162,183-184,638-650` — build tests と CPU quant の既定値、および ggml configure 条件。
- `engine/cmake/strata_ggml.cmake:7-17,19-60` — ggml root の選択と subproject 追加。
