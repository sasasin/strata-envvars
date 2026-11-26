# `strata drafting fetch --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか。既定値は `human` |

## 役割

取得処理の結果を人向け表示または機械可読形式で標準出力へ出します。`jsonl` は進捗イベントも出すため、アプリなどが取得中の状態を逐次読む用途に使われます。ファイルの出力先を指定するオプションではありません。

## 使い方

```sh
# 通常の人向け表示（既定）。必要な drafter を取得・検証・準備する
strata drafting fetch

# 結果を JSON で受け取る
strata drafting fetch --config ./run.json --output json

# 進捗イベントと最終結果を JSON Lines で受け取る
strata drafting fetch --config ./run.json --if-needed --output jsonl
```

`fetch` は必要な drafter が未配置ならネットワーク取得や pack 作成を行います。`--if-needed` を指定すると、選択内容が drafter を使わない、または既にファイルがある場合は取得せず終了します。

## 値と既定値

- parser は `choices=("human", "json", "jsonl")`、`default="human"` として登録しています。値の省略時は `human` です。
- 別の値や空文字列は argparse に拒否され、usage とエラーが標準エラーに出て終了コード `2` になります。値の複数回指定は parser 側で禁止されておらず、argparse の通常の扱いでは最後に指定した値が使われます。
- `--output` は `fetch` の parser に値を取る引数として定義されています。`plan` 側にも同じ選択肢がありますが、その文書は索引上の別項目です。

## 実行時の動作

- `human` は既定の人向け形式です。進捗を `Downloading…` 等の文言で表示し、成功時は準備できた pack のパスを表示します。
- `json` と `jsonl` はどちらも機械可読モードです。通常の進捗 callback では `jsonl` だけが `{"event":"progress", ...}` を1イベント1行で出し、`json` は進捗行を出しません。処理終了時は両形式とも結果を JSON オブジェクトで出力します。成功・スキップには `schema_version: 1` と `ok: true`、取得失敗には `ok: false` とエラー情報が含まれます。
- `--if-needed` により取得を省略したときも、機械可読モードでは `event: "result"`、`skipped: true` の JSON を出します。人向けモードでは `Nothing to download.` と表示します。
- `--output` の値は出力形式だけを選び、取得対象や保存場所は変えません。対象モデル・設定・データディレクトリなどは他の引数や検出結果で決まり、`fetch` は選ばれた stock または tuned drafter の取得・検証・準備を行います。

## 適用条件と副作用

出力は標準出力へ行われ、ファイルへの出力や上書きは `--output` 自体では発生しません。ただし `fetch` の処理には別の副作用があります。drafter が未配置ならネットワークアクセスを行い、モデルデータ領域へ一時ファイルや pack を作成します。stock drafter は取得元ファイルを検証して pack 化後に一時取得ファイルを削除し、必要な selector や語彙ファイルも準備します。既に有効な pack がある場合は再取得せず、その pack を返します。

モデル選択が必要なインストール済みモデルが複数あるのに対象が指定されていない場合、処理は取得前に終了します。Hy4-Flash または Inkling-2-Mini と判定された場合は別 drafter がモデル内蔵として扱われ、外部 drafter を取得せずスキップ結果になります。

## 出力とエラー

- 人向け成功時は `The DFlash2 drafter is ready: <path>`、進捗は同じ標準出力へ表示されます。
- 機械可読成功時は JSON の結果イベントを標準出力へ出します。`jsonl` では取得中に進捗イベントが先行します。
- 取得・検証など捕捉された失敗は、`human` では `strata: ...` を標準エラーへ出して終了コード `5`、機械可読モードでは `ok: false` の JSON を標準出力へ出して終了コード `5` になります。`jsonl` でもエラー時の最終行は JSON オブジェクトです。
- 対象モデルが複数で選択できない場合は終了コード `2` です。人向けでは標準エラー、機械可読ではエラー JSON が標準出力へ出ます。
- `--throttle` によるフィード照会の抑制などで取得結果が `None` となるケースは、`--throttle` 指定時にはスキップ成功として扱われます。通常 fetch でネットワーク到達不能等となるケースは取得失敗になります。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting fetch` の登録、`--output` の選択肢・既定値。`--output` は `plan` と `fetch` の各 parser に共通登録されます。
- `terminal/strata_cli/drafting_cmd.py:211-239` — 機械可読モードの判定、内蔵 drafter のスキップ、複数モデル未選択時のエラーと終了コード。
- `terminal/strata_cli/drafting_cmd.py:267-305` — `--if-needed` のスキップ出力、JSONL 進捗、取得呼び出し、失敗・成功の出力形式と終了コード。
- `terminal/strata_control/drafting_fetch.py:349-373` — モデル条件に応じた tuned / stock drafter の選択と fallback。
- `terminal/strata_control/drafting_fetch.py:376-442` — pack の再利用、ダウンロード、pack 作成、検証、関連ファイルの準備と取得元ファイルの削除。
- `docs/cli/README.md:349-361` — `strata drafting fetch` の階層と `--output` の索引リンク。
