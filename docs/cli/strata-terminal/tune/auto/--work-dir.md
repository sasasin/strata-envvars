# `--work-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--work-dir` |
| 別名 | なし |
| 値 | ディレクトリのパス（文字列） |

## 役割

チューニング中に使う一時的な実行設定と engine / worker のログを置くディレクトリを指定します。指定しない場合は `strata-tune-` を接頭辞にした一時ディレクトリが作られます。

## 使い方

```sh
strata tune auto my-profile --work-dir ./tune-work
```

`my-profile` は対象の保存済み profile 名または run configuration JSON です。相対パスは CLI を起動したプロセスの作業ディレクトリを基準に解釈されます。

## 値と既定値

- 値は `argparse` の文字列として受け取り、parser でパス形式・存在・書き込み権限を検証しません。省略時の値は `None` です。
- 空文字列は `auto()` 側の真偽判定で未指定と同じ扱いになり、一時ディレクトリが使われます。
- 同じオプションを複数回指定した場合は通常の `argparse` の `store` 動作により最後の値が残ります。
- `auto()` は指定値を `Path` に変換して `WorkerSession` に渡します。`WorkerSession` は親ディレクトリも含めて作成し、既に存在するディレクトリも受け入れます（`mkdir(parents=True, exist_ok=True)`）。

## 実行時の動作

`strata tune auto` は対象設定の読み込み、engine の存在確認、チューニング条件の準備を済ませてから作業ディレクトリを選び、worker session を作ります。明示したパスはそのまま使い、省略時には `tempfile.mkdtemp(prefix="strata-tune-")` が作る一時ディレクトリを使います。チューニング run ごとに `engine-N.log`、`worker-N.log`、`run-N.json` をその場所に作成し、コピーした設定を用いて loopback 上の worker server / engine を起動します。worker 終了時には子プロセスを終了しますが、作業ディレクトリや生成ファイルを削除する処理はこの経路にありません。

パスが既に存在し、同じ run 番号のファイルがある場合、engine log は空文字で書き直され、worker log は `open(..., "w")` で切り詰められ、設定 JSON も `write_text()` で上書きされます。並行する実行で同じ作業ディレクトリを共有すると、各プロセスの run 番号が同じファイル名に到達し得ます。実行ごとに専用の空ディレクトリを指定してください。

このオプションは `strata tune auto` のものです。同じ `--work-dir` は別コマンド `strata presets recheck` にも独立して定義されていますが、この文書の対象範囲には含みません。

## 適用条件と副作用

- `--work-dir` 自体はファイルシステム上のパス検証を行いません。ディレクトリ作成や後続のファイル書き込みで失敗した場合は OS エラーになります。
- 指定したディレクトリとその親が作成されることがあります。そこに既存の `engine-N.log`、`worker-N.log`、`run-N.json` があれば上書きされます。
- worker server は設定コピーを使って測定ごとに起動され、通常の終了・割り込み処理で終了対象になります。作業ファイルは残ります。
- 作業ディレクトリ作成後の実行では engine の測定を行います。`--work-dir` は測定内容・保存プリセットの保存先を指定するオプションではありません。

## 出力とエラー

- 作業ディレクトリの作成やログ・設定ファイルの作成で発生した `OSError` は、CLI の共通ハンドラで整形されます。人間向け出力では `strata: <エラー>` を stderr に出し、終了コード `6` を返します。`--output json` では `{"schema_version":1,"ok":false,"error":{"code":6,"message":"..."}}` 形式を stdout に出します。
- ディレクトリが作成できた後の tuner の通常出力（人間向け結果または JSON 結果）は `--output` に従います。進捗ログは人間向け実行では stderr に出ます。

## 根拠

- parser 定義、既定値、help: `strata_cli/tune_commands.py:20-46`（`--work-dir` は 43 行目）。
- 対象設定等の事前処理と work directory 選択、session への受け渡し: `strata_cli/tune_commands.py:174-219`。
- session が選択パスを `Path` にし、親を含めて作成: `strata_control/tune_session.py:420-435`。
- run ごとのログ・設定ファイル作成と worker 起動: `strata_control/tune_session.py:443-509`。
- worker プロセス終了処理: `strata_control/tune_session.py:510-522`。
- tune コマンドの parser 登録と `auto()` への dispatch: `strata_cli/cli.py:486-487`, `strata_cli/cli.py:1652-1653`。
- 共通 OSError ハンドラとエラー出力: `strata_cli/cli.py:527-532`, `strata_cli/cli.py:2176-2183`。
- 調査範囲は上記 checkout の Terminal CLI と WorkerSession 実装です。別 OS・権限・ファイルシステムでの実際の挙動や Release 配布物は、この調査では実行・検証していません。
