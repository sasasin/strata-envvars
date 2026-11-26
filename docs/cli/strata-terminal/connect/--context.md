# `strata connect --context`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--context` |
| 別名 | なし |
| 値 | 必須。トークン数、または `k` / `m` を付けたサイズ |

## 役割

接続先アプリの設定に書き込むコンテキスト長を指定します。サーバーを起動・再設定する値ではなく、`strata connect` が表示または生成する各アプリ用設定のモデル情報やコンテキスト管理値に反映されます。省略時は実行中 launch の設定を使い、それが取得できない場合は 32K です（`terminal/strata_cli/launch/cmd.py:1074-1079`）。

## 使い方

```sh
# Codex 用の接続設定を 64K コンテキストとして表示する（書き込みはしない）
strata connect codex --context 64k
```

表示内容をファイルへ反映する場合は `--write` を加えます。既定では確認を求め、無人実行では `--yes` が必要です（`terminal/strata_cli/launch/cmd.py:175-180`, `terminal/strata_cli/launch/cmd.py:1019-1050`）。

## 値と既定値

- 値は必須で、`--context` は `_context` 型変換を通じて `settings.parse_context` を呼びます（`terminal/strata_cli/launch/cmd.py:46-50`, `terminal/strata_cli/launch/cmd.py:173`）。
- 整数のトークン数、または `k` / `m` 単位を受け付けます。大文字小文字は区別せず、前後空白、数値中の空白・`_`・`,` は除去されます。`k` は 1024、`m` は 1024² 倍として計算し、数値が小数なら最近接整数へ丸めます（`terminal/strata_cli/launch/settings.py:90-100`）。
- 最小値は 1024 トークンです。より小さい値は拒否されます。上限値や特定モデルのコンテキスト長との照合は、この parser / 変換処理では行いません（同上）。
- 省略時、`run_connect` は `--preset` で指定した実行中 launch、または通常は最初に検出された実行中 launch の設定を参照し、その context がなければ 32768 を使います。保存済み preset 単独から context は取得せず、`launch_info` が読み取るのは実行中 launch の設定ファイルです（`terminal/strata_cli/launch/cmd.py:703-725`, `terminal/strata_cli/launch/cmd.py:1074-1079`）。

## 実行時の動作

変換後の整数を `harness.target` に渡し、接続先ごとの設定をレンダリングします（`terminal/strata_cli/launch/cmd.py:1078-1080`, `terminal/strata_cli/launch/harness.py:339-347`）。生成先により、モデルの context window、コンテキスト上限、アプリ用環境変数、圧縮・要約設定などに反映されます。例えば Codex 用設定では `model_context_window`、Claude Code 用環境では `CLAUDE_CODE_MAX_CONTEXT_TOKENS`、Pi 用設定ではコンテキスト予約値に使われます（`terminal/strata_cli/launch/harness.py:144-149`, `terminal/strata_cli/launch/harness.py:158-163`, `terminal/strata_cli/launch/harness.py:199-202`）。

明示した値は実行中 launch から取得される context より優先されます。`--check` の通信確認には context は渡されず、確認処理には URL・key・model が渡されます（`terminal/strata_cli/launch/cmd.py:1074-1080`, `terminal/strata_cli/launch/cmd.py:1088-1093`）。`--write` を指定しない限り、設定ファイルは変更されません。`--write` 時の実ファイル書き込みは harness の各出力ファイルに対して順に行われます（`terminal/strata_cli/launch/cmd.py:1039-1049`, `terminal/strata_cli/launch/cmd.py:1156-1167`）。

## 適用条件と副作用

- `--context` は接続先アプリの設定生成にだけ適用されます。`strata launch` がサーバーに渡すコンテキスト値を変更しません。実行中 launch から取得する値は `--max-context` の引数を設定ファイルから読み取ったものです（`terminal/strata_cli/launch/cmd.py:693-700`, `terminal/strata_cli/launch/cmd.py:1078-1080`）。
- `--write` を付けなければ出力表示のみです。書き込み時は既存ファイルのバックアップを作る旨を案内し、`--if-unchanged` があれば生成内容と一致するファイルを変更せずに扱います（`terminal/strata_cli/launch/cmd.py:175-179`, `terminal/strata_cli/launch/cmd.py:1025-1049`, `terminal/strata_cli/launch/harness.py:355-380`）。
- harness ごとに context の使い方が異なります。例えば OpenCode / Codex / Cline / Pi / Hermes / OpenClaw のモデル設定や、Claude Code 用環境変数へ出力されます（`terminal/strata_cli/launch/harness.py:120-141`, `terminal/strata_cli/launch/harness.py:144-163`, `terminal/strata_cli/launch/harness.py:191-215`）。利用先アプリ自身による値の上限適用・解釈は Strata ソースからは確認できません。

## 出力とエラー

形式不正や 1024 未満の値は型変換時に拒否され、`argparse.ArgumentTypeError` になります（`terminal/strata_cli/launch/cmd.py:46-50`, `terminal/strata_cli/launch/settings.py:93-99`）。通常の parser エラー出力と終了コードは argparse の経路であり、この調査では CLI を実行して表示文言を確認していません。`--write` で確認が必要なのに stdin が端末でなく `--yes` もない場合は終了コード 2、書き込み失敗時は終了コード 1 となり、失敗したファイルと後続の未書き込みファイルが報告されます（`terminal/strata_cli/launch/cmd.py:1025-1049`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と `--context` の登録、値型、既定値に関する help。
- `terminal/strata_cli/launch/cmd.py:46-50`, `terminal/strata_cli/launch/settings.py:90-100` — 型変換、構文、単位、丸め、下限。
- `terminal/strata_cli/launch/cmd.py:693-725`, `terminal/strata_cli/launch/cmd.py:1074-1080` — 実行中 launch / preset 情報の取得と context の優先順位。
- `terminal/strata_cli/launch/harness.py:339-347` および `terminal/strata_cli/launch/harness.py:144-163`, `terminal/strata_cli/launch/harness.py:191-215` — 値を harness 設定へ適用する処理。
- `terminal/strata_cli/launch/cmd.py:1088-1093`, `terminal/strata_cli/launch/cmd.py:1019-1049` — `--check` と `--write` の経路、確認・失敗処理。
