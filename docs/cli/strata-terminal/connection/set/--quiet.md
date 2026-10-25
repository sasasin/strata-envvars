# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True` |

## 役割

接続設定の変更結果など、人向けの成功情報を標準出力に表示しないためのフラグです。接続の検証や保存内容は変えません。`--plan` と組み合わせると保存予定を表示せずに確認できます。

## 使い方

既存の保存済み接続名に置き換えて、保存せずに変更案を検証する例です。

```sh
strata connection set <NAME> prefix=/strata --plan --quiet
```

変更を保存する例では `--plan` を外します。その場合、`--quiet` を付けても設定ファイルへの保存は行われます。

## 値と既定値

`--quiet` は `argparse` の `store_true` フラグで、引数値は取りません。省略時は `False` です。`-q` などの別名は parser にありません（`strata_cli/monitor_commands.py:86-94`）。

このフラグ自体に値の validation はありません。`set` の位置引数 `KEY=VALUE` は `url=ROOT`、`prefix=/PATH`、`credential_env=ENV_NAME` のいずれかでなければならず、各値は接続データの validation を受けます（`strata_cli/connections.py:245-253`）。URL は埋め込み認証情報を含まない HTTP(S) のサーバールートで、リモート宛ては HTTPS が必要です（`strata_cli/client.py:45-63`）。prefix は空または `/`、もしくは最大256文字の単純なパスセグメントで、`.`・`..` やクエリ等は受け付けません（`strata_cli/client.py:66-76`）。認証参照は ASCII の環境変数名です（`strata_cli/connections.py:41-42,66-69`）。

## 実行時の動作

`strata connection set` の `set` parser に `--quiet` が登録されます（`strata_cli/monitor_commands.py:75-94`）。トップレベル CLI は `connection` を `monitor_commands.run()` に渡します（`strata_cli/cli.py:2119-2165`）。`run()` は `--quiet` が指定され、かつ JSON 出力でないときだけ `quiet=True` とし、`connection` のローカル処理の標準出力を一時バッファへリダイレクトします（`strata_cli/monitor_commands.py:167-175`）。したがって通常の人向け成功結果は表示されません。

`set` はまず保存済み接続を読み、指定されたキーと値から候補を作ります。`--plan` の場合は現在値と比較した `would_save` を含む結果を作るだけで、保存しません。`--plan` がなければ `save()` を呼び、変更を保存します（`strata_cli/monitor_commands.py:140-163`）。保存処理は接続名のロック下で revision を照合し、同じ値なら書き換えず、異なる場合は一時ファイルから置換します（`strata_cli/connections.py:256-270`）。`--quiet` はこれらの処理・副作用を変更しません。

`--json` は `--output json` の別表記です。JSON 出力では `quiet` が無効となり、機械可読な結果が標準出力に出ます。`--output` は `human`（既定）または `json` を選べます（`strata_cli/monitor_commands.py:91-94`、`strata_cli/cli.py:2232-2239`）。

## 適用条件と副作用

このオプションが抑えるのは `connection` / `config` のローカルコマンドが出す標準出力です。接続先への通信は `set` の処理にありません。`--plan` なしでは、成功時にローカルの接続設定ファイルを書き換えることがあります。保存場所は `STRATA_CONNECTION_DIR` があればその絶対パス、Windows では `%APPDATA%/Strata/connections`、その他では `$XDG_CONFIG_HOME/strata/connections`（未設定なら `~/.config/strata/connections`）です（`strata_cli/connections.py:72-95`）。

## 出力とエラー

人向け出力で `--quiet` を指定すると、成功時の結果 JSON は標準出力に表示されません。エラー処理は quiet 時も stderr へメッセージを出し、原因に応じた終了コードを返します（`strata_cli/monitor_commands.py:124-129,167-175,231-240`）。たとえば存在しない接続名、無効な設定値、保存先の問題は接続処理のエラーとなります。`--if-revision` が現在の revision と一致しなければ保存前に終了コード 6 のエラーになります（`strata_cli/monitor_commands.py:152-160`）。

## 根拠

- 索引上のコマンド階層と予定リンク: `docs/cli/README.md` の `strata connection set` 節（1071-1080行）。
- `--quiet` を含む parser 定義: `strata_cli/monitor_commands.py:75-94`。
- quiet の適用、JSON 時の出力、エラー経路: `strata_cli/monitor_commands.py:124-175,231-244`、トップレベルの routing: `strata_cli/cli.py:2119-2165,2232-2239`。
- `set` の候補生成、plan/save 分岐: `strata_cli/monitor_commands.py:140-163`。
- 代入値の validation と revision 保護付き保存: `strata_cli/connections.py:245-270`。
- URL/prefix の形式: `strata_cli/client.py:45-76`。

調査範囲は上記 checkout の Terminal CLI ソースです。同一 revision の CLI `--help` や Release 配布物は補助資料として確認していません。
