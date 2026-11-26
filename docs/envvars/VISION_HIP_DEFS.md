# `VISION_HIP_DEFS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`tools/packaging/build_hip_linux.sh` が、Linux 向け HIP GPU picture reader (`strata-vision-hip`) の CMake 構成時に、追加のコマンドライン引数として展開・転送するビルド用環境変数です。通常のエンジンや CPU reader の CMake 構成には渡されません。スクリプト自身は値を解釈せず、Strata の実行時環境変数として読むコードもありません（`tools/packaging/build_hip_linux.sh:17,63-80`）。

## 値と判定

スクリプトは `${VISION_HIP_DEFS:-}` を引用符なしで展開します。変数が未設定または空文字なら展開結果は空となり、追加引数はありません。空白区切りの各単語は CMake の引数として渡されます。シェルの通常の単語分割と pathname expansion が適用され、スクリプトによる値の parse、boolean 判定、数値変換、検証はありません（`tools/packaging/build_hip_linux.sh:80`）。

| 条件 | unset | 引数として渡される例 | スクリプトが有効性を判定しない例 |
|---|---|---|---|
| `build_hip_linux.sh` の HIP GPU reader 構成 | 追加引数なし | `-DNAME=VALUE`。複数の引数は空白で区切る | 空文字・空白のみは追加引数なし。`0`、`1`、`true`、`false` もスクリプト内では真偽値にならず、その文字列が引数として渡る。CMake が受理するかはこのスクリプトでは検証しない |

引数の引用が必要な値をどのように指定するか、重複する CMake 定義がどう扱われるか、各定義が reader のビルドにどう作用するかは、この変数を処理するスクリプトでは規定されません。CMake に渡す前に値を整形・検査する処理はありません。

## 有効になる条件

- Linux HIP パッケージ作成用の `tools/packaging/build_hip_linux.sh` が、CPU reader 構成を通過して GPU reader の CMake 構成箇所まで実行されること。スクリプトは `-DSTRATA_VISION_HIP=ON`、`-DSTRATA_VISION_HIP_ARCHS=$ARCHS`、`-DSTRATA_PORTABLE=ON` とともにこの値を渡します（`tools/packaging/build_hip_linux.sh:71-81`）。
- `VISION_ONLY` が未設定または空でも GPU reader は構成されます。設定されていればエンジン構成を飛ばしますが、CPU/GPU reader の構成は行い、GPU reader の後に終了します（`tools/packaging/build_hip_linux.sh:60-70,79-85`）。
- この変数を渡すのは GPU reader の構成だけです。エンジンの CMake 呼び出し（`tools/packaging/build_hip_linux.sh:63-65`）および CPU reader の CMake 呼び出し（同:73-75）には渡されません。
- 設定があっても、CMake が引数を受理して構成に成功しなければ後続の GPU reader build には進みません。具体的な `-D` 定義の妥当性や生成されるコードへの効果は、値の内容と CMake 側の処理によるため、この環境変数を展開するコードだけからは特定できません。

## 実行時の詳細

値は `build_hip_linux.sh` の GPU reader 用 `cmake` コマンドが実行される時点で shell 展開されます。スクリプト内に `VISION_HIP_DEFS` 用のキャッシュや再読取りはなく、Strata の engine、server、CLI が起動後に読む処理も見つかりません。展開値は `cmake -S terminal/tools/vision -B "$OUT/bh" ...` に引数として渡され、構成出力は `"$OUT/cfg-vision-hip.log"` にリダイレクトされます（`tools/packaging/build_hip_linux.sh:79-81`）。

CMake が非ゼロで終了すると、スクリプトは `build.status` に `gpu reader configured rc=<終了コード>` と `ABORT gpu reader configured failed (rc=<終了コード>)` を記録して終了コード 1 で停止します。構成に成功した後のビルド失敗は `gpu reader built` / `ABORT gpu reader built failed (rc=<終了コード>)` として同様に停止し、生成物がない場合は `ABORT no strata-vision-hip` を記録して build log の末尾20行を status に追記します（`tools/packaging/build_hip_linux.sh:44-47,79-84`）。スクリプト自身は `VISION_HIP_DEFS` の値や採用された各定義をログに出しません。

## ログと測定値

測定値はありません。CMake の標準出力・標準エラーは `$OUT/cfg-vision-hip.log` に保存されます。スクリプトの status には上記の構成・ビルド失敗理由が記録されますが、変数の値を表示するログはありません（`tools/packaging/build_hip_linux.sh:79-84`）。

## 根拠

- `tools/packaging/build_hip_linux.sh:17` — パッケージスクリプトの入力説明。
- `tools/packaging/build_hip_linux.sh:63-80` — engine、CPU reader、HIP GPU reader の各 CMake 呼び出しと、変数を GPU reader にだけ渡す箇所。
- `tools/packaging/build_hip_linux.sh:44-47,81-84` — status 記録、構成・ビルド失敗時の終了経路。
- `terminal/tools/vision/CMakeLists.txt:25-28,63-69,84-90` — GPU reader 用 CMake option、HIP 構成、出力名の定義。
