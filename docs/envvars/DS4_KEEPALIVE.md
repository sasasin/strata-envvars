# `DS4_KEEPALIVE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

Metal 上の DS4 runtime で、GPU dispatch が続いている間に別の command queue から小さな spin kernel を送る keep-alive thread を起動します。実装コメントによると、GPU が低クロックの idle 状態に入るのを抑えるための処理です。環境変数は有効/無効だけを選び、spin kernel の反復回数は関連変数 `DS4_KEEPALIVE_ITERS` が指定します。これは DS4 runtime 専用で、通常の Strata Metal runtime では `STRATA_DS4_RUNTIME` が定義されないため、この処理はコンパイル対象になりません。

## 値と判定

| `DS4_KEEPALIVE` | 判定 |
|---|---|
| 未設定 | 無効。keep-alive thread を開始しない |
| 空文字を含む何らかの値が設定済み | 有効。値の内容は検査しない。`0` や `false` も有効 |

判定は `std::getenv("DS4_KEEPALIVE")` の null 判定であり、数値や文字列の parse はありません。CLI 引数や他の設定による上書き経路もありません。ソースの `mtl_rt.h` には `DS4_NO_KEEPALIVE=1` で無効化するとのコメントがありますが、調査対象 commit のソース全体でこの名前の読み取りは見つからず、実装上の無効化方法は `DS4_KEEPALIVE` を unset にすることです。

反復回数は thread 内で一度 `DS4_KEEPALIVE_ITERS` から `std::atoi` で読み、`uint32_t` に変換します。未設定なら `20000`、空文字・数値に変換できない文字列なら `atoi` の結果 `0` です。数値の後ろに非数値があっても先頭の数値部分が使われ、負の `int` 値は符号なし 32-bit 値に変換されます。明示的な範囲検査や clamp はありません。反復回数は DS4_KEEPALIVE の有効判定とは独立です。

## 有効になる条件

- `metal/src/mtl_rt.mm` が `STRATA_DS4_RUNTIME` 定義付きでビルドされること。`metal/CMakeLists.txt` はこの定義を DS4 専用 runtime object に付け、その object を `strata_ds4` にリンクします。
- DS4 Metal engine が `ds4_finish.cpp` の `ensure()` を初めて通ること。この初期化経路が `Context::start_keepalive()` を呼びます。
- 起動時点で `DS4_KEEPALIVE` が設定されていること。

この処理は Metal runtime に属し、CUDA/HIP/SYCL の読み取り箇所はありません。`DS4_KEEPALIVE` が未設定なら spin thread は作られません。設定値を起動後に変更しても、初期化後に再評価されません。

## 実行時の詳細

`start_keepalive()` は設定有無を判定し、既に開始済みなら atomic flag で二重起動を防ぎます。成功すると GPU device を保持する detached thread を作ります。thread は spin kernel の Metal library と pipeline、command queue、64-byte buffer を作り、`DS4_KEEPALIVE_ITERS` を一度読み取ります。library または pipeline の作成に失敗すると、その thread はそのまま終了します。失敗ログや再試行はありません。

thread は最後の dispatch 記録時刻 `g_last_act_ns` が現在から 50 ms より古いとき、2 ms sleep してから再確認します。記録が 50 ms 以内なら、256 thread の spin kernel を別 queue で dispatch し、完了を待って繰り返します。dispatch 記録時刻は DS4 runtime の `Context::run()` が単一 dispatch を encode した時に更新されます。thread に終了条件はなく、process 終了まで動作します。keep-alive 自体のログ出力はありません。

`DS4_KEEPALIVE` の判定は DS4 Context 初期化時、反復回数は起動した worker thread 内で一度行われます。`g_ka_on` は有効判定後すぐ true になるので、Metal library/pipeline 作成に失敗して thread が終了しても同一プロセス内で再起動されません。

## 根拠

- `metal/src/mtl_rt.mm:364-412` — DS4 runtime 限定の keep-alive 実装、環境変数判定、反復回数の parse、待機と dispatch、失敗時の return。
- `metal/src/mtl_rt.mm:902-931` — DS4 runtime の dispatch encode と `g_last_act_ns` 更新。
- `metal/src/engine/ds4_finish.cpp:62-85` — DS4 Metal Context の初期化時に `start_keepalive()` を呼ぶ。
- `metal/CMakeLists.txt:151-169` — `STRATA_DS4_RUNTIME` を DS4 用 runtime object に定義し、`strata_ds4` にリンク。
- `metal/src/mtl_rt.h:86-89` — keep-alive の説明コメント。`DS4_NO_KEEPALIVE` のコメントは現行の実装判定と一致しない。
