# `--backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend 名を取る。parser の `choices` 検査はない |

## 役割

導入済み engine の切替先を調べるとき、GPU backend の自動検出結果を指定値で上書きします。指定した backend に適合しない engine は使用可能な候補として扱われず、`newest` は指定 backend で使用可能な候補から選ばれます。engine のダウンロードや削除は行いません。

## 使い方

```sh
strata components use newest --backend cuda
```

上の例は `cuda` backend の適合判定で最新の導入済み engine を選びます。特定 engine を選ぶときは `newest` の代わりに版番号または folder 名を指定できます。両 engine family に同じ版番号がある場合は `--family qwen` または `--family deepseek` で絞れます。

## 値と既定値

- 省略時は `None` です。`strata components use` の実行時には `updater.detect_hardware()` が環境変数 `STRATA_ENGINE_BACKEND`、保存された backend 選択、OS と GPU 検出などから判定した値を使います（`strata_cli/update_cmd.py:244-252`、`strata_control/updater.py:261-281`、`strata_control/engine_component.py:514-540`）。
- 値を指定すると、前後の空白を除去して小文字化した値で検出結果を上書きします。既知の backend family は `metal`、`cuda`、`hip`、`sycl`、`cpu` です（`strata_control/engine_component.py:465-471`、`strata_control/targets.py:20-29`）。
- `hip-rdna2` のように `hip-` で始まる未知の名前は `hip` と variant 部分に分割されます。ただし `components use` の一覧・適合判定は backend family を参照し、`variant_wanted` を使って候補を絞り込みません。そのため、このコマンドで variant まで指定しても、同じ `hip` family 内の variant 選択を保証しません（`strata_cli/update_cmd.py:247-251`、`strata_control/engine_library.py:91-110,136-161`）。
- `nvidia` / `amd` / `intel` などの別名変換はこの経路では行われません。`split_backend()` は `hip-...` 以外をそのまま返すため、backend family の正規名（例: `cuda`、`hip`、`sycl`）を指定してください（`strata_control/engine_component.py:465-482`）。
- parser に `choices` や専用 validation はありません。未知の値でも parser は受理しますが、一覧の適合判定では backend が一致せず候補が不適合になります（`strata_cli/update_cmd.py:47-56`、`strata_control/engine_library.py:59-80,91-110,136-161`）。

## 実行時の動作

`--backend` は `strata_cli/update_cmd.py` の `_common()` が定義し、`use` parser にも追加されます。CLI から `update_cmd.run()` に渡された後、検出済み hardware の `backend` を指定値で上書きし、`backend_source` を `requested` にします（`strata_cli/update_cmd.py:47-56,84-87,233-255`、`strata_cli/cli.py:2136-2138`）。

その hardware 情報を使って導入済み engine を列挙します。Qwen 側では OS、backend、runtime、GPU arch、driver、ファイル検証などを適合判定に使い、DeepSeek 側では OS と backend を確認します。`newest` は適合する候補のうちの最新を指します（`strata_control/engine_library.py:59-80,91-123,136-162,198-211`）。版番号や folder 名を直接指定した場合も、選ばれた entry が不適合なら切替を中止します（`strata_cli/update_cmd.py:378-383`）。

切替が成功すると、engine が次回以降の起動で使われるよう更新状態を保存します。Qwen engine は pin と履歴・previous 情報を更新し、選んだ engine が自動選択される最新 engine なら pin を外して更新追従に戻します（`strata_control/updater.py:1303-1352`）。DeepSeek engine は選択状態を更新し、保存済み run config の参照先も切り替えます（`strata_control/engine_library.py:265-289`）。engine family の選択は `--family` が別途担います（`strata_cli/update_cmd.py:84-87`）。

## 適用条件と副作用

- `--backend` は自動検出を上書きする明示指定です。backend と OS の組み合わせ、engine の runtime 条件、GPU arch や driver 条件、engine ファイルの状態によっては候補が使用不可と判定されます（`strata_cli/update_cmd.py:247-252`、`strata_control/engine_library.py:59-80`、`strata_control/targets.py:20-53`）。
- backend を変えても engine package は変換されません。指定 backend に適合する導入済み候補がない場合は切替できません。
- 切替は実行中の model が停止するまで待つか、待機が許可されていない場合は拒否されます。実行中 model が使用中の engine はそのままです（`strata_cli/update_cmd.py:378-383,403-418`、`strata_control/engine_library.py:216-239`）。
- 成功時は設定・engine 選択状態・履歴が更新され、engine が変わった場合は保存済み tuning preset が短い再確認の対象としてマークされることがあります。preset は削除されません（`strata_control/updater.py:1313-1352`、`strata_cli/update_cmd.py:386-393`）。

## 出力とエラー

- 成功時は通常、人向け出力で使用中になった engine と更新追従状態を表示します。すでに使用中なら「変更なし」と表示します。`--output json` / `jsonl` または one-shot alias の `--json` では構造化出力になります（`strata_cli/update_cmd.py:358-394`、`strata_cli/cli.py:508-515`）。
- 指定 backend に適合しない engine を指定すると、理由を含むエラーで終了コード `5` になります。指定名に一致する導入済み engine がない場合、または指定が曖昧な場合は `2` です（`strata_cli/update_cmd.py:378-383`、`strata_control/engine_library.py:198-211`）。
- 実行中 engine があり切替できない場合は `7` の busy error になります。通常出力では `strata: ...` を stderr に出し、JSON 系出力では error object を出します（`strata_control/engine_library.py:216-236`、`strata_cli/update_cmd.py:237-242,307-311`）。

## 根拠

- parser と option scope: `strata_cli/update_cmd.py:47-56,84-87`、共通 one-shot option: `strata_cli/cli.py:508-515`
- 値の上書きと hardware 検出: `strata_cli/update_cmd.py:244-255`、`strata_control/updater.py:261-281`、`strata_control/engine_component.py:465-482,514-540`
- engine 候補の適合判定・`newest` 解決: `strata_control/engine_library.py:59-80,91-123,136-162,198-211`
- 切替・状態更新と出力: `strata_cli/update_cmd.py:358-394`、`strata_control/engine_library.py:216-289`、`strata_control/updater.py:1303-1352`

この文書はソースコードの静的確認に基づきます。`--help` の実行、build、GPU 実行、テストは行っていません。
