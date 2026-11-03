# `--output`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか。値を1つ取る |

## 役割

エンジン切替の結果・エラーを人向けまたは機械向けに出力します。切替対象は位置引数 `engine`、同じ版番号のファミリー指定は `--family` で決まります。このオプションは選択や切替動作を変えません（`strata_cli/update_cmd.py:56,84-87,378-394`）。

## 使い方

```sh
strata components use 0.1.54 --output json
```

この例は、導入済みエンジンを指定して切り替え結果を JSON で出力します。`engine` には版番号、エンジンのフォルダー名、または `newest` を指定できます（`strata_cli/update_cmd.py:84-87`、`strata_control/engine_library.py:198-211`）。

## 値と既定値

- 省略時は `human` です（`strata_cli/update_cmd.py:56`）。
- `human` は通常の説明文を標準出力へ表示します。
- `json` は結果を `schema_version: 1` と `ok: true` を含む JSON オブジェクトとして1件出力します。失敗時は `ok: false` と `error.code` / `error.message` を含む JSON オブジェクトです（`strata_cli/update_cmd.py:98-107,237-242,383-394`）。
- `jsonl` はイベントを1行ずつ出し、最後に切替結果の JSON オブジェクトを出力します。待機イベントが発生しなければ、通常は結果の1行だけです（`strata_cli/update_cmd.py:102-105,383-385`、`strata_control/updater.py:311-322`）。
- 選択肢は `argparse` の `choices` で制限されます。別の値や値なしは parser エラーになります。明示的な型変換や空文字の特別扱いは定義されていません（`strata_cli/update_cmd.py:56`）。

## 実行時の動作

`strata_cli/cli.py` は `strata components use` を `update_cmd.run()` へ送り、`--output json` または `jsonl` を機械出力モードとして扱います（`strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:233-242`）。切替前に実行中エンジンを確認し、対象が実行可能なら `engine_library.use_engine()` に渡します。成功時の JSON/JSONL 結果は `schema_version: 1`、`ok: true` とライブラリーが返す情報を含みます（`strata_cli/update_cmd.py:358-394`）。

JSON/JSONL では通常の人向け進捗表示は抑制されます。JSONL のイベント出力関数はイベントを各行で出力し、JSON ではイベントを出しません（`strata_cli/update_cmd.py:98-120`）。切替前にモデルが実行中で、`--wait` が指定されていない場合、機械出力モードでは対話確認をせず待機もしません。切替処理が busy エラー（終了コード7）を返します。`--wait SECONDS` を併用するとその秒数の間待機し、JSONL では待機イベントが出ます（`strata_cli/update_cmd.py:403-418`、`strata_control/engine_library.py:225-239`、`strata_control/updater.py:311-322`）。

`--json` は one-shot コマンドで `--output json` にする alias です。`--json` と `--output jsonl` を同時に指定すると one-shot 専用のエラー経路になります（`strata_cli/cli.py:508-515,2249-2252`）。`--quiet` は機械出力時には出力を抑止しません（同 `:2253-2254`）。

## 適用条件と副作用

このオプション自体は表示形式のみを変更します。エンジン切替は既存の導入済みパッケージに対して行われ、ダウンロードや削除はありません。切替時には選択エンジンのピン、更新状態、履歴などの状態ファイルが更新され、保存済み tuning preset が再確認対象としてマークされる場合があります。最新版を選ぶ場合はピンを外して更新追従状態に戻します（`strata_control/engine_library.py:225-289`、`strata_control/updater.py:1303-1352`）。

## 出力とエラー

- 指定エンジンが見つからない、または版番号が複数ファミリーに一致して `--family` なしでは一意に決まらない場合、エラーコード2です（`strata_control/engine_library.py:198-211`）。
- 選択エンジンがこの PC で実行できない場合、エラーコード5です（`strata_cli/update_cmd.py:378-383`）。ファミリー別検証で署名・完全性検査または DeepSeek の試験起動に失敗した場合も、エラーコード5で拒否されます（`strata_control/engine_library.py:246-260,265-279`）。
- 実行中モデルを待機せずに切り替えようとした場合、何も切り替えずエラーコード7です（`strata_control/engine_library.py:216-222,232-239`）。
- 上記の実行時エラーは `json` / `jsonl` では `ok: false` の JSON、`human` では `strata: ...` を標準エラーへ出します（`strata_cli/update_cmd.py:237-242,307-317`）。無効な `--output` 値など parser 段階のエラーは `argparse` が usage とエラーを標準エラーに出し、終了コード2で終了します（`strata_cli/update_cmd.py:56`、`strata_cli/cli.py:2240-2248`）。

## 根拠

- parser 定義と既定値・選択値: `strata_cli/update_cmd.py:47-56,84-87`
- 出力モード、切替処理、成功・失敗出力: `strata_cli/update_cmd.py:98-120,233-242,358-394`
- Terminal CLI の実行振分けと `--json` / `--quiet` の適用: `strata_cli/cli.py:508-515,2136-2138,2240-2265`
- エンジン選択、busy 条件、切替の状態変更: `strata_control/engine_library.py:198-289`、`strata_control/updater.py:311-322,1303-1352`

調査範囲は上記 commit の checkout 内の Terminal CLI と `strata_control` 実装です。CLI の実行やリリース配布物との照合は行っていません。
