# `strata components rollback --force`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `false`、指定時は `true`。 |

## 役割

`--force` は共通 parser で受理されるフラグです。parser の説明は、テスト起動に失敗した版または rollback された版を再試行することです。ただし `strata components rollback` の実行経路ではこの値を参照しません。このコマンドに付けても rollback の対象選択や検証を変えず、再試行の強制にもなりません。再試行の制御は `strata update --force` の更新経路で行われます。

## 使い方

```sh
# 以前の切り替えで記録されたエンジンへ戻す。--force はこの経路の動作を変えない。
strata components rollback --force
```

このコマンド自体はエンジンの選択状態を切り替えます。`--force` はその変更を強制したり、確認を省略したりする指定ではありません。

## 値と既定値

`argparse` の `store_true` フラグで、既定値は `false` です。引数値は定義されておらず、別名もありません。rollback 用 parser は `_common()` を通じてこのフラグを登録します。重複して指定しても値は真のままで、rollback の結果は変わりません（`strata_cli/update_cmd.py:47-57,80-82`）。

## 実行時の動作

CLI は受け取った値を `updater.Context.force` に渡してから rollback 分岐へ進みますが、その分岐は `updater.rollback_engine(ctx)` を呼び、`force` を読みません（`strata_cli/update_cmd.py:310-321`、`strata_control/updater.py:1450-1472`）。rollback は保存状態の `engine.previous` を取得し、そのパッケージの manifest と完全性を検証してから切り替えます。対象が存在しない場合や検証に通らない場合も、`--force` による迂回はありません（`strata_control/updater.py:1453-1472`）。

`--force` が効果を持つのは更新側です。新しい版が過去に失敗した、またはスキップ扱いになった場合の選択を許可し、通常の「再試行しない」判定を変えます（`strata_control/updater.py:698-705,1193-1204,1680-1688`）。

## 適用条件と副作用

このフラグに固有の副作用はありません。rollback が成功すると、以前のエンジンを起動対象として pin し、active / previous / skipped 状態と履歴を更新します。必要な場合は、そのエンジンで測定された保存済み tuning preset に再確認マークを付けますが、preset 自体は削除しません。パッケージはローカルで検証・切り替えられ、rollback 処理はダウンロードしません（`strata_control/updater.py:1398-1447,1450-1472`、`strata_control/preset_marks.py:72-96`）。

エンジンが稼働中の場合、`--wait` がなければ対話端末では待機するか質問し、非対話・機械出力では待たずに失敗します。`--wait` を指定すると、その秒数まで待ちます（`strata_cli/update_cmd.py:473-487`、`strata_control/updater.py:366-377`）。

## 出力とエラー

成功時は通常出力で切り替え元・先、preset の再確認状態、次の操作案内を表示します。`--output json` または `--output jsonl` では成功結果を JSON オブジェクト1行で出力します（`strata_cli/update_cmd.py:318-331`）。

previous が記録されていない、または既に previous のエンジンを使用中の場合は終了コード `2`、以前のパッケージが利用不能・検証失敗の場合は `5`、稼働中のエンジンを待機時間内に停止できない場合は `7` です。人向け出力ではエラーを stderr に `strata: ...` と表示し、JSON / JSONL 指定時は `ok: false` とエラー情報を JSON で出します（`strata_control/updater.py:72-83,1453-1472`、`strata_cli/update_cmd.py:301-308,368-380`）。

## 根拠

- `strata_cli/update_cmd.py:47-57,80-82` — 共通 parser での `--force` 登録、rollback parser への適用。
- `strata_cli/update_cmd.py:310-321` — 値を context に渡した後、rollback 関数へ分岐する処理。
- `strata_control/updater.py:698-705,1193-1204,1680-1688` — `--force` が更新時の失敗済み・スキップ済み版の再試行判定に使われる箇所。
- `strata_control/updater.py:1398-1447,1450-1472` — rollback の対象取得、検証、切り替え、状態更新と失敗条件。`rollback_engine()` 内で `ctx.force` は参照されない。
- `strata_control/updater.py:366-377`、`strata_cli/update_cmd.py:473-487` — 稼働中のエンジンの確認と待機。
- `strata_control/preset_marks.py:72-96` — エンジン identity 変更時の preset 再確認マーク。
- `strata_cli/update_cmd.py:301-308,318-331,368-380` — 成功・失敗の出力と終了コードの返却。
