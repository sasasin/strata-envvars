# `DISABLE_AUTOUPDATER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この名前は Strata が自身のプロセス環境から値を読む設定ではない。Strata の `strata connect claude-code` が Claude Code 用設定を生成するとき、`~/.claude/settings.json` の `env` オブジェクトへ文字列値 `"1"` として含める。端末向け表示では環境設定一覧に、JSON 出力では `env` フィールドに現れる。Strata がこの値を使って自身の更新動作を変える処理は確認できない（`terminal/strata_cli/launch/harness.py:158-168,343-347`; `terminal/strata_cli/launch/cmd.py:1074-1085,1120-1133`）。

## 値と判定

Strata は `DISABLE_AUTOUPDATER` を `getenv` / `os.environ` などから読み取らず、入力値の parse や真偽判定もしない。Claude Code 用 `claude_env()` が常に固定文字列 `"1"` を生成するため、Strata 側に未設定・空文字・境界値・無効値の分岐はない。親プロセスに同名環境変数が設定されていても、その値を参照するコードはなく、生成値の選択にも使われない（`terminal/strata_cli/launch/harness.py:158-163`）。

| 条件 | Strata が行うこと |
|---|---|
| `strata connect claude-code` の設定生成 | `env.DISABLE_AUTOUPDATER` に文字列 `"1"` を設定 |
| 他のハーネス、または Strata 自身の実行 | この名前に関する環境値の読み取り・判定はない |

## 有効になる条件

- `strata connect claude-code` を選ぶこと。Claude Code のハーネス登録が `claude_env` を環境設定生成関数として指定している（`terminal/strata_cli/launch/harness.py:293-295`）。
- 設定ファイルへ反映するには `--write`（またはモニターの Connect 画面で Write）を実行して書き込みを選ぶこと。表示・コピーだけの場合は値を出力またはクリップボード用テキストに含めるが、ファイルには書かない（`terminal/strata_cli/launch/cmd.py:1108-1119,1128-1133,1156-1167`; `terminal/strata_cli/launch/monitor_ext.py:247-253,259-282`）。
- `~/.claude/settings.json` が既にある場合、JSON の再帰マージでは生成側の同名キーが優先されるため、このキーは `"1"` に置き換わる。Strata が Claude Code を直接起動してこの環境変数を設定する経路は、確認した参照箇所にはない（`terminal/strata_cli/launch/harness.py:364-369,423-429`）。
- `DISABLE_AUTOUPDATER` という値を Claude Code がどう解釈するかは外部プログラム側の挙動なので、本書では説明しない。

## 実行時の詳細

値は `harness.render()` がハーネスの環境辞書を呼び出す際に生成される。Strata はプロセス起動時やリクエストごとにこの環境変数を読むことも、値を cache することもない（`terminal/strata_cli/launch/harness.py:158-163,343-347`）。`strata connect claude-code` は生成した環境辞書を端末表示または JSON 出力に含め、設定ファイル書き込みでは Claude Code の設定 JSON として保存する。既存ファイルへのマージでは、同名キーに新しい生成値が使われる（`terminal/strata_cli/launch/cmd.py:1079-1085,1120-1133`; `terminal/strata_cli/launch/harness.py:355-371,423-429`）。

## ログと測定値

この名前に関する Strata 固有の有効・無効ログや測定値はない。`strata connect claude-code` の通常表示では生成された設定ファイルと Environment の一覧に `DISABLE_AUTOUPDATER=1` を表示し、JSON 出力では環境辞書に含める。設定書き込み時に失敗した場合は対象ファイルのエラーを報告し、終了コード `1` となる（`terminal/strata_cli/launch/cmd.py:1123-1133,1041-1050,1108-1115`）。

## 根拠

- `terminal/strata_cli/launch/harness.py:158-168` — 固定値を作り Claude Code 設定の `env` に埋め込む。
- `terminal/strata_cli/launch/harness.py:293-295,343-347` — Claude Code ハーネスへの登録と描画結果への環境辞書の追加。
- `terminal/strata_cli/launch/harness.py:355-399,423-429` — 設定ファイルの書き込み、既存 JSON とのマージ規則。
- `terminal/strata_cli/launch/cmd.py:1074-1085,1120-1167` — CLI の生成・表示・JSON 出力・書き込み経路。
- `terminal/strata_cli/launch/monitor_ext.py:247-282` — モニター画面でのコピーと設定書き込み。
