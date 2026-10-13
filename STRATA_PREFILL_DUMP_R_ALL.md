# `STRATA_PREFILL_DUMP_R_ALL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有の CUDA 系および SYCL の実装を確認した。外部ライブラリや GPU ドライバーの環境変数動作は対象外。

## 役割

プロンプト処理の最終 residual `m.R` を、各位置について BF16 の生データとしてファイルに追記する診断・データ採取用フックです。コードコメントは draft-layer distillation data 用としています。通常の生成設定を変える分岐ではなく、ファイル出力と GPU/queue の同期を追加します。

読み取り箇所は `src/prefill/prefill.cpp` と `sycl/src/prefill/prefill.cpp` の各1箇所です。両方とも layer-split の後続 stage がない経路（`next_ == nullptr`）で、chunk の layer 処理後に実行されます。先行 stage は residual を次 stage に hand-off して `continue` するため、その stage ではこのファイル出力を行いません。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 出力しない。 |
| 設定済み（空文字を含む） | 設定値をファイルパスとして `fopen(path, "ab")` に渡す。開けた場合に出力する。 |
| `0`、`false` などの文字列 | 特別な無効値として解釈しない。文字列全体をパスとして扱う。 |

`getenv()` の戻り値が null かどうかだけを調べ、`atoi` 等の変換や真偽文字列の比較はしません。したがって空文字も設定ありとして同期処理まで進みますが、空のパスを `fopen` が開けない場合は書き込みません。相対パスならプロセスの作業ディレクトリからのパスです。既定値、CLI 引数、設定ファイルによる上書きはありません。

## 有効になる条件

- `Prefill::run_impl()` が実行され、その chunk が `next_ == nullptr` の stage に到達すること。
- chunk の layer 処理後に `ple_land()` が成功して処理が続くこと。途中 return/error した chunk は出力箇所まで到達しません。
- 当該箇所で環境変数が設定されており、指定パスを `fopen(..., "ab")` で開けること。

CUDA 系では `src/prefill/prefill.cpp`、SYCL では `sycl/src/prefill/prefill.cpp` に同じ機能があります。両方とも `D = N * HC` を固定定義し、`N=2560`, `HC=4`, `D=10240` です。外側の chunk ループごとに条件を評価するため、値を static cache しません。コード上は各 chunk のこの箇所で環境変数を読み直します。両環境変数 `STRATA_PREFILL_DUMP_R` と `STRATA_PREFILL_DUMP_R_ALL` が同時に設定されていれば、別々の出力処理が両方行われます。

## 実行時の詳細

環境変数が設定されていると、ファイルを開けるかどうかにかかわらず、まず CUDA stream または SYCL queue を同期します。その後ファイルを append mode で開き、chunk 内の全 `T` 行を最大512行ずつ host にコピーして BF16 に変換し、順番に書きます。`std::fwrite` の戻り値は確認せず、`fopen` が失敗しても警告やエラーを出しません。ファイル書き込みの失敗をこの箇所が `err` に設定することもありません。

出力はヘッダーなしの連続した 16-bit 値です。各行は `m.R` の `D=10240` 個の float 要素を並び順のまま BF16 に丸めたもので、1行あたり 20,480 bytes です。変換は float の上位16 bitを取り出し、下位部と上位部の最下位bitを使って round-to-nearest-even を行っています。値は `uint16_t` 配列をそのまま書くため、ファイル内の byte order は実行環境の native byte order です。行の位置番号、chunk 長、request 境界、shape はファイルに格納されません。コードコメント上は chunk と request をまたいで追加される形式です。同じパスを使うと既存ファイル末尾に追記し、開始時に切り詰めません。

## 根拠

- `src/prefill/prefill.cpp:98-104`: `N`, `HC`, `D` の固定値。
- `src/prefill/prefill.cpp:2139-2143`: `run_impl()` の chunk ループと `T` の算出。
- `src/prefill/prefill.cpp:4050-4071`: 先行 layer-split stage は residual を hand-off して次 stage に進む。
- `src/prefill/prefill.cpp:4085-4105`: 環境変数判定、同期、ファイル append、512行単位のコピー、BF16丸め、書き込み。
- `sycl/src/prefill/prefill.cpp:98-100, 4480-4502`: SYCL 側の対応する定義と出力処理。
- `src/prefill/prefill.cpp:4230-4242`, `sycl/src/prefill/prefill.cpp:4703-4715`: `run()` から `run_impl()` を呼び、pipeline drain を行う経路。

`docs/DETAILS.md` などの資料でこの変数の追加仕様や出力レイアウトを説明する記述は確認できなかったため、形式と挙動は上記実装から記述した。
