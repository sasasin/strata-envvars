# `PA_BENCH_OUT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA 用 `pa_bench` が計測する QSA prompt attention の出力配列を、比較用にファイルへ書き出すパスです。通常の Strata サーバーや推論 CLI の挙動を変える環境変数ではありません。`pa_bench` は記録済みの `STRATA_QSA_DUMP` を読み、ランダムな入力で `qsa_prompt_attn_batch` を実行するベンチマーク用実行ファイルです。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 出力ファイルを書かない |
| 設定あり（空文字を含む） | 値をパスとして `fopen(path, "wb")` に渡す。文字列の数値変換や内容検査、別パスへの fallback はない |

値は `getenv()` の非 null 判定だけで使われます。先頭文字や文字列全体の比較はありません。`fopen` に成功した場合は既存ファイルを `wb` で開き、`out` 配列の `float` バイト列を書きます。書き込みサイズや出力先のエラーは確認せず、`fopen` に失敗した場合もこの箇所から警告・エラーを出しません。

## 有効になる条件

`pa_bench` 自体が CMake の `STRATA_BUILD_TESTS AND STRATA_ENABLE_CUDA` 条件内でのみ追加されます。通常のサーバー／CLI のターゲットから `PA_BENCH_OUT` を読む実装は見つかりませんでした。したがって、変数を設定しても `pa_bench` 以外の実行経路には作用しません。

## 実行時の詳細

`pa_bench DUMP [reps]` は dump のヘッダーと選択・step データを読み、`qsa_prompt_attn_batch` を繰り返し実行します。関数が実行を受け付けない場合は `qsa_prompt_attn_batch declined` を stderr に出して終了するため、環境変数の出力処理には到達しません。処理完了後、結果配列 `out` を GPU からホストへコピーし、ハッシュと RMS を表示してから `PA_BENCH_OUT` を読みます。設定値が開けるパスなら `T * NH * HD` 個の `float` をホストのネイティブなバイト表現で書き出します。テキスト形式やヘッダーは付けません。

読み取りはこの `main()` の末尾で一度だけ行われます。static cache は使いませんが、読み取られるのはベンチマーク処理後です。子プロセスへの転送や、プロセス起動後の変更を再評価する処理はありません。

## 根拠

- `CMakeLists.txt:492-496` — CUDA と `STRATA_BUILD_TESTS` の条件で `pa_bench` を追加。
- `tests/cuda/pa_bench.cpp:1-4,22-35` — ベンチマークの入力と呼び出し形式。
- `tests/cuda/pa_bench.cpp:85-109` — attention 実行、失敗時の終了、出力配列の取得と表示、`PA_BENCH_OUT` の読み取りと書き出し。
