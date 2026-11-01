# `SHOTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`apps/host/scripts` にある手動 QA・画面フロー用 Node.js スクリプトが、ブラウザーのスクリーンショットを保存するディレクトリを指定します。Strata の製品本体（engine、host/server、CLI）が `SHOTS` を読む箇所は見つかりません。この変数を使うのは、以下の8スクリプトを直接起動した場合です。

## 値と判定

各スクリプトは `process.env.SHOTS ?? '<既定値>'` を `node:path` の `resolve()` に渡し、起動時に一度だけ保存先を決めます。`??` なので未設定のときだけ既定値になり、空文字は未設定扱いではありません。空文字の場合は `resolve('')` の結果、実行時のカレントディレクトリが保存先になります。相対パスはカレントディレクトリ基準で絶対パスに解決されます。文字列の trim、形式検査、範囲制限、CLI 引数との優先順位処理はありません。

| スクリプト | `SHOTS` 未設定時の既定値 | 読み取り・ディレクトリ作成 |
|---|---|---|
| `apps/host/scripts/skills-shot.mjs` | `skills-shots` | `:5-6` |
| `apps/host/scripts/agent-flow.mjs` | `agent-shots` | `:29-30` |
| `apps/host/scripts/mode-flow-s4b.mjs` | `mode-shots` | `:9` |
| `apps/host/scripts/agent2-tools-flow.mjs` | `agent2-tools-shots` | `:20-21` |
| `apps/host/scripts/agent-flow-s4b.mjs` | `agent-shots-s4b` | `:22-23` |
| `apps/host/scripts/agent2-flow.mjs` | `agent2-shots` | `:21-22` |
| `apps/host/scripts/task-flow-s4b.mjs` | `task-shots` | `:9` |
| `apps/host/scripts/tools-shots.mjs` | `tools-shots` | `:13-14` |

## 有効になる条件

上記スクリプトを Node.js で実行したときに限り適用されます。スクリプトは Playwright の起動やページ操作に進む前に `mkdirSync(SHOTS, { recursive: true })` を呼びます。したがって、ディレクトリがなければ再帰的に作成し、既に存在していればそのまま使います。親ディレクトリへの書き込み権限がないなど作成に失敗すると、その呼び出しは例外になり、後続処理へ進みません。保存先を変える CLI オプションはこれらのスクリプトにありません。

`approval-flow.mjs` と `qa2-flows.mjs` にも大文字の `SHOTS` というローカル変数がありますが、これは CLI 引数（`process.argv[2]`）または一時ディレクトリから作られ、`process.env.SHOTS` は読みません。環境変数 `SHOTS` の根拠には含めていません（`apps/host/scripts/approval-flow.mjs:18-19`, `apps/host/scripts/qa2-flows.mjs:13-14`）。

## 実行時の詳細

保存先はモジュール評価時に定数へ格納され、そのプロセスの実行中に環境変数を変えても再評価されません。スクリプトはここに `.png` ファイルを書きます。たとえば `skills-shot.mjs` は Skills 画面などを3枚保存し（`apps/host/scripts/skills-shot.mjs:16,22,25`）、`agent-flow.mjs` は名前付き checkpoint 画像と失敗時画像を保存します（`apps/host/scripts/agent-flow.mjs:43,152`）。他のフローも `page.screenshot()` の path に同じ保存先を使います（`apps/host/scripts/mode-flow-s4b.mjs:16,47`, `apps/host/scripts/agent2-tools-flow.mjs:33`, `apps/host/scripts/agent-flow-s4b.mjs:34,156`, `apps/host/scripts/agent2-flow.mjs:35`, `apps/host/scripts/task-flow-s4b.mjs:14,37`, `apps/host/scripts/tools-shots.mjs:47`）。一部のスクリプトは撮影時に `shot <ファイル名>.png` を標準出力へ表示します。`SHOTS` 自体の値を出すログや、環境変数の無効値に対する専用警告はありません。

これらのスクリプトは `STRATA_URL` など別の環境変数も使いますが、それらは接続先・モデル等に関する設定であり、`SHOTS` の値を上書きしません。Playwright による撮影機能はスクリプト内で呼び出されますが、その依存ライブラリの内部動作は本調査の対象外です。

## 根拠

`SHOTS` の環境読み取り全8箇所: `apps/host/scripts/skills-shot.mjs:5-6`, `agent-flow.mjs:27-30`, `mode-flow-s4b.mjs:8-9`, `agent2-tools-flow.mjs:18-21`, `agent-flow-s4b.mjs:20-23`, `agent2-flow.mjs:19-22`, `task-flow-s4b.mjs:8-9`, `tools-shots.mjs:11-14`。いずれも `process.env.SHOTS` を直接読むため、動的な env helper の転送・呼び出し経路はありません。候補一覧には `SHOTS` の記載があります（`docs/envvars/000_envvers.md:555`）が、確認できた用途はこの QA/画面撮影スクリプト群の出力先指定に限られます。
