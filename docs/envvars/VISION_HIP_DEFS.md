# `VISION_HIP_DEFS`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

`tools/packaging/build_hip_linux.sh` が、GPU 画像リーダー (`strata-vision-hip`) 用の CMake configure に追加引数を渡すためのビルド時環境変数です。実行時に Strata 本体や reader がこの名前を読む箇所はなく、モデル処理や実行時動作を直接切り替える変数ではありません。スクリプトのコメントも「GPU reader only」の追加 CMake 定義としています (`tools/packaging/build_hip_linux.sh:17,79-83`)。

## 値と判定

スクリプトは `${VISION_HIP_DEFS:-}` を引用符なしで展開し、値を parse したり許可リストと照合したりしません。bash の通常の word splitting と pathname expansion が行われ、展開後の各語が CMake コマンドの引数になります (`tools/packaging/build_hip_linux.sh:21,80-82`)。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `tools/packaging/build_hip_linux.sh` の GPU reader configure | 引数を追加しない | 例: `'-DNAME=value -DOTHER=value'` は通常、2 個の CMake 引数として渡される | Strata 独自の「無効値」判定はない。空文字、空白だけの値は通常 0 語になり追加引数なし。意図しない glob はファイル名に展開され得る。CMake が受け付けない引数・値は configure を失敗させる |

`0`、`1`、`true`、大文字小文字、数値境界などをこの変数自身について判定する処理はありません。値は一つの文字列として保持されず、空白等で分かれた語列です。引用符を値に含めても shell 展開後に引用構文として再解釈されないため、空白を含む CMake 引数をこの方法で安全に一語として渡す処理はありません (`tools/packaging/build_hip_linux.sh:80-82`)。

## 有効になる条件

- Linux の HIP パッケージビルドで `tools/packaging/build_hip_linux.sh` が GPU reader configure まで到達する必要があります。同スクリプトは `VARIANT` と ROCm の `HP` を要求し、`VISION_ONLY` が空の場合は先に engine build も実行します (`tools/packaging/build_hip_linux.sh:21-29,61-71,79-83`)。
- 対象 configure は `terminal/tools/vision` で、スクリプトが `STRATA_VISION_HIP=ON` と `STRATA_VISION_HIP_ARCHS` を明示し、HIP compiler 定義も渡します。CMake 側は HIP と CUDA の同時有効化をエラーにし、HIP が有効なら HIP language を有効化して reader を `strata-vision-hip` として構成します (`tools/packaging/build_hip_linux.sh:80-83`; `terminal/tools/vision/CMakeLists.txt:26-38,64-70,85-90`)。
- この変数は同じ CMake 呼び出しの明示引数より後、`$sym_cmake` より前に展開されます。したがって追加の CMake 定義を供給できますが、同一キーを重ねた場合の最終値や各定義の妥当性は Strata の shell コードでは検査しません (`tools/packaging/build_hip_linux.sh:79-82`)。
- CPU reader の configure と engine の configure にはこの変数を渡していません (`tools/packaging/build_hip_linux.sh:64-76,79-83`)。

## 実行時の詳細

スクリプト実行時に GPU reader の CMake コマンドを組み立てる段階で一度 shell 展開されます。プロセス起動後に親環境を書き換える方法はなく、生成済みバイナリがこの環境変数を読み直す処理もありません。環境変数自体を子プロセスへ転送するのではなく、展開された語を `cmake` のコマンドライン引数として渡します (`tools/packaging/build_hip_linux.sh:80-83`; `terminal/tools/vision/CMakeLists.txt:26-29,85-90`)。

configure の標準出力・標準エラーは `$OUT/cfg-vision-hip.log` にリダイレクトされます。configure が非 0 で終わると `chk` が build status に失敗と abort を記録してスクリプトを exit 1 で終了します。後続の build が成功しても所定の `strata-vision-hip` 実行ファイルがなければ abort します (`tools/packaging/build_hip_linux.sh:46-47,80-85`)。

## 根拠

- `tools/packaging/build_hip_linux.sh:17,79-83` — 変数の用途、GPU reader configure への展開、configure/build の順序。
- `tools/packaging/build_hip_linux.sh:21,46-47,61-76` — shell 設定、失敗時処理、engine/CPU reader への非適用。
- `terminal/tools/vision/CMakeLists.txt:26-38,64-70,85-90` — reader の backend 条件と HIP reader の構成。

