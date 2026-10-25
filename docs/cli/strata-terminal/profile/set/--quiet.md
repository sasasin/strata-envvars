# `strata profile set --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

## 概要

`--quiet` は `strata profile set` の成功時に、人間向けの標準出力を抑制します。プロファイルの変更や保存方法は変えず、出力だけを制御します。既定では無効です。JSON 出力は抑制されません。

このオプションは `strata profile set` 専用ではなく、CLI が共通オプションを追加する one-shot コマンドの一つとして有効です。本書では索引のスコープに従い `profile set` での動作を説明します。

## 使い方

```sh
strata profile set NAME parallel=8 --plan --quiet
strata profile set NAME parallel=8 --quiet
```

`--plan` を付ける例は保存せず変更案を確認します。2つ目の例は実際に保存します。`NAME` は既存プロファイル名、`KEY=VALUE` は設定です。`profile set` は名前と1個以上の assignment を位置引数に取り、`--plan`、`--output human|json` を受け付けます（`strata_cli/cli.py:84-88`）。

## 値と既定値

- 値を取りません。`store_true` のフラグで、指定すると真になります（`strata_cli/cli.py:508-515`）。
- 未指定時は無効です。共通追加時の既定値は `argparse.SUPPRESS` で、属性が省略された場合も実行時は `getattr(a, "quiet", False)` により無効として扱います（`strata_cli/cli.py:514-515, 2236`）。
- `--quiet=false` のような値指定や、quiet 自体の数値・文字列 validation はありません。

## 実行時の動作と相互作用

`profile_set` は共通オプションを後から追加する parser 群に含まれているため、このサブコマンドで `--quiet` が受理されます（`strata_cli/cli.py:508-515`）。quiet が有効で、人間向けの one-shot 出力を行う場合、CLI は `_run` の stdout を最大64 KiB保持する捕捉先へ向けます。終了コードが0なら捕捉した内容を出さず、成功時の人間向け出力が抑制されます（`strata_cli/cli.py:2196-2214, 2236-2248`）。

`profile set` の実処理は assignment を検証し、`--plan` なら変更案を返して保存せず終了します。通常実行では保存関数を呼び、変更を保存します（`strata_cli/cli.py:986-997`）。保存時はプロファイルの revision を照合し、内容に差があれば履歴へ旧内容を保存してから新内容を原子的に書き込みます。同一内容なら書き換えません（`strata_control/profiles.py:266-295`）。quiet はこれらの処理に介入しません。プロファイル層はプロセスを起動せず、ネットワークにも接続しないと説明されています（`strata_control/profiles.py:1-5`）。

`--output json` または alias の `--json` と併用すると、quiet による stdout 捕捉を行わず、JSON レコードが出力されます（`strata_cli/cli.py:513-515, 2232-2237`）。`--plan` の通常出力は `_success` に人間向け文字列を渡さないため JSON 形式ですが、`--quiet` のみで使う場合は成功時にその stdout も抑制されます（`strata_cli/cli.py:990-992, 535-542, 2236-2248`）。

## validation と適用条件

quiet 自体に追加 validation はありません。assignment の validation は quiet の有無にかかわらず実行されます。受理されるキーは `host`、`port`、`parallel`、`batch_groups`、`max_queue`、`queue_timeout`、`offline`、`batch_telemetry` です。整数・数値・真偽値の変換と各範囲検査は `strata_control/profiles.py:66-117` にあります。空 assignment や未知キーなどは `ProfileError` になります。

## 出力と失敗経路

失敗時は `_run` の例外処理がエラーを stderr（human 出力時）または JSON（JSON 出力時）へ書き、`ProfileError` の終了コードを保ちます。quiet は stderr を抑制しません（`strata_cli/cli.py:527-542, 2166-2188`）。quiet 実行中に stdout が既に捕捉されていて処理が非0で終了した場合、その内容は stderr に戻されます。捕捉量が64 KiBを超えて切り詰められた場合は、その旨も stderr に出ます（`strata_cli/cli.py:2196-2208, 2241-2248`）。

## 根拠

- parser と scope: `strata_cli/cli.py:84-88, 508-515`
- quiet の既定値、JSON との相互作用、標準出力の捕捉: `strata_cli/cli.py:2232-2248`
- profile set の plan / 保存経路: `strata_cli/cli.py:986-997`
- 成功・エラー出力と例外処理: `strata_cli/cli.py:527-542, 2166-2188`
- assignment の型変換と範囲検証: `strata_control/profiles.py:66-117`
- revision 確認、履歴、原子的保存: `strata_control/profiles.py:266-295`
