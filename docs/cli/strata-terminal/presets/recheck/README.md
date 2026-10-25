# `strata presets recheck`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/autotune.py`、`strata_control/tune_session.py`、`strata_control/presets.py` |

## 役割

保存済み tuning preset の設定を実際に engine で計測し、保存時の性能・メモリー値に対して現在も妥当かを確認します。preset の候補設定を再探索する `strata tune auto` とは異なり、保存済み設定を短い計測で確認します。結果は `keep`（維持）、`retune`（再 tuning を推奨）、`inconclusive`（判定不能）のいずれかです。`retune` でも preset は自動で無効化・再作成されません（`strata_control/autotune.py:885-894,918-952`）。

## 使い方

```sh
# profile の設定を使い、指定 preset を再確認
strata presets recheck "Gaming" my-profile

# JSON 出力にし、進捗をファイルにも記録
strata presets recheck "Gaming" my-profile --output json --status-file ./recheck-status.json

# worker の起動先と作業ファイル置き場を明示
strata presets recheck "Gaming" my-profile --serve-dir ./Strata --work-dir ./recheck-work
```

位置引数の順序は `PRESET TARGET` です。`PRESET` は ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致の名前で指定できます。名前の複数一致は拒否されます。`TARGET` は保存済み profile 名または run configuration JSON です（parser: `strata_cli/tune_commands.py:82-90`; 解決: `strata_control/presets.py:218-231`; target 読込: `strata_cli/tune_commands.py:111-114`）。

## 実行時の動作

1. preset と target を読み、target の engine・モデル・ハードウェア identity を得ます。preset の identity と現在値を比較し、GPU、CPU、メモリー、PCIe、モデルファイル、backend などの hard change があれば計測を始めず終了します。soft change の場合は再確認へ進みます（`strata_cli/tune_commands.py:414-425`; `strata_control/presets.py:158-197`）。
2. preset に保存された args と環境設定を target の run configuration に適用し、worker session で `serve.server` を起動します。worker は loopback の一時 port を使い、browser を開かず、計測時に保存済み tuning が二重に適用されないよう `STRATA_NO_PRESET=1` を設定します（`strata_cli/tune_commands.py:427-429,437-438`; `strata_control/autotune.py:897-905`; `strata_control/tune_session.py:443-479`）。
3. 通常は engine を一度起動し、warmup 1回、decode 3回（各200 token）、context に応じた prompt 計測（4096 token、context が6000未満なら1024 token）を実行します。SYCL backend では prompt 計測を省きます。保存値に比べ prompt が5%超遅い場合は、engine をもう一度起動して確認します。engine の tuning epoch が変わっている場合は標準設定でも計測し、保存 preset の decode が標準より遅ければ `retune` の理由になります（`strata_control/autotune.py:885-952`; epoch 判定: `strata_cli/tune_commands.py:417-425`）。
4. 完了後、測定結果と verdict を preset ファイルへ保存します。`keep` の場合は最終確認時刻と identity を更新し、再計測 decode 値が保存値より3%超高ければ測定値も更新します。`retune` と `inconclusive` でも最終結果は記録します（`strata_cli/tune_commands.py:437-447`; `strata_control/presets.py:412-429`）。保存先は既定では profiles directory の隣の `presets/`、`STRATA_PRESET_DIR` 設定時はその directory です（`strata_control/presets.py:43-50`）。

## 主なオプション

| オプション | 値・既定値 | 動作 |
| --- | --- | --- |
| `--output` | `human` または `json`、既定 `human` | 成功結果を人向け文または `schema_version: 1`、`ok: true` を含む JSON で標準出力に出します。JSON モードでは進捗文を標準エラーに出しません（`strata_cli/tune_commands.py:53-55,426,443-447`; `_print`: `95-100`）。 |
| `--gpu-lock` | path。既定は環境変数 `STRATA_TUNE_GPU_LOCK` の値（未設定なら lock なし） | 指定時、各 worker engine の実行中にそのファイルの排他 lock を保持します。競合 lock の待機は最大5400秒です（`strata_cli/tune_commands.py:85,132-136`; `strata_control/tune_session.py:196-210,443-447`）。 |
| `--serve-dir` | path。既定はこの CLI installation の親 directory | `serve.server` worker の作業 directory として使います（`strata_cli/tune_commands.py:126-129,427-429`; `strata_control/tune_session.py:478-484`）。 |
| `--work-dir` | path。省略時は `strata-recheck-` prefix の一時 directory | run config と engine/worker log を置きます。指定 directory は worker session が作成します（`strata_cli/tune_commands.py:427-429`; `strata_control/tune_session.py:420-435,461-468`）。 |
| `--status-file` | path。既定なし | 計測中と完了時の状態 JSON を `.tmp` に書いて置換します。書き込み時の `OSError` は無視されます（`strata_cli/tune_commands.py:432-442,149-157`）。 |
| `--boot-timeout` | float 秒。既定 `900.0` | worker 起動後、health endpoint が ready になるまでの制限時間です。parser は数値型を検査しますが正の範囲の validation はありません（`strata_cli/tune_commands.py:89,427-429`; `strata_control/tune_session.py:423-435,489-507`）。 |
| `--no-quiet-check` | 値なし flag | parser では受理されますが、`_recheck` は値を参照せず、recheck の session にも busy/quiet check を設定していません。このサブコマンドでの効果はソースから確認できません（parser: `strata_cli/tune_commands.py:90`; 使用箇所との対照: 同 `411-438`; quiet-check option の利用は `strata_cli/tune_commands.py:193-196` の `tune auto`）。 |

GPU lock を省略すると、この CLI が協調する他の処理との排他は行いません。計測中に他プロセスが GPU/CPU を使うと判定が揺れたり `inconclusive` になったりする可能性があります（recheck の説明: `strata_control/autotune.py:888-894,936-948`）。

## 出力と失敗

- human 出力では `Still as fast as when it was saved. Kept.`、再 tuning 推奨、判定不能のいずれかを表示します。機械出力では verdict、reason、計測結果、更新後 preset の要約を含めます（`strata_cli/tune_commands.py:443-447`）。
- PC/モデル/backend に hard change がある場合は、再計測せずエラー code `5` を返します（`strata_cli/tune_commands.py:418-420`）。preset 不在・無効などの `PresetError` も code `5` です。`OSError` / `ValueError` は通常 code `2`（例外に `exit_code` があればその値）で処理されます。human error は標準エラー、JSON error は `ok: false` と error object を標準出力に出します（同 `103-108,344-347`）。
- worker を起動できない、ready にならない、engine が計測を通過しない場合は計測結果の verdict が `retune` となり得ます。通常 worker は終了時に terminate され、応答がなければ kill されます（`strata_control/autotune.py:907-923`; `strata_control/tune_session.py:481-520`）。
- preset 結果の保存や target の読み込みなどが失敗した場合は上記例外経路になります。`--status-file` の書き込み失敗だけは無視されます（`strata_cli/tune_commands.py:149-157,344-347,437-447`）。

## 注意点

これは実際に worker/server と engine を起動する計測コマンドです。GPU/CPU を使い、一時 port を開き、作業 directory に run config と log を作成し、完了後は preset の記録を更新します。通常の計測時間は help 文面で「約2分」と案内されていますが、起動時間や再試行、engine 更新後の baseline 計測などで変わります（parser help: `strata_cli/tune_commands.py:82`; 計測と分岐: `strata_control/autotune.py:888-952`）。この調査では CLI help の実行、別 platform の Release artifact、実機での engine 起動は行っていません。

## 関連文書

- [`strata presets` の概要](../README.md) — tuning preset の管理操作と保存領域。
- [CLI オプション索引](../../../README.md) — `strata presets recheck` の option scope。

## 根拠

- `strata_cli/tune_commands.py:49-55,82-90` — `presets recheck` parser、位置引数、共通 `--output` と各 option。
- `strata_cli/tune_commands.py:103-114,126-136,149-157,289-348,411-447` — preset command dispatch、target/lock/status helpers、再計測処理と結果・エラー出力。
- `strata_control/autotune.py:885-955` — request set、判定基準、再試行、engine epoch 比較。
- `strata_control/tune_session.py:420-435,443-520` — worker 構成、engine 起動、health timeout、終了処理。
- `strata_control/presets.py:43-50,158-197,218-231,412-429` — 保存先、staleness 判定、preset 参照解決、再計測結果の記録。
