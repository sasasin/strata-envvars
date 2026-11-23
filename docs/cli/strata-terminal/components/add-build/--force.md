# `strata components add-build --force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `false`、指定時は `true`。 |

## 役割

このコマンドでは `--force` は共通 parser によって受理されますが、`add-build` の処理には使われません。指定しても既存のローカル engine を上書きせず、同じローカル engine がすでに登録済みなら通常どおり拒否されます。parser の help 文言は「テスト起動に失敗した、または rollback された version を再試行する」と説明していますが、これは他の更新経路向けの説明であり、`add-build` の動作を表していません（`terminal/strata_cli/update_cmd.py:47-56,95-99,339-340,425-434`、`terminal/strata_control/local_engine.py:153-157`）。

## 使い方

```sh
strata components add-build ./build --force
```

`--force` は値を取らないため、後ろに値を付けません。指定しない場合と同じ処理になります。位置引数 `folder` はビルド済み engine のフォルダーです（`terminal/strata_cli/update_cmd.py:95-99`）。

## 値と既定値

`--force` は `_common()` が `action="store_true"` で登録するフラグで、既定値は `false` です。別名や値の変換・範囲検証はありません。繰り返し指定しても真偽値が `true` になるだけで、`add-build` の効果は変わりません（`terminal/strata_cli/update_cmd.py:47-56`）。

## 実行時の動作

parser の結果は `updater.Context.force` に入ります。しかし `add-build` 分岐は `_add_build_command()` を呼び、そこでは `ctx.force` を参照せず、`local_engine.add_build()` に `force` を渡しません。その後の `engine_library.use_engine()` にも `force` 引数はありません。したがってこのコマンドでは `--force` は受理されるだけで、ビルドの検査、登録、engine の切り替えを強制・迂回しません（`terminal/strata_cli/update_cmd.py:303-321,337-340,425-435`、`terminal/strata_control/local_engine.py:127-130`、`terminal/strata_control/engine_library.py:211-228`）。

`--wait` は別の共通オプションで、engine が稼働中の場合の待機を制御します。これは `--force` の効果ではありません。`add-build` は `_maybe_wait()` の後に登録処理を行い、登録済みと同じ名前のローカル engine があれば、`--force` の有無にかかわらず終了コード 2 で拒否します（`terminal/strata_cli/update_cmd.py:51-53,428-434,500-515`、`terminal/strata_control/local_engine.py:153-157`）。

## 適用条件と副作用

`--force` 自体による副作用はありません。オプションを付けても、コマンド本体は通常どおり、ビルドをローカル・unsigned engine として登録し、選択中の engine に切り替えます。重複登録の上書きはしません（`terminal/strata_cli/update_cmd.py:425-441`、`terminal/strata_control/local_engine.py:127-130,153-176`）。

## 出力とエラー

`--force` を指定したかどうかで成功出力やエラー経路は変わりません。人向け出力では登録した engine が現在使用中であることと unsigned であることを表示し、`--output json` または `jsonl` では成功結果を JSON で出力します（`terminal/strata_cli/update_cmd.py:305-312,434-442`）。

`add-build` の入力や環境に問題がある場合、たとえばフォルダーでない、engine 実行ファイルがない、対応 backend でない、または同じローカル engine がすでにある場合は登録を拒否します。`AddBuildError` は `UpdateError` に変換され、人向け出力では stderr、機械向け出力では JSON のエラーとして返されます。`--force` でこれらの失敗を回避することはできません（`terminal/strata_control/local_engine.py:35-45,131-157`、`terminal/strata_cli/update_cmd.py:307-312,430-433,374-378`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--force` の登録、型、既定値と help 文言。
- `terminal/strata_cli/update_cmd.py:95-99` — `add-build` が位置引数 `folder` と共通 options を登録する箇所。
- `terminal/strata_cli/update_cmd.py:303-321,337-340,425-442` — `force` を context に格納する一方、`add-build` の handler がそれを使わず登録・切り替えを行う経路。
- `terminal/strata_control/local_engine.py:127-130,153-176` — `add_build()` が `force` を受け取らず、重複時に拒否し、ローカル engine のファイルと manifest を作る処理。
- `terminal/strata_control/engine_library.py:211-228` — engine 切り替え関数の引数と、稼働中 engine の待機・拒否処理。
- `terminal/strata_cli/update_cmd.py:307-312,374-378,500-515` — エラー出力と `--wait` の確認経路。
