# `STRATA_DSV41_BIN`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

DeepSeek-V4.1 の長い prompt での layer skip を比較する開発用テスト `tools/dsv41/test_prompt_skip.py` に、テスト対象の `strata-dsv41` 実行ファイルのパスを渡します。Strata の通常の setup / launch がこの変数を読む実装は確認できません。この変数を利用者向け実行設定として説明できる根拠はありません。

## 値と判定

テストモジュールの import 時に `os.environ.get("STRATA_DSV41_BIN")` で一度読み取ります。値は文字列のまま保持され、strip、パス解決、存在確認、実行権限確認は行いません。

| 環境変数の状態 | テストの扱い |
|---|---|
| 未設定または空文字 | `BIN` が falsy となるため、実行比較テストを skip |
| 空でない文字列 | `PACK` と `IDS` も空でない場合に、比較テストを有効化 |

テスト実行時は値を `subprocess.run` の argv の先頭（実行ファイル名）としてそのまま渡します。シェル経由ではありません。間違ったパスや起動失敗は `check=True` によりテスト失敗になります。値を数値や真偽値に変換する処理はありません。

## 有効になる条件

この読み取りはテスト専用です。`STRATA_DSV41_BIN`、`STRATA_DSV41_PACK`、`STRATA_DSV41_IDS` のすべてが非空文字列の場合だけ、`test_scored_rows_after_a_skipped_prompt_match_the_full_work` が実行されます。GPU とDeepSeek-V4.1 pack、golden IDsを必要とする旨はテスト冒頭に記されていますが、GPU等の有無をこの環境変数で判定するわけではありません。

通常のsetupコードで独自ビルドのDeepSeek engineを指定する変数は`STRATA_DSV41_EXE`です。setupはその値を空白除去してから扱い、空でなければ指定ファイルが存在する場合にそのパスを使います。`STRATA_DSV41_BIN`と`STRATA_DSV41_EXE`は別の名前であり、通常のsetup / launchに`_BIN`が伝播する処理は確認できません。

## 実行時の詳細

有効な場合、テストは`STRATA_DS4_PROMPT_SKIP=0`と`=1`の2回、同じバイナリを起動します。各起動には`--pack`で`STRATA_DSV41_PACK`、`--score`で`STRATA_DSV41_IDS`を渡し、score出力を一時ディレクトリに書きます。親プロセスの環境を複製して`STRATA_DS4_PROMPT_SKIP`、`DS4_SCORE_PREFIX=4200`、`DS4_CHUNK=1024`を上書きして子プロセスに渡します。結果のKL、top-1一致率などを比較します。

このため、モジュールを import した後に親プロセスの環境を書き換えても`BIN`は更新されません。テストコード自体が実行ファイルを探したり、setupが選んだengineパスを取得したりする処理もありません。

## 根拠

- `tools/dsv41/test_prompt_skip.py:1-11` — テストの目的、必要なGPU / pack / IDs、起動例。
- `tools/dsv41/test_prompt_skip.py:23-25,38-47` — import 時の環境読み取り、3変数が揃う場合のskip条件、子プロセス起動と環境の設定。
- `tools/dsv41/test_prompt_skip.py:48-52` — 2回の出力を比較する判定。
- `setup.py:7815-7829` — setup / launchで使う変数は`STRATA_DSV41_EXE`であり、その値の処理。
- `setup.py:8107-8116` — setup時の smoke test の制御は別変数`STRATA_DSV41_NO_SMOKE`。

調査範囲内の完全一致検索では、`STRATA_DSV41_BIN`の参照は`tools/dsv41/test_prompt_skip.py`だけでした。テスト専用コードは本番の環境変数実装根拠に含めないという調査基準に従い、上記のテスト挙動のみを記載しています。通常実行時の意味は確認できません。
