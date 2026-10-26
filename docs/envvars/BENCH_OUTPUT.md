# `BENCH_OUTPUT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

同梱の公開 fixture ベンチマークスクリプト `bench/results/2026-10-07-community-arc-b65-v01402/public-fixtures.py` が、計測結果を書き出すディレクトリを指定します。Strata エンジン本体の通常実行設定ではなく、このスクリプト専用の出力先です。

## 値と判定

| 状態 | 挙動 |
|---|---|
| 未設定 | `os.environ['BENCH_OUTPUT']` の参照で `KeyError` になり、出力先作成より前にスクリプトが失敗する。 |
| 空文字 | `Path('')` はカレントディレクトリを指し、`mkdir(exist_ok=False)` が既存ディレクトリを作ろうとして `FileExistsError` になる。 |
| ディレクトリパス | `Path` に渡され、相対パスはスクリプト起動時のカレントディレクトリ基準で解決される。 `mkdir(exist_ok=False)` により、新規ディレクトリとして作成できる場合に続行する。 |
| 既存パス | ディレクトリが既に存在すれば作成に失敗する。既存内容への追記や上書きはしない。 |

値の文字列比較や数値変換はありません。絶対パスを必須とする処理もありませんが、同梱 `BUILD.md` の実行例は絶対パスを指定しています。

## 有効になる条件

この変数を読むのは `public-fixtures.py` だけです。同スクリプトを `matched` モードで実行した場合に使われます。CLI 引数に出力先を渡す経路や、別変数による fallback はありません。Strata エンジンの通常の起動・推論経路での読み取りは確認できませんでした。

## 実行時の詳細

スクリプト開始後、引数解析で `matched` を確認した後に `BENCH_OUTPUT` を読み、直ちに出力ディレクトリを新規作成します。その後のベンチマーク処理では、`requests.json` と `lifecycle.json` に進捗・計測行と起動情報を保存し、終了処理で `result.json` を書きます。したがって、変数の値は出力先パスを決めるだけで、測定内容やエンジンの挙動を切り替えません。環境変数はスクリプト起動時に一度参照されます。

同梱の `BUILD.md` は `BENCH_OUTPUT=/absolute/path/to/new-public-512` を設定して同スクリプトを起動する例を示しています。`docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。

## 根拠

- `bench/results/2026-10-07-community-arc-b65-v01402/public-fixtures.py:12-20`: モード引数、必須の環境参照、出力ディレクトリの新規作成。
- `bench/results/2026-10-07-community-arc-b65-v01402/public-fixtures.py:58-60,99,136-137`: 出力ファイルと保存タイミング。
- `bench/results/2026-10-07-community-arc-b65-v01402/BUILD.md:94-100`: 実行手順と絶対パスの設定例。
