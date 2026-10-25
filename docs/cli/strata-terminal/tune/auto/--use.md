# `--use`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--use` |
| 別名 | なし |
| 値 | `chat` または `coding` |

## 役割

自動チューニングで各設定の性能を比べるとき、どのワークロード指標を主に評価するかを選びます。エンジンやモデルの設定値そのものを直接指定するオプションではありません。

## 使い方

```sh
strata tune auto "My profile" --use coding
```

`target` には保存済み profile 名またはチューニング対象の run configuration を指定します。`--use` を省略すると `chat` です。

## 値と既定値

- `chat`: 生成（decode）の tokens/s で比較します。
- `coding`: 生成速度と長い prompt の処理速度を合わせた指標で比較します。両方の値が得られる場合、幾何平均 `sqrt(decode_tok_s × prompt_tok_s)` を使います。長い prompt の測定値がない場合は通常の prompt 処理速度にフォールバックし、それもなければ decode 速度が評価値になります。
- 既定値は `chat` です。値は `argparse` の `choices` で制限され、別名や複数回指定時の独自処理はありません（同じ引数の後の値が argparse により採用されます）。

## 実行時の動作

parser の値は `autotune.Options.use` に渡され、基準設定・候補設定の評価に使われます。`chat` は decode 速度、`coding` は上記の複合指標を評価し、測定結果のノイズ確認、候補の勝敗判定、確認試行にも同じ指標を用います（`strata_control/autotune.py:139-153,397-407,521-541`）。

`coding` かつ `--mode thorough` で、対象 context が 64K 未満の場合は最大 `min(28000, 0.8 × context)` tokens の長い prompt を測定要求に加えます。context が 64K 以上なら `--use` の値にかかわらず長い prompt を要求します。短い context の quick mode では専用の長い prompt を追加しないため、`coding` の評価は得られた通常 prompt 指標を使います（`strata_control/autotune.py:369-377`）。prompt 処理だけを対象とする個別 knob は、`--use` にかかわらず prompt 指標で評価されます（`strata_control/autotune.py:430-433,537-545`）。

結果を保存する場合、`use` は preset の `choices` に記録されます（`strata_cli/tune_commands.py:236-248`, `strata_control/presets.py:89-117`）。ただし slot の識別に使うのはモデル digest、context、KV 形式、vision、goal で、`use` は含まれません（`strata_control/presets.py:128-131`）。したがって、これらの選択が同じなら `--use coding` で得た preset も通常起動時の検索対象になり得ます。通常起動の検索は `presets.overlay(...)` の既定 `use="chat"` で行われますが、`use` が slot key に含まれないためです（`strata_control/presets.py:441-455`, `strata_cli/launch/runner.py:1425`）。

このオプションはチューニングの測定・比較に作用します。チューナーは基準設定および候補をエンジンで実行して測定するため、`--use` はその実行自体を省略するものではありません（`strata_control/autotune.py:397-400,475-500`）。

## 適用条件と副作用

- `coding` の長い prompt 測定は、上記の mode と context 条件に依存します。常に長文 prompt の速度を測定するとは限りません。
- `--no-save` がなければ、改善が確認された場合、または現設定が最速と確認された場合に preset を保存します。その preset の選択情報に `use` が記録されます。`--no-save` を指定した場合は preset を作成しません（`strata_cli/tune_commands.py:236-248`）。
- 測定はエンジン実行を伴います。候補が失敗・スキップされることがあり、ベース設定を測定できない場合は `base_failed` となります（`strata_control/autotune.py:397-407,475-490`）。

## 出力とエラー

値が `chat` / `coding` 以外の場合、parser の choices validation により受理されず、argparse の usage/error 経路になります（`strata_cli/tune_commands.py:20-32`; parser の登録は `strata_cli/cli.py:486`）。測定開始前の profile 読込・設定 validation や engine 不在など `_fail` を通る失敗は、人向けなら stderr に `strata: ...` を出し、`--output json` なら `ok: false` の JSON を stdout に出して対応するコードを返します（`strata_cli/tune_commands.py:103-108,178-196`）。測定後の `base_failed` / `inconclusive` 等は別経路で、結果 JSON の `ok: true` と `result.code` / 終了コードに結果を記録します（`strata_cli/tune_commands.py:230-261`, `strata_control/autotune.py:355-367,397-407`）。

## 根拠

- `strata_cli/tune_commands.py:20-32` — `strata tune auto` parser、許容値と既定値。
- `strata_cli/tune_commands.py:174-197,230-261` — option の伝達、preset 選択情報への記録、出力と終了コード。
- `strata_control/autotune.py:50-63,139-153` — `Options.use` と評価指標。
- `strata_control/autotune.py:369-377,397-407,430-433,475-505,521-545` — 測定条件、基準・候補評価、prompt-only knob の評価。
- `strata_control/presets.py:89-117,128-131,441-455` — `use` を含む preset choices と、`use` を含めない slot 検索。
- `strata_cli/launch/runner.py:1425` — 通常起動からの preset 検索呼び出し。
- `strata_cli/cli.py:486` — `tune auto` parser の登録。

調査範囲は記載した checkout のソースです。同一 revision の既存 CLI `--help` や Release 配布物は照合していません。
