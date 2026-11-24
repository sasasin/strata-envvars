# `--no-control`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--no-control` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

通常のコンポーネント更新から Control の更新を除外します。Engine の更新は独立して実行されます。`--no-engine` も併用した場合、`--app` を指定していなければ Engine と Control の更新ステップはいずれも実行されません。

## 使い方

```sh
# Engine は更新対象にし、Control の更新を除外する
strata components update --no-control
```

この例はフィードを読み、Engine など選択された対象を更新し得ます。更新処理自体を実行せずフィードの状況だけ確認するには `--check` を使えますが、その場合 `--no-control` は確認結果を絞りません。

## 値と既定値

値は不要です。指定時は真、未指定時は偽です。値の範囲や追加 validation はありません。同じフラグを繰り返しても真のままです（parser は `argparse` の `store_true`）。

## 実行時の動作

parser は `strata components update` にこのフラグを登録し、CLI は同コマンドを `update_cmd.run` に渡します。通常更新では `control=not a.no_control` として更新処理へ渡します。Control が無効の場合、実際の Control 更新ステップに加え、実行中モデルがある場合の「更新予定」判定からも Control を外します。Engine の更新と、Engine が有効な場合の既設モデル形状別 Engine ステップは別に扱われます。

このフラグは `--app` の選択には影響しません。`--no-control --app` では Control を更新せず、アプリのインストーラー取得・検証処理は引き続き対象になります。また、フィードの取得、署名検証、更新ロック、更新状態の保存は共通処理です。Control の更新を省略しても、Control のパッケージ情報がフィード内にあればフィード自体は読み込まれ、通常更新の最後には通知用の `last_check` 情報が保存されます。

`--check` 指定時は `update_cmd.run` が `updater.check` を呼び、Engine・Control・アプリの状態を含むレポートを返して終了します。この分岐では `no_control` は参照されないため、Control もレポート対象です。

同じ parser 関数はトップレベルの `strata update` にも独立して `--no-control` を登録します。指定文書のスコープは索引どおり `strata components update` です。トップレベルコマンドは索引上の別スコープです。

## 適用条件と副作用

通常更新では Control の存在確認・新しい Control のダウンロード・展開・起動テスト・`active.json` の切り替えを行う Control 更新ステップを省略します。Engine、アプリのインストーラーなど、他に有効な更新対象があればそれらの処理は継続します。フィード取得や共通の状態ファイル更新など、Control ステップ外の処理は抑止しません。

このフラグは引数の受理後に値を補正・拒否する個別 validation を持ちません。更新処理自体は acquisition が禁止された環境で拒否され、フィード・署名関連の例外も通常の失敗経路で返されます。

## 出力とエラー

人向け出力では、通常更新結果として実行されたステップの結果が表示されるため、除外した Control の更新結果行は作られません。`--output json` / `jsonl` でも結果は同じ選択対象に基づきます。`--check` の人向け・機械向けレポートには Control の状態が含まれます。

更新エラーは既定の human 出力では標準エラーに `strata: <メッセージ>` として出力され、対応する終了コードを返します。機械出力ではエラーオブジェクトを JSON で出力します。Control を省略しても、フィード取得や残る更新対象の失敗は通常どおり発生し得ます。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-79` — `strata update` と `strata components update` の parser 登録。どちらも値なしの `store_true`。
- `terminal/strata_cli/cli.py:135-161,2210-2212` — `components` 階層と parser 登録、対象コマンドの `update_cmd.run` への dispatch。
- `terminal/strata_cli/update_cmd.py:361-377` — `--check` の分岐と、通常更新で `control=not a.no_control` を渡す箇所。
- `terminal/strata_control/updater.py:2066-2079,2082-2096` — Engine/Control の保留変更判定と、稼働モデルがある場合に判定結果を使う箇所。
- `terminal/strata_control/updater.py:2109-2139` — 有効な対象だけを更新ステップに加える処理、共通フィード読込・状態保存、結果と終了コード。
- `terminal/strata_control/updater.py:1936-1984` — Control 更新ステップのダウンロード、テスト起動、active pointer の更新と一時ディレクトリの後始末。`control=False` ではこの関数を呼ぶステップが追加されない。
- `terminal/strata_cli/update_cmd.py:311-316,378-390` — human / 機械出力の失敗経路、acquisition 拒否、割り込み時の処理。
