# `strata drafting fetch --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`--output` は `strata drafting fetch` の結果を人向け表示または機械処理向け JSON 系表示に切り替えます。ファイルの出力先を指定するオプションではありません。

```sh
strata drafting fetch --output json
strata drafting fetch --output jsonl
```

## 値と既定値

値は `human`、`json`、`jsonl` のいずれかで、省略時は `human` です。parser はこの3値以外を受理しません（`strata_cli/drafting_cmd.py:17-29`）。不正な値は argparse の引数エラーとなり、コマンド本体の fetch 処理には入りません。

## 実行時の動作

- `human` は進捗を標準出力に `step done of total GB` の形で上書き表示し、完了時に pack のパスを表示します（`strata_cli/drafting_cmd.py:81-85, 95-99`）。
- `json` と `jsonl` はどちらも機械向けモードです。完了時には `schema_version: 1`、`ok: true`、`event: "result"`、`pack` を含む JSON オブジェクトを標準出力に1行出します（`strata_cli/drafting_cmd.py:59, 95-96`）。
- `json` は進捗コールバックの表示を抑えます。`jsonl` はダウンロード・pack 処理の進捗を `event: "progress"`、`step`、`done`、`total` を含む JSON Lines として標準出力へ逐次出力し、最後に結果行を出します（`strata_cli/drafting_cmd.py:81-85, 95-96`）。

このオプションは表示形式だけを選び、`ensure` を呼ぶかどうかや取得内容を変えません。`--if-needed` を併用した場合だけ、`needed` が偽なら取得を省略して結果を出します。この分岐では機械向け出力は `skipped: true` の JSON 1行、human は `Nothing to download.` です（`strata_cli/drafting_cmd.py:60-79`）。現 revision では `ENGINE_SERVES_DFLASH2 = False` のため `needs_pack` は常に偽になり、`--if-needed` 付き fetch はスキップされます（`strata_control/drafting.py:141-146, 179-183`）。`--if-needed` なしの明示的な fetch は `ensure` に進みます。

## 適用条件と副作用

`json` / `jsonl` 自体にファイル・ネットワークの副作用はありません。fetch が実際に未取得 pack を準備する場合は、`--data-dir` 等で決まるデータフォルダーの `dflash2/` 以下に pinned ファイルを取得し、検査後に engine 用 pack を作成します。一時ソースファイルは pack 後に削除されます。既存の pack が有効なら再利用されます（`strata_control/drafting_fetch.py:54-67, 70-101`）。取得には明示コマンド `strata drafting fetch` が必要で、取得禁止状態では `AcquisitionRefused` になります（`strata_control/drafting_fetch.py:60-64`; `strata_control/acquisition.py:70-73`）。

## 出力とエラー

取得または pack 作成時に捕捉される `DraftingError` / `AcquisitionRefused` は終了コード `5` です。機械向けモードは標準出力へ `ok: false` と `error.code: "drafting_failed"` を含む JSON 1行、human は標準エラーへ `strata: <理由>` を出します（`strata_cli/drafting_cmd.py:87-94`）。取得途中の転送失敗や checksum 不一致、pack 準備失敗は `DraftingError` に変換されます（`strata_control/drafting_fetch.py:74-94`）。

## 根拠

- `strata_cli/drafting_cmd.py:17-29` — `fetch` parser と許容値・既定値。
- `strata_cli/drafting_cmd.py:57-99` — 機械向け判定、進捗・成功・失敗出力、および `--if-needed` 分岐。
- `strata_cli/cli.py:2144-2146` — Terminal CLI から drafting command への dispatch。
- `strata_control/drafting_fetch.py:54-101` — pack の再利用、取得・検査・変換・後片付け。
- `strata_control/drafting.py:141-146, 179-183` — 現 revision の serve 対応状態と `needed` 判定。
- `strata_control/acquisition.py:70-73` — 取得禁止時の拒否。

調査範囲は指定 checkout のソースです。CLI help、Release 配布物、他 platform の実行差はこの文書では別途確認していません。

関連: [CLI オプション索引](../../../README.md)、[CLI 調査手順](../../../001_investigation.md)
