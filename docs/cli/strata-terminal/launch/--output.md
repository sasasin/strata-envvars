# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

起動・計画・一部の管理結果を、人向けのテキストか機械処理向けの JSON で出力します。値を指定しない場合は `human` です。`--output json` は起動内容を読み取り専用にする指定ではありません。変更せず計画だけを見る場合は `--plan` も指定します。

## 使い方

```sh
# 計画を JSON で表示する（起動・変更はしない）
strata launch --plan --model q2_0 --output json

# 起動結果を JSON で受け取る
strata launch --model q2_0 --no-tui --output json
```

## 値と既定値

- parser は `choices=("human", "json")`、既定値 `human` として定義されています。別名はありません（`strata_cli/launch/cmd.py:140`）。
- 値を省略すると人向けの出力です。`--output` の値を省略した場合や、`human` / `json` 以外を渡した場合は `argparse` の選択肢検証で拒否されます。
- 同じ `--output` を複数回指定したときの個別仕様はソースで定義されていません。`argparse` の通常の単一値引数として最後に解析された値が Namespace に入ります。

## 実行時の動作

- `run_launch` は `--output json` を machine mode として扱います。失敗は stdout に `schema_version`、`ok: false`、`error.code`、`error.message` を持つ JSON を出し、返したコードを終了コードにします。human mode の失敗は `strata: ...` を stderr に出します（`strata_cli/launch/cmd.py:630-641`）。
- machine mode では計画結果を `{"schema_version":1,"ok":true,"plan":...}` として出力します。human mode では計画の要約を行ごとに表示します。どちらも `--plan` の経路であり、計画表示後に終了します（`strata_cli/launch/cmd.py:733-760`）。
- 起動成功時は、稼働中の URL、profile、再利用の有無、API key の有無（キーそのものではなく `set`）、tuning 情報、通知を JSON で出します。エンジン起動に至らなかった場合も `serving: false`、原因情報、メッセージを含む成功形式の JSON を出します（`strata_cli/launch/cmd.py:785-805`）。
- `--list-presets` は preset 一覧を JSON 化し、`--status` は稼働中 launch の一覧を JSON 化します（`strata_cli/launch/cmd.py:643-671`）。
- `--output json` のとき対話式 TUI は選ばれません。質問可能な画面がなく、起動対象も指定していない場合はエラーになります（`strata_cli/launch/cmd.py:685-710`）。machine mode は自動確認扱いで runner に渡されます（`strata_cli/launch/cmd.py:715-716`）。

## 適用条件と副作用

- `--output json` は起動処理自体を無効にしません。`--plan` がなければ通常の runner 実行に進み、必要に応じてモデル等の準備や server 起動を行います（`strata_cli/launch/cmd.py:733-760, 784-805`）。
- `--output json` は `--data-dir` と併用しても既存モデルの移動を選ばず、新しいフォルダーを新規ダウンロード先として使う選択になります。移動するには明示的な `--move-data` が必要です（`strata_cli/launch/cmd.py:504-526`）。
- machine mode では途中経過・警告の人向け表示を抑えます。runner に渡す出力 callback は `machine` を quiet として受け取り、通知の行表示も JSON 経路では省略されます（`strata_cli/launch/cmd.py:432-457, 761-771`）。
- `--delete-preset` と `--stop` は `--output json` でもそれぞれ通常のテキストを出します。`--show-key` も成功時はキーをテキストで表示するため、JSON 出力を期待して機密情報を隠せると考えてはいけません。キーがない場合の失敗は machine mode の JSON エラーです（`strata_cli/launch/cmd.py:657-677`）。
- 索引の `strata launch` scope に対応する parser は `strata_cli/launch/cmd.py:75-146` です。同ファイルの `strata connect` にも独立した同名オプションがありますが、そちらは別コマンドの出力仕様であり、この文書の対象外です（`strata_cli/launch/cmd.py:148-165`）。

## 出力とエラー

- JSON 出力は stdout に1つの JSON object として書かれます。失敗時の終了コードはエラー経路ごとに設定され、例として parser / 引数起因は通常 `2`、カタログ利用不可等は `5`、中断は `130` です（`strata_cli/launch/cmd.py:636-641, 679-684, 832-837`）。
- `--output` の未対応値など parser 段階の引数エラーは `run_launch` に入る前に発生します。launch/connect で認識されない引数は `strata: ... See: strata launch --help` を stderr に出して `2` を返します（`strata_cli/cli.py:2223-2231`）。
- 機械可読化は `strata launch` の分岐で個別に実装されています。特に `--delete-preset`、`--stop`、`--show-key` の成功出力は JSON object ではありません（`strata_cli/launch/cmd.py:657-677`）。

## 根拠

- `strata_cli/launch/cmd.py:127-146` — launch parser の `--output` 宣言と launch 用管理オプション。
- `strata_cli/launch/cmd.py:630-677` — machine mode、共通失敗出力、preset / status / delete / stop / key の分岐。
- `strata_cli/launch/cmd.py:685-716` — TUI 選択、非対話エラー、自動確認としての runner 設定。
- `strata_cli/launch/cmd.py:733-805` — plan、起動失敗・成功時の JSON / human 出力。
- `strata_cli/launch/cmd.py:504-526` — JSON / yes / plan と `--data-dir` の移動選択規則。
- `strata_cli/cli.py:2223-2237` — parser 呼び出し、launch の未知引数エラー、最上位の dispatch。
