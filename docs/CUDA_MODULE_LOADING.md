# `CUDA_MODULE_LOADING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリや GPU ドライバーが値をどう解釈するかは対象外。

## 役割

Strata の実行ファイルは、起動時にこの環境変数が未設定なら、プロセス環境に `CUDA_MODULE_LOADING=EAGER` を設定します。ソース内のコメントでは、CUDA context 作成時に CUDA kernel を読み込む意図を説明しています。CUDA/HIP/SYCL の各実行条件で設定ブロック自体を分岐していませんが、外部ランタイムがこの値をどう扱うかは Strata のソースからは説明しません。

## 値と判定

| 起動時の値 | Strata の処理 |
|---|---|
| 未設定 | `EAGER` を設定する |
| 空文字 | 設定済みとして扱い、変更しない |
| その他の文字列（`LAZY` などを含む） | 設定済みとして扱い、変更しない |

値の内容は比較も parse もされず、`std::getenv(...) == nullptr` かどうかだけを確認します。したがって、空文字や Strata が認識する有効値かどうかにかかわらず、環境に値が存在すれば既存値を保ちます。POSIX 系では `setenv(..., 0)` を使い、上書きを禁止します。Windows では未設定を確認した後に `_putenv_s` で設定します。

## 有効になる条件

この処理は通常の `src/program/generate.cpp` と `sycl/src/program/generate.cpp` の `main` にあります。該当する実行ファイルを起動し、この処理に到達することが条件です。CUDA/HIP/SYCL のビルド条件によるガードは設定箇所にありません。

CUDA 側では `--version` / `-V` の早期終了判定の後、オプション解析より前に実行されます。そのため、これらのオプションで早期終了する呼び出しでは設定処理に到達しません。HIP 用のビルドでも同じ無条件ブロックがコンパイルされますが、ここから HIP runtime がこの変数を使うとは結論できません。

## 実行時の詳細

環境の確認は `main` の起動時に一度行います。値が既に設定されている場合、それが `EAGER`、`LAZY`、空文字、その他の値のいずれでも Strata は変更しません。未設定の場合は `EAGER` を設定し、後続処理にそのプロセス環境を渡します。設定関数の戻り値は確認しておらず、この処理自身によるログ出力もありません。

実装コメントは、CUDA の既定の lazy loading では長い prompt の途中で初めて使う kernel のコード領域を確保できず、`cudaFuncSetAttribute` の out-of-memory で engine が終了した事例を説明しています。これはコードコメントに記された背景であり、調査時点での独立した測定結果ではありません。Strata の `docs/DETAILS.md` にはこの変数の説明は見つかりませんでした。

## 根拠

- `src/program/generate.cpp:1730-1760` — CUDA/HIP 側 `main`。CUDA `--version` の早期終了後、値の有無を調べ、未設定時に `EAGER` を設定する。
- `sycl/src/program/generate.cpp:1627-1651` — SYCL 側 `main` にも同じ環境変数の確認・設定がある。
- `CMakeLists.txt:74-79` — CUDA kernel のグループ別実体化と VRAM に関するコメント中で `CUDA_MODULE_LOADING=EAGER` に言及する。これは説明コメントであり、環境変数の読み取り実装ではない。
