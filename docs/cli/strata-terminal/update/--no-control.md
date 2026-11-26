# `--no-control`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--no-control` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

通常の更新処理から Control コンポーネントの更新を外し、主に Engine だけを更新したい場合に使います。Engine 更新と、Engine 更新が有効なときに組み立てられるモデル形状別 engine の更新は引き続き対象です。`--app` を併用した場合は app installer の取得・検証も引き続き行います。

## 使い方

```sh
# 署名済み feed から Engine を更新し、Control の更新工程は省く
strata update --no-control

# Engine を更新せず、Control も app installer も対象にしない（feed の確認自体は行う）
strata update --no-engine --no-control
```

## 値と既定値

値は指定しません。parser は `action="store_true"` で登録しており、未指定時は偽です。したがって未指定では Control 更新が有効で、指定すると `control=False` が更新処理へ渡されます。値の検証や独自の無効値処理はありません。同じフラグを繰り返しても真のままです。`terminal/strata_cli/update_cmd.py:59-69`、`:371-372`。

## 実行時の動作

通常実行では parser の値を反転して `engine_update.update_with_models(..., control=not a.no_control)` に渡します。更新本体はこの値を使って、Control の変更有無をモデル停止判定から除き、更新工程のリストにも Control の `update_control` を加えません。そのため Control の更新・展開・検証起動・active pointer の切り替えはこの実行では行いません。Engine は既定で有効であり、`--no-engine` を併用しなければ更新されます。`terminal/strata_cli/update_cmd.py:371-372`、`terminal/strata_control/updater.py:2066-2079`、`:2082-2096`、`:2109-2122`。

Control を省いても、更新前に署名済み feed 自体は読み込まれます。`--check` 経路は `--no-control` を引数に渡さず `updater.check(ctx)` を呼び、Engine・Control・app の判定を報告します。従って `strata update --check --no-control` でも Control の状態確認・表示は省略されません。また `check` は feed 確認結果を state の `last_check` に保存します。`terminal/strata_cli/update_cmd.py:361-367`、`terminal/strata_control/updater.py:778-789`。

`--app` との組み合わせでは Control 工程を省いたまま app installer 工程を実行します。通常更新では結果が個別に集約され、失敗した工程のエラーと終了コードが返ります。`--no-control` 自体は独自の出力や失敗経路を持たず、Control の結果項目も生成しません。`terminal/strata_control/updater.py:2119-2139`。

## 適用条件と副作用

`strata update` に対するフラグです。索引には別スコープの `strata components update` にも同名オプションがありますが、この文書は `strata update` のみを扱います。両 parser で `store_true` として登録されています。`terminal/strata_cli/update_cmd.py:59-79`、索引 [`docs/cli/README.md:257-269`](../../README.md)。

このフラグは Control の更新工程だけを抑止します。feed の取得・署名検証、Engine の更新、要求した app installer のダウンロードと検証は別の処理です。通常更新は `STRATA_NO_ACQUIRE` 等による取得拒否、feed/署名エラー、Engine 等の更新失敗の影響を受けます。Control を更新しないため、Control 専用のダウンロード、展開、テスト起動、active pointer 更新、旧 Control 世代の整理は発生しません。`terminal/strata_cli/update_cmd.py:355-388`、`terminal/strata_control/updater.py:1936-1984`、`:2112-2122`。

## 出力とエラー

通常の人向け出力では実行した工程の結果が表示されるため、Control の結果行はありません。`--output json` / `jsonl` でも Control 工程の結果は含まれません。これは Control が最新であることを意味せず、この実行で Control 更新をスキップしたことを意味します。機械可読モードでも更新本体の feed 読み込み・他工程の失敗は返されます。`terminal/strata_cli/update_cmd.py:368-388`、`terminal/strata_control/updater.py:2123-2139`。

このフラグ固有の validation error はありません。更新全体で発生した `UpdateError`、feed error、署名エラー、取得拒否、割り込みは通常の更新経路で処理されます。`terminal/strata_cli/update_cmd.py:378-390`。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-79` — `strata update` と `strata components update` の parser 登録、およびフラグが値を取らないこと。
- `terminal/strata_cli/update_cmd.py:361-377` — `--check` 経路と、通常実行で `control=not a.no_control` を渡す箇所。
- `terminal/strata_cli/update_cmd.py:378-390` — 更新失敗、feed・署名・取得拒否、割り込みの出力と処理。
- `terminal/strata_control/updater.py:2066-2079`、`:2082-2096` — Control をモデル停止判定の変更一覧に含める条件。
- `terminal/strata_control/updater.py:2109-2139` — Control 更新工程の追加条件、工程別失敗収集、最終結果。
- `terminal/strata_control/updater.py:778-789` — `--check` が Control も判定し、確認結果を状態へ保存する処理。
- `terminal/strata_control/updater.py:1936-1984` — 通常の Control 更新工程が行うダウンロード、展開、テスト起動、切り替えと整理。
