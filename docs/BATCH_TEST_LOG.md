# `BATCH_TEST_LOG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 同梱ツール `tools/batch_test.py`。

## 役割

`tools/batch_test.py` が起動する Strata エンジンの標準エラー出力を保存するファイル名を指定します。Strata エンジン本体の動作を切り替える変数ではなく、バッチ生成の比較・計測ツールがエンジン診断出力を記録するために使います。同ツールは単独の `GEN` と同時バッチの `BGEN` を実行し、生成 token を比較します（`docs/BATCHING.md:520-523,563-564`）。

## 値と判定

`os.environ.get("BATCH_TEST_LOG") or ...` で値を読みます。数値変換や文字列検査はありません。

| 値 | 動作 |
|---|---|
| 未設定 | `tempfile.gettempdir()` の `batch_test_engine.log` を使用 |
| 空文字 | 未設定と同じ既定パスを使用（Python では空文字が偽として扱われるため） |
| 空でない文字列 | その文字列をログファイルのパスとしてそのまま使用。空白の除去、環境変数・チルダ展開、相対パスの絶対化はしない |

指定値および既定値のパスは `open(path, "w")` で開きます。既存ファイルは切り詰められ、存在しないファイルは作成されます。親ディレクトリがない、または書き込みできない場合は `open` の例外となり、その後のエンジン起動には進みません。相対パスは Python ツールの作業ディレクトリ基準です。

## 有効になる条件

この変数を読むのは `tools/batch_test.py` の `Engine` 初期化時です。環境変数を設定しただけではファイルを開かず、同ツールが `Engine` を生成する場合に使われます。Strata エンジン本体に `BATCH_TEST_LOG` の読み取り箇所はありません。

## 実行時の詳細

ツールは `Engine` 初期化時にログファイルを開き、そのファイルオブジェクトを `subprocess.Popen(..., stderr=self.log)` に渡します。したがって起動したエンジンの stderr がファイルに入り、stdout はパイプ経由でツールが `READY` や生成結果を読みます。エンジンが `READY` を出す前に終了した場合、ツールは `the engine ended before READY - see <path>` で終了し、指定したログパスを案内します。ログファイルを開くタイミングは設定ファイルと tokenizer の読み込み、prompt の準備の後です。

子プロセス用環境は親環境のコピーにツール内の `extra_env` を加えて作られるため、`BATCH_TEST_LOG` は特別に除去・変更されず子プロセスにも継承されます。ただし、調査対象ソース内でエンジンがこの変数を読む実装は確認できません。

## 根拠

- `tools/batch_test.py:47-66` — パスの選択、ファイルの open、stderr への接続、`READY` 前終了時の案内。
- `tools/batch_test.py:77-109` — CLI 設定・tokenizer・prompt 準備後に `Engine` を生成。
- `docs/BATCHING.md:520-523,563-564` — 同梱テストツールが行うバッチ比較の説明。
