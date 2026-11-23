# `--backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend family 名。parser は文字列を受け取り、選択肢や型を指定しない |

## 役割

削除コマンド内でエンジン一覧を評価するときに、どの GPU backend のエンジンをこの PC で使用するものとして扱うかを指定します。削除対象は位置引数のバージョンまたはフォルダー名で決まり、`--backend` は対象の絞り込みには使われません。複数 GPU backend がある PC で、削除可否の「使用中」判定を特定 backend に合わせたい場合に関係します。

## 使い方

```sh
strata components remove 0.1.54 --backend amd
```

`amd` は `hip` backend として解釈されます。実際に削除する前に対象を確認する場合は `strata components engines` で一覧を表示できます。

## 値と既定値

- 省略時は `updater.detect_hardware()` による検出結果を使います。検出では `STRATA_ENGINE_BACKEND`、保存済みの選択、OS・GPU 情報が参照されます（`terminal/strata_cli/update_cmd.py:303-321`、`terminal/strata_control/updater.py:316-336`、`terminal/strata_control/engine_component.py:542-565`）。
- 明示時は値を backend 名として正規化し、`cuda` / `hip` / `sycl` / `metal` / `cpu` など `BACKEND_MATRIX` の family 名を指定できます。別名 `nvidia` → `cuda`、`amd` → `hip`、`intel` / `arc` → `sycl` と、`hip-<variant>` 形式も処理されます（`terminal/strata_cli/update_cmd.py:283-300`、`terminal/strata_control/engine_component.py:490-502`、`terminal/strata_control/targets.py:25-30`）。
- parser は `--backend` に `default=None` のみを設定し、`choices` や `type` による入力検証をしません。未登録の値も parser では拒否されず、`requested_hardware()` がその文字列を backend として一覧評価へ渡します（`terminal/strata_cli/update_cmd.py:47-56,88-91,283-300`）。無効な値では使用中エンジンを正しく特定できない可能性があるため、指定する場合は実在する backend family 名を使ってください。
- 同じオプションを複数回指定した場合の独自処理はありません。値を取る `argparse` 引数の通常の解析に従い、後の値が使われます。

## 実行時の動作

`run()` は `--backend` が空でなければ `requested_hardware()` を呼び、明示された backend を含む hardware 情報を一覧処理へ渡します。backend が有効な family なら環境変数 `STRATA_ENGINE_BACKEND` にその family を一時的に設定して GPU 情報を検出し、variant がある場合は `variant_wanted` に保持します。`amd` のような alias は family に変換されます。空文字列は条件分岐で未指定扱いとなり、通常の検出へ進みます（`terminal/strata_cli/update_cmd.py:283-321`）。

削除対象の候補は、位置引数のフォルダー名またはバージョンと `--family` で選択されます。`--backend` は一覧の各項目について、指定 backend で解決されるエンジンを「使用中」と判定する処理、および PC との適合性判定に影響します（`terminal/strata_cli/update_cmd.py:445-466`、`terminal/strata_control/engine_library.py:98-134`）。そのため、指定 backend が実際の選択と異なると、既定で使用されるエンジンの active 判定が変わることがあります。無効な値も parser が拒否せず、選択中エンジンが見つからず active が未設定になる経路があります（`terminal/strata_control/engine_library.py:98-122`）。

削除時はロックを取り直して一覧を再評価し、active エンジンと実行中プロセスが使うエンジンを削除拒否します。`--backend` は実行中プロセスの実体確認を置き換えず、プロセスによる使用は別途チェックされます（`terminal/strata_control/engine_library.py:91-95,139-148,317-342`）。削除対象ディレクトリを一時名へ rename した後に再帰削除し、Qwen 系または shape engine の pin・履歴などの状態を更新します（`terminal/strata_control/engine_library.py:337-366`）。モデルや設定ファイル自体は削除対象ではありません（`terminal/strata_cli/update_cmd.py:88-91,492-497`）。

## 適用条件と副作用

- `--backend` は `strata components remove` の共通引数として登録されています。削除対象のバージョンが複数 family に存在して曖昧な場合は、別の `--family` で指定します（`terminal/strata_cli/update_cmd.py:88-91`、`terminal/strata_control/engine_library.py:184-197`）。
- 現在使用中、または実行中プログラムが使用するエンジンは削除できません。フォルダーの rename に失敗した場合も削除を中止し、元のエンジンを残します。ファイルを使用中で再帰削除できない場合、一時名 `.deleting-*` に残り、次回の削除時に掃除されます（`terminal/strata_control/engine_library.py:139-148,317-366,373-375`）。
- 成功時はエンジンのファイルを削除し、関連する pin / previous / history 状態を更新します。ネットワーク取得処理はこの削除経路にはありません（`terminal/strata_cli/update_cmd.py:445-497`、`terminal/strata_control/engine_library.py:317-366`）。

## 出力とエラー

- 成功時、人間向け出力は削除した engine の version と解放サイズを表示します。`--output json` または `jsonl` では成功結果を JSON で出力します（`terminal/strata_cli/update_cmd.py:303-312,445-497`）。
- 対象なし、同じ version に複数候補がある場合、または active / running の場合は `UpdateError` として失敗します。通常出力では `strata: ...` を stderr に出し、エラーコードを返します。rename に失敗した場合はコード 6 です（`terminal/strata_control/engine_library.py:184-197,317-342`、`terminal/strata_cli/update_cmd.py:307-312,374-378`）。
- 無効な `--backend` 値に対する専用の parser エラーはありません。値の不整合による一覧・active 判定への影響を、入力検証エラーとしては報告しません（`terminal/strata_cli/update_cmd.py:47-56,283-300`、`terminal/strata_control/engine_library.py:98-122`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,88-91` — 共通 parser の `--backend` 宣言と `remove` 固有の引数。
- `terminal/strata_cli/update_cmd.py:283-300,303-321` — 明示値の backend 変換と hardware 情報の構築。
- `terminal/strata_cli/update_cmd.py:445-497` — 候補選択、削除呼び出し、成功出力。
- `terminal/strata_control/engine_library.py:98-134,139-148` — backend に基づく active / 適合性評価と削除可否フラグ。
- `terminal/strata_control/engine_library.py:317-366` — 再検証、削除、状態更新および失敗経路。
- `terminal/strata_control/engine_component.py:490-502,542-565,1136-1231` — backend alias、未指定時の検出、engine 解決規則。
- `terminal/strata_control/targets.py:22-30` — 現行 checkout が扱う backend family と platform の組み合わせ。
- `terminal/strata_control/updater.py:316-336` — hardware 検出で参照する環境変数と GPU 情報。
