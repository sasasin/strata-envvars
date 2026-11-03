# `VISION_HIP_DEFS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`packaging/build_hip_linux.sh` で Linux AMD HIP 用エンジンパッケージを作るとき、GPU 画像 reader（`strata-vision-hip`）の CMake configure に追加定義を渡します。Strata の通常実行時に読む設定ではなく、パッケージビルド用 shell スクリプトの入力です。スクリプトのコメントにある例は `VISION_HIP_DEFS="-DGGML_CUDA_FA=OFF"` です（`packaging/build_hip_linux.sh:2-18,84-90`）。

## 値と判定

値を boolean や数値として解釈する処理、既定の CMake 定義、値域検証はありません。行 86 の未引用展開 `${VISION_HIP_DEFS:-}` は、変数が未設定または空文字なら何も追加しません。空でなければ shell の単語分割と pathname 展開を経た引数列が CMake に渡ります。そのため、空白区切りで複数の `-D...` 引数を指定できます。引用符を含む値も shell コードとして再解釈されるわけではなく、展開後の単語分割規則に従います（`packaging/build_hip_linux.sh:22,84-87`）。

| 状態 | スクリプトの扱い |
|---|---|
| 未設定 | 追加引数なし |
| 空文字 | 追加引数なし |
| 非空 | 単語分割・pathname 展開後の各単語を CMake の追加引数として渡す |

## 有効になる条件

この値が使われるのは `packaging/build_hip_linux.sh` を実行した場合だけです。GPU reader の configure は `-DSTRATA_VISION_HIP=ON` と `-DSTRATA_VISION_HIP_ARCHS=$ARCHS` を付けた `tools/vision` に対して行われ、追加引数は同じ configure 呼び出しに渡されます。エンジン本体および CPU reader の configure には渡されません。`VISION_ONLY` が設定されていてエンジンのビルドを省略する場合も、GPU reader の configure は実行されます（`packaging/build_hip_linux.sh:60-63,78-90`）。

## 実行時の詳細

シェルは GPU reader 用 CMake configure の実行時に環境値を展開します。値は CMake に渡す追加コマンドライン引数であり、生成されたプログラムへ環境変数として設定・転送される処理はこのスクリプトにはありません。CMake configure の標準出力と標準エラーは `$OUT/cfg-vision-hip.log` に記録されます。configure が失敗すると `chk` が `build.status` に失敗と `ABORT` を記録してスクリプトを終了します（`packaging/build_hip_linux.sh:45-48,84-90`）。

Strata ソース内で確認できるのは追加引数の受け渡しまでです。各 `-D` 定義の受け入れ可否や、その定義が依存する ggml/hip のビルド挙動はこの変数の Strata 側の実装範囲ではないため、ここでは説明しません。索引には候補として載っていますが、通常実行時に Strata が読む環境変数ではなく、HIP GPU reader のビルド引数を渡す packaging 用入力です。

## 根拠

- `packaging/build_hip_linux.sh:18`: 用途と値の例。
- `packaging/build_hip_linux.sh:22,84-90`: 未設定・空値時の展開、CMake への引数受け渡し、ログ・終了経路。
- `packaging/build_hip_linux.sh:60-63,78-90`: engine / CPU reader と GPU reader の configure 対象の違い、および `VISION_ONLY` 時の経路。
- `tools/vision/CMakeLists.txt:19-29,68-70,84-108`: GPU reader 用 HIP 設定と生成 target が `strata-vision-hip` であること。
