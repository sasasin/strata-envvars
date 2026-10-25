# `--backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | エンジン backend family 名を指定する文字列 |

## 役割

ローカルに保存された直前のエンジン版へ戻す際、どの backend family のエンジンを対象にするかを指定します。指定値は rollback 中の現行エンジン解決と、旧版がこの PC で実際に選択されるかの検証に使われます。rollback は更新 feed を読んだりダウンロードしたりせず、コンポーネント状態の pin を切り替えます（`strata_cli/update_cmd.py:185-196`, `strata_control/updater.py:1033-1078`）。

## 使い方

```sh
strata components rollback --backend cuda
```

この例では `cuda` family を使うエンジン解決を試みます。対象コンポーネントディレクトリを変える場合は `--components-dir PATH` も指定できます。

## 値と既定値

- `strata_cli/update_cmd.py:30-39` の共通 parser が `--backend` を `default=None`、型変換・`choices` 指定なしで登録し、rollback parser にも適用します（同 `:57-59`）。したがって CLI parser 自体は任意の文字列を受理し、値の正当性を事前検証しません。
- 既知の family は `metal`、`cuda`、`hip`、`sycl`、`cpu` です。対応 OS/architecture は `strata_control/targets.py:23-29` に定義され、例えば `cuda` / `hip` は Windows・Linux x86_64、`metal` は macOS arm64、`sycl` は Linux x86_64、`cpu` は列挙された全対象 platform です。
- 省略時は `None` のまま hardware 検出結果を使います。検出では `STRATA_ENGINE_BACKEND` が優先され、それがなければ platform・GPU adapter・既存 probe を確認します（`strata_control/updater.py:249-270`, `strata_control/engine_component.py:439-482`）。エンジン解決時に backend を検出できなければ `cpu` を選びます（`strata_control/engine_component.py:868-874`）。
- 明示した値は小文字化などの正規化を受けず、そのまま backend 名との照合に使われます。空文字列は実行時の `if a.backend` 判定を通らないため、省略時と同様に検出値が使われます（`strata_cli/update_cmd.py:176-180`）。

## 実行時の動作

rollback の実行前に `detect_hardware()` が呼ばれ、その後、空でない `--backend` 値が検出 backend を上書きします（`strata_cli/update_cmd.py:174-184`）。このため明示値は有効な `STRATA_ENGINE_BACKEND` より優先しますが、明示値があっても hardware 検出処理自体は先に実行されます。省略時には環境変数または自動検出が選択に残ります。

`rollback_engine()` は保存済みの previous engine を読み、署名・全ファイルを検証した後、指定 backend を含む hardware 情報で現在のエンジンを解決します。続いて旧版を pin し、同じ backend 条件で通常の engine resolver を呼んで、起動時にもその旧版が選ばれることを確認します（`strata_control/updater.py:1036-1066`, `strata_control/updater.py:506-511`, `strata_control/engine_component.py:859-944`）。従って `--backend` は旧版の folder を直接指定する値ではなく、起動時の選択条件です。対象 backend/platform、runtime、GPU architecture 等に適合する旧版が必要です。

## 適用条件と副作用

- 旧版が現在の `--backend` 条件で選択できない場合、rollback は失敗します。例えば `--backend` を前回更新時と異なる family にすると、旧版がその family でなければ適合確認を通りません。resolver は platform、backend、runtime、CUDA/HIP architecture、driver、署名およびファイル整合性を確認します（`strata_control/engine_component.py:881-918`）。
- parser に `choices` がないため未知の文字列も入力できますが、backend の一致判定で適合エンジンが見つからず、最終的に「previous engine does not fit this PC any more」相当のエラーになります。backend 名は `BACKEND_MATRIX` にある family 名と完全一致させてください（`strata_control/targets.py:23-51`, `strata_control/engine_component.py:868-892`, `strata_control/updater.py:1060-1066`）。
- rollback は serving 中の engine が停止するまで待つか、待機時間が尽きた場合に拒否します。`--wait SECONDS` は共通 parser の値で、指定しない場合は待機せず Busy として扱います（`strata_cli/update_cmd.py:34-35`, `strata_control/updater.py:300-311`, `strata_control/updater.py:1042-1043`）。
- 成功すると状態ファイルの `pinned`、`previous`、`active`、rollback history を更新します。異なる engine identity への切り替え時には tuning preset を短い再確認対象として印付けますが、preset 自体は削除しません（`strata_control/updater.py:1055-1078`, `strata_cli/update_cmd.py:192-195`）。rollback 自体は engine をダウンロードしません（`strata_control/updater.py:1033-1035`）。
- `--feed`、`--force`、`--model-config` も共通 parser により受理されますが、rollback 分岐では参照されません（parser: `strata_cli/update_cmd.py:30-39`, 分岐: 同 `:185-196`）。

## 出力とエラー

- 成功時の human 出力は rollback 元・先、tuning preset の扱い、再試行方法を表示します。`--output json` または `--json` では `ok: true` と rollback 結果を JSON で出力します（`strata_cli/update_cmd.py:189-195`）。
- previous engine が存在しない場合、すでに previous 版が選択中の場合は終了コード 2。旧版の署名・整合性不良、または PC に適合しない場合は終了コード 5。serving 中で待機後も停止しない場合は Busy の終了コード 7 です（`strata_control/updater.py:65-75`, `strata_control/updater.py:1040-1066`, `strata_cli/update_cmd.py:167-172`, `strata_cli/update_cmd.py:225-232`）。JSON/JSONL 出力モードでは失敗を `schema_version`, `ok: false`, `error.code`, `error.message` の JSON として出力します（`strata_cli/update_cmd.py:63-84`, 同 `:167-172`）。
- 旧版の fit 確認で失敗した場合、その場で書いた `pinned` は削除して保存し直し、誤った版を固定した状態を残しません（`strata_control/updater.py:1057-1066`）。

## 根拠

- parser と rollback 専用 parser: `strata_cli/update_cmd.py:30-39`, `strata_cli/update_cmd.py:57-59`
- CLI から rollback 処理への分岐、backend 上書き、出力・例外処理: `strata_cli/update_cmd.py:163-196`, `strata_cli/update_cmd.py:225-234`
- hardware 検出: `strata_control/updater.py:249-270`, `strata_control/engine_component.py:439-482`
- backend/platform 対応と resolver の適合条件: `strata_control/targets.py:23-51`, `strata_control/engine_component.py:859-944`
- rollback の状態変更、pin 検証、副作用: `strata_control/updater.py:1033-1078`

調査は指定 revision のソースを対象とし、CLI `--help` は実行していません。Release 配布物や他 OS 上での実動作はこの調査では確認していません。
