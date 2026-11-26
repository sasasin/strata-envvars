# `--if-needed`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--if-needed` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（`store_true`）。 |

## 役割

現在のモデル・drafting の選択・ローカルファイル状態から DFlash2 drafter が必要と判定された場合だけ取得処理へ進みます。不要なら fetch をスキップして成功扱いで終了します。`fetch` の既定動作は明示的な取得であり、このフラグを付けない場合は必要性判定にかかわらず取得処理を呼びます（`terminal/strata_cli/drafting_cmd.py:34-38,240-272`）。

## 使い方

```sh
strata drafting fetch --config ./run-config.json --if-needed
```

## 値と既定値

- 引数値はありません。parser は `action="store_true"` で登録し、未指定なら偽です。`fetch` にだけ登録され、`plan` では受け付けません（`terminal/strata_cli/drafting_cmd.py:19-38`）。
- 値を後ろに置く形式ではありません。重複指定を特別に拒否する処理はなく、同じ真偽値を指定するだけです（同:34-38）。
- このオプション固有の値検証はありません。`--mode` は別途 `auto`、`mtp`、`dflash2`、`off` のいずれかに制限されます（同:29-35、`terminal/strata_control/drafting.py:37`）。

## 実行時の動作

1. fetch は config などから mode、モデル、data directory、backend・hardware 情報を組み立てます。明示した `--mode` は config の drafting 選択より優先されます。config の読み込みで OS または JSON エラーが起きると、この処理は空 config として続行します（`terminal/strata_cli/drafting_cmd.py:101-137,139-149`）。
2. `needed` は `needs_pack` または `needs_tuned` のどちらかが真かで決まります。前者は選択が DFlash2 で、対応 drafter が未準備の場合、後者は選択が DFlash2 で、該当モデル向け tuned drafter が適用され、そのファイルが未準備の場合に真です（`terminal/strata_cli/drafting_cmd.py:240-244`; `terminal/strata_control/drafting.py:1611-1622`）。選択はモデル、family、mode、backend、GPU 系統などから `choice_of` が決定します（`terminal/strata_control/drafting.py:1521-1545,1527-1545`）。
3. `--if-needed` があり `needed` が偽なら、取得処理は呼ばれません。人向け出力は `Nothing to download.`、JSON/JSONL は `{"schema_version":1,"ok":true,"event":"result","pack":null,"skipped":true}` を出し、終了コード 0 です（`terminal/strata_cli/drafting_cmd.py:267-272`）。
4. 必要と判定されると `drafting_fetch.ensure_for()` を呼びます。該当モデルで tuned drafter が使える場合はそれを試し、取得できない場合は既存 stock pack を使うか stock drafter の取得へ進みます。対象によりネットワーク取得、pack 作成、draft vocabulary の配置や selector の変換が行われます（`terminal/strata_cli/drafting_cmd.py:281-283`; `terminal/strata_control/drafting_fetch.py:349-373,376-443`）。

## 適用条件と副作用

- 必要性は「この選択で drafter を使うか」と「対応ファイルがあるか」に依存します。選択が MTP または off なら `needs_pack` / `needs_tuned` は偽となり、フラグ指定時は取得を省略します（`terminal/strata_control/drafting.py:1611-1622,1527-1545`）。
- Hy4-Flash と Inkling-2-Mini は drafter がモデルファイルに内蔵されている専用分岐があり、`--if-needed` の判定より前に「別途取得不要」として成功終了します（`terminal/strata_cli/drafting_cmd.py:152-208,214-233`）。
- 複数のインストール済み DFlash2 config が見つかると、必要性判定より前にモデル選択エラーとなります（`terminal/strata_cli/drafting_cmd.py:234-239`）。
- 必要と判定されて取得へ進んだ場合は、通信および data directory 内の drafter 関連ファイルの作成・置換・一時ファイル削除が起こり得ます。準備済み stock pack は維持され、tuned 版が適用される条件では tuned 版の取得も試みます（`terminal/strata_control/drafting_fetch.py:349-373,376-443`）。

## 出力とエラー

- 必要性判定による skip は成功（終了コード 0）です。JSON/JSONL では `skipped: true` の result event、人向けでは `Nothing to download.` を出します（`terminal/strata_cli/drafting_cmd.py:267-272`）。
- fetch 対象が複数 config により特定できない場合は、JSON/JSONL に `which_model` エラー、人向けでは stderr に `strata: ...` を出し、終了コード 2 です（同:234-239）。
- 取得時の `DraftingError` または acquisition 拒否は、機械出力で `drafting_failed`、人向けでは stderr にエラーを出し、終了コード 5 です（同:295-301）。取得成功時は JSON/JSONL に pack のパス、人向けに ready メッセージを出し、終了コード 0 です（同:302-306）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting fetch` parser と `--if-needed` の定義、値なし・fetch 限定。
- `terminal/strata_cli/drafting_cmd.py:101-137,139-149` — config 等から必要性判定に使う入力の構成。
- `terminal/strata_cli/drafting_cmd.py:211-272` — 特殊モデル分岐、必要性判定、skip の出力と終了。
- `terminal/strata_cli/drafting_cmd.py:281-306` — 取得呼び出し、進捗、失敗・成功出力。
- `terminal/strata_control/drafting.py:1521-1545,1611-1622` — 選択と stock / tuned drafter の必要性条件。
- `terminal/strata_control/drafting_fetch.py:349-443` — tuned / stock の取得、pack 作成とファイル処理。
