# `strata connect --model`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。調査時の `git status --short --branch` は `## main...origin/main`。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <app>` |
| オプション | `--model` |
| 別名 | なし |
| 値 | `NAME`。モデル名を表す文字列。parser に型変換・選択肢・形式検証はない |

## 役割

接続先アプリに表示・生成するモデル名を指定する。`strata launch --model` のように Strata が起動するモデルを選ぶものではない。`connect` が各アプリ用設定に入れる名前と、`--check` がサーバーへ送る API リクエストの `model` 値を上書きする（`strata_cli/launch/cmd.py:165`, `:945-950`, `strata_cli/launch/harness.py:92-100`, `strata_cli/launch/check.py:50-68`).

## 使い方

```sh
strata connect opencode --model my-model
strata connect codex --model my-model --check
```

`connect` の対象アプリ名（例: `opencode`, `codex`）を指定した場合に適用される。アプリ名を省略して `strata connect --model my-model` とすると、アプリ一覧を出す早期経路に入り、モデル値は使われない（`strata_cli/launch/cmd.py:926-937`, `:938-951`）。

## 値と既定値

`--model` は `metavar="NAME"` の通常の文字列引数で、parser に `type`、`choices`、専用 validator や既定値の明示はない。未指定値は `None` となり、実行時に `a.model or info.get("model") or "strata"` で補完される。したがって、空文字列を明示した場合も同じ補完経路に入り、空のモデル名にはならない。非空文字列については Strata 側で名前の妥当性を検証しない（`strata_cli/launch/cmd.py:165`, `:945-950`; `strata_cli/launch/harness.py:272-279`）。

## 実行時の動作

指定した非空の `--model` が最優先される。省略時は `launch_info(a.preset)` のモデル値を使い、それもなければ `strata` を使う。`launch_info` は実行中 launch の設定 JSON にある `model_name` を読み、値がなければ `strata` を返す。`--preset NAME` は `launch_info` が参照する launch/preset を選ぶが、保存 preset のモデル名そのものは返却値の `model` に使われず、対象 launch の設定 `model_name` がなければ `strata` になる（`strata_cli/launch/cmd.py:636-658`, `:945-950`）。

選ばれた値は `harness.target()` の `Target.model` に入り、各アプリ向け設定の model/provider 項目や環境変数として表示される。たとえば OpenCode の `model` / `small_model`、Codex の `model`、Claude Code のモデル環境変数に使われる（`strata_cli/launch/harness.py:92-116`, `:123-160`, `:272-280`）。

`--check` を付けると、アプリに対応する API 形式を使い、prompt と tool-call の 2 リクエストの JSON body の `model` に同じ値を設定してサーバーへ送る。これは設定内容だけでなく、指定モデルで応答・tool call が通るかも確認する（`strata_cli/launch/cmd.py:1002-1010`, `strata_cli/launch/check.py:50-68`, `:111-143`）。

## 適用条件と副作用

- 有効なのは `strata connect <app>` のアプリ別設定生成経路。`connect` 単独の一覧表示には影響しない（`strata_cli/launch/cmd.py:926-937`）。
- `--model` 単独では設定をファイルへ書かず、設定内容を標準出力（`--output json` なら JSON）に表示する。`--write` を併用すると生成設定を対象アプリのファイルへ書く。既存ファイルはバックアップされ、JSON merge 対象では既存キーを保持しつつ新しい値を優先する（`strata_cli/launch/cmd.py:953-960`, `:981-1001`, `:1011-1028`; `strata_cli/launch/harness.py:288-311`）。
- `--write` は既定で確認を求める。非対話端末では `--yes` がなければ stderr に案内を出して終了コード 2、確認で `y` / `yes` 以外を選ぶか EOF なら書き込みを中止する（`strata_cli/launch/cmd.py:1011-1028`）。
- `--check` はサーバーへ実リクエストを送る。失敗した check は通常出力で終了コード 1、`--output json` でも payload の `ok: false` と `error.code: 1` を返す。指定モデルの受け入れ可否はサーバー側の応答に依存し、CLI parser は事前判定しない（`strata_cli/launch/cmd.py:961-977`; `strata_cli/launch/check.py:111-143`）。

## 出力とエラー

対象アプリ名が不正なときは stderr に利用可能なアプリ一覧（近い名前があれば候補も）を出し、終了コード 2 となる。モデル名自体について専用の CLI validation error はない（`strata_cli/launch/cmd.py:938-944`; `strata_cli/cli.py:2240-2247`）。モデル名を含む設定は表示され、`--write` 時はその設定値がファイルに保存される。`--check` 時のモデル名による拒否・サーバーエラーは check の失敗として報告され、終了コード 1 になる（`strata_cli/launch/cmd.py:978-1010`）。

## 根拠

- parser 定義と option scope: `strata_cli/launch/cmd.py:157-173`
- launch/preset 由来の既定値、および `--model` 優先適用: `strata_cli/launch/cmd.py:636-658`, `:945-950`
- アプリ設定へのモデル名の埋め込み: `strata_cli/launch/harness.py:92-116`, `:123-160`, `:272-280`
- `--check` のリクエスト body と結果: `strata_cli/launch/check.py:50-68`, `:111-143`; 呼び出しと終了コード: `strata_cli/launch/cmd.py:961-977`
- 表示・書き込み・確認・バックアップ: `strata_cli/launch/cmd.py:978-1028`, `strata_cli/launch/harness.py:288-311`
- CLI option の不明引数処理: `strata_cli/cli.py:2240-2247`
