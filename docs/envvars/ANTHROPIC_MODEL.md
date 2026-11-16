# `ANTHROPIC_MODEL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 自身の起動設定や推論を制御する環境変数ではない。Strata は実行環境から `ANTHROPIC_MODEL` を読み取らず、`strata connect claude-code` が Claude Code 用に表示・生成する環境設定のキーとして値を設定する。通常は `--model`、実行中 launch のモデル名、または既定の `strata` を設定値にする（[strata_cli/launch/harness.py:119-128](../../../../Niko1221/Strata/strata_cli/launch/harness.py)、[strata_cli/launch/cmd.py:993-999](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)）。

同梱 MCP の接続情報は別の例を返し、`ANTHROPIC_MODEL` に固定文字列 `claude-sonnet-4-5` を設定する（[tools/strata_mcp.py:2588-2591](../../../../Niko1221/Strata/tools/strata_mcp.py)）。この値は MCP の例であり、Strata のプロセス環境から読み取った値ではない。

`docs/DETAILS.md` は Claude Code に認識される Claude のモデル名を指定する案内だが、`strata connect claude-code` の設定生成コードは選択された Strata のモデル名をそのまま入れ、Claude のモデル名かを検証しない（`docs/DETAILS.md:678-679`; [strata_cli/launch/harness.py:119-124](../../../../Niko1221/Strata/strata_cli/launch/harness.py)）。したがって同案内は、現在の接続設定生成コードが必ずその値を出すという説明ではない。

## 値と判定

Strata による環境変数値の判定はない。`getenv` や `os.environ` から既存の `ANTHROPIC_MODEL` を読み取るコードは、対象 checkout の Strata 所有ソースで見つからなかった。`claude_env()` は入力の `Target.model` を文字列のまま辞書に格納し、空文字やモデル名の書式を検証しない（[strata_cli/launch/harness.py:119-124](../../../../Niko1221/Strata/strata_cli/launch/harness.py)）。

| 経路 | unset / 空文字 | 設定される値 | 無効値・境界 |
|---|---|---|---|
| `strata connect claude-code` | 既存の `ANTHROPIC_MODEL` は参照しない。`--model` が空または未指定なら、実行中 launch 情報のモデル名、さらにそれがなければ `strata` を使う | 選択された `Target.model` をそのまま設定する | 値の形式・大小文字・空白を検査せず、Strata による無効値判定や fallback はない（[strata_cli/launch/cmd.py:993-999](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)、[strata_cli/launch/harness.py:280-288](../../../../Niko1221/Strata/strata_cli/launch/harness.py)） |
| MCP `strata_connect_info` | 環境変数を参照しない | 例示用の `claude-sonnet-4-5` 固定 | 値の判定なし（[tools/strata_mcp.py:2588-2591](../../../../Niko1221/Strata/tools/strata_mcp.py)） |

## 有効になる条件

- `strata connect claude-code` の設定を表示または JSON 出力すると、`env` オブジェクトに含まれる。`--write` では同じ環境設定を含む `~/.claude/settings.json` を作成・更新する。Strata がシェルや Claude Code のプロセス環境に直接設定する処理ではない（[strata_cli/launch/harness.py:127-128,237-239](../../../../Niko1221/Strata/strata_cli/launch/harness.py)、[strata_cli/launch/cmd.py:1001-1008,1034-1039,1059-1076](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)）。
- `--model` が指定されればそれが優先される。未指定の場合は `launch_info()` が返す実行中 launch のモデル名（なければ `strata`）を使う。`--preset` は接続先情報の選択に使われるが、モデル名は `launch_info()` の戻り値で preset から取得されない（[strata_cli/launch/cmd.py:993-999](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)、[strata_cli/launch/cmd.py:660-682](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)）。
- `--key-env` は API キーの入力元であり、`ANTHROPIC_MODEL` の値や優先順位には関与しない（[strata_cli/launch/cmd.py:163-168,993-997](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)）。
- `--check` の通信は生成済み環境変数を子プロセスへ渡すものではない。Strata の checker が選択済み `Target.model` をリクエストに使って接続を確認する（[strata_cli/launch/cmd.py:1009-1025](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)、[strata_cli/launch/check.py:46-64](../../../../Niko1221/Strata/strata_cli/launch/check.py)）。

## 実行時の詳細

`run_connect()` が CLI 引数・launch 情報からモデル名を選び、`harness.render()` が Claude Code harness の `claude_env()` を呼ぶ。人向け出力では `Environment:` の行、JSON 出力では `env` フィールドに値を含める。`claude_file()` は同じ環境辞書を `~/.claude/settings.json` の `env` として直列化し、`--write` の場合にファイルへ保存する。環境変数のキャッシュやプロセス起動後の再読込はなく、Strata のサーバープロセスや各リクエストからこの名前を読む経路もない（[strata_cli/launch/cmd.py:993-1008,1026-1039,1059-1077](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)、[strata_cli/launch/harness.py:119-128,284-289,296-321](../../../../Niko1221/Strata/strata_cli/launch/harness.py)）。

MCP の `strata_connect_info` は別途、Claude Code 用の例データに固定値を含めて返すだけで、子プロセス起動や設定ファイル書き込みは行わない（[tools/strata_mcp.py:2581-2591](../../../../Niko1221/Strata/tools/strata_mcp.py)）。

## ログと測定値

Strata に `ANTHROPIC_MODEL` の値に応じたログ、警告、終了・失敗経路はない。`--check` の PASS / FAIL は checker が送る prompt と tool call の結果であり、プロセス環境の `ANTHROPIC_MODEL` を評価した結果ではない（[strata_cli/launch/cmd.py:1009-1025](../../../../Niko1221/Strata/strata_cli/launch/cmd.py)）。この変数に関する Strata の測定値は該当なし。

## 根拠

- 候補名の Strata 所有ソース参照は `strata_cli/launch/harness.py:120` と `tools/strata_mcp.py:2590`。いずれも設定・例の生成であり、環境から値を読む参照ではない。
- `strata connect` のモデル入力と優先順位: `strata_cli/launch/cmd.py:157-174,993-999`。
- Claude Code 用設定生成: `strata_cli/launch/harness.py:119-128,237-239,284-289`。
- 表示・書き込み経路: `strata_cli/launch/cmd.py:1001-1008,1026-1039,1059-1077`; `strata_cli/launch/harness.py:296-321`。
- MCP の固定値例: `tools/strata_mcp.py:2581-2591`。
- 接続方法についての文書上の案内: `docs/DETAILS.md:678-679`。実際の設定値生成は上記 Python 実装を根拠とした。
