# `strata connect --model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--model` |
| 別名 | なし |
| 値 | `NAME` を1つ取る。parser に選択肢・形式・モデル存在確認の指定はない |

## 役割

接続先アプリ用の設定に記載するモデル名を指定する。指定値は `--preset` で読み込んだ preset や稼働中の `strata launch` から得たモデル名より優先される。アプリの設定ファイルや環境変数のモデル項目に埋め込まれ、`--check` を付けた場合は検証リクエストのモデル名にも使われる。

## 使い方

```sh
strata connect opencode --model my-server-model
```

この例は OpenCode 向け設定を表示する。`--write` を付けないため、設定ファイルは書き換えない。

## 値と既定値

- `NAME` は parser 上で任意の文字列として受け取られ、空でないことやサーバーに存在することは事前検証されない。引数を省略した場合、稼働中 launch の設定からモデル名を得られればそれを使い、得られなければ `strata` を使う。
- 値を空文字列として渡した場合も、実行時の `or` による選択で明示値とは扱われず、launch 情報または `strata` にフォールバックする。
- 同じオプションを複数回指定した場合の個別仕様は定義されていない。Python `argparse` の通常の単一値引数として処理される。

## 実行時の動作

`strata connect <harness>` では `launch_info(--preset)` のモデル名を候補にし、明示した `--model` があればそれを採用する。launch 情報がない場合は `strata` が既定値となる。選択したモデル名はアプリごとの設定生成関数へ渡され、OpenCode / Codex / Cline / Claude Code / oh-my-pi / pi / Hermes / OpenClaw 向けのモデル識別子などに反映される。

`--check` を指定すると、同じモデル名を prompt と tool-call の検証リクエストに含めて接続先サーバーへ送る。モデル名が不正またはサーバーに存在しない場合の拒否は、CLI の事前 validation ではなく、このリクエストに対するサーバー応答で判明する。

`--harness`（位置引数）を省略すると、接続可能なアプリ一覧を表示する早期分岐に入るため、`--model` は設定生成に使われない。モデル名の設定だけではファイルは書かれず、書き込みには `--write` が別途必要。

## 適用条件と副作用

- `--preset NAME` を指定しても、同時に与えた `--model` がモデル名の優先値となる。preset/稼働中 launch からの URL やキーの解決は別途行われる。
- `--check` は prompt と tool call の2つを実際にサーバーへ送るため、推論リクエストが発生する。失敗時は通常設定ファイルへの書き込みに進まず、終了コード `1` となる。
- `--write` を併用すると、生成済み設定ファイルを書き込む処理へ進む。書き込みの確認・バックアップ等は `--write` 側の動作であり、`--model` 自体はファイル操作をしない。

## 出力とエラー

- parser は値を取れない場合や未知のオプションを通常の argparse エラーとして扱う。モデル名の形式・存在に関する parser エラーはない。
- `--check` ではモデル名を含む各リクエストの結果が表示される。失敗した検査があれば人向け出力は終了コード `1`、JSON 出力では `ok: false` と失敗情報を返す。無効なモデル名に対する具体的な応答文や HTTP status はサーバー実装・応答に依存し、このオプション側では固定されない。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と `--model NAME` の登録。別名や choices / validator は登録されていない。
- `terminal/strata_cli/cli.py:2235-2237` — `connect` を `run_connect` に渡す dispatch。
- `terminal/strata_cli/launch/cmd.py:703-725` — preset または稼働中 launch の情報を解決し、モデルの取得に失敗した際 `strata` を設定。
- `terminal/strata_cli/launch/cmd.py:1052-1080` — harness 未指定時の一覧分岐、明示モデルと launch 情報の優先順位、ターゲット生成。
- `terminal/strata_cli/launch/harness.py:119-163,191-217` — 選択モデルを各アプリ設定ファイル・環境変数のモデル欄へ反映。
- `terminal/strata_cli/launch/cmd.py:1087-1118,1147-1155` — `--check` の実行、失敗時の書き込み抑止、終了コード。
- `terminal/strata_cli/launch/check.py:50-68,111-143` — 検査リクエストの body にモデル名を含め、prompt / tool-call の成否を確認。
- 利用者向け補助資料 `docs/TERMINAL_LAUNCH.md:175-200` は running launch のモデル名を既定値と説明する。ソースでは launch 情報がない場合に `strata` へフォールバックする。
