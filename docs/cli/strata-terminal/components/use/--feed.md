# `strata components use --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | `URL|DIR` 相当の文字列を1つ受け取る。use 経路では形式検証も参照もされない |

## 役割

このコマンドスコープでは `--feed` は共通 parser によって受理されますが、`strata components use` の処理では使われません。`use` は既にインストール済みの engine を選ぶローカル操作であり、feed の読み込み、ネットワークアクセス、feed による engine の検索やインストールは行いません。feed を指定しても選択対象や切り替え結果は変わりません（parser 登録: `terminal/strata_cli/update_cmd.py:47-56,84-87`、`use` の処理分岐: `terminal/strata_cli/update_cmd.py:337-338,466-491`）。

## 使い方

```sh
# newest に選択を戻す。--feed は受理されるが、このコマンドでは参照されない。
strata components use newest --feed https://example.invalid/strata-feed.json
```

`newest` はインストール済み一覧上の最新 engine を指します。コマンド自体は engine の選択状態を変更し得ます。feed の指定はその切り替えに関与しません（`terminal/strata_control/engine_library.py:184-197,211-228`）。

## 値と既定値

- parser 定義は `default=None` の通常の `argparse` 引数で、`type`、`choices`、独自 validation は指定されていません。1個の値が必要です（`terminal/strata_cli/update_cmd.py:47-49,84-87`）。
- 未指定時の属性値は `None` です。空文字列を明示した場合も use 経路で検査・利用されません。重複指定時の特別な処理はなく、標準 `argparse` の単一値引数として処理されます。
- 値を欠いた場合など parser が構文エラーにする入力は `argparse` の usage error となります。独自 validation がないため、URL やディレクトリとしての有効性はこの parser では確認しません。

## 実行時の動作

`run()` は引数から component directory と backend 情報を含む context を作り、`components_command` が `use` なら `_engines_command()` に分岐して戻ります（`terminal/strata_cli/update_cmd.py:303-321,337-338`）。この分岐は feed source を解決するコードより前です。feed source の解決（明示 `--feed`、`STRATA_UPDATE_FEED`、記憶済み source、既定 source の順）は `strata update` 側でのみ行われます（`terminal/strata_cli/update_cmd.py:142-158,351-355`）。したがって `use` では `--feed` の値は `STRATA_UPDATE_FEED` や記憶済み feed と比較されず、優先順位・相互作用もありません。

`use` はインストール済み engine 一覧から位置引数の engine 名を解決し、指定の backend/family に適合することを確認してから `use_engine()` を呼びます（`terminal/strata_cli/update_cmd.py:466-472`）。engine の署名とファイル一式を検証し、次回の起動で選択されるよう状態ファイルの pin を設定します。すでに最新選択に一致する場合は pin を設定せず更新なしとして扱うことがあります（`terminal/strata_control/engine_library.py:211-228,277-312`、`terminal/strata_control/updater.py:1701-1735`）。これらは `--feed` の値による動作ではありません。

## 適用条件と副作用

- `--feed` は parser 上 `components use` にも登録されていますが、同コマンドの処理では未使用です。feed ファイルの読み取り、HTTP 要求、feed 署名検証、ダウンロード、engine の追加は発生しません（`terminal/strata_cli/update_cmd.py:47-56,337-338,351-355`）。
- `use` 自体は engine 選択状態を保存します。対象 engine が別の GPU make 向けで、その make が同一 PC で検出される場合は backend 選択も保存されます（`terminal/strata_control/engine_library.py:277-293`）。インストール済み engine が実行可能かは実ハードウェア条件で判定されます（`terminal/strata_cli/update_cmd.py:466-471`）。
- 実行中の model がある場合、`--wait` が未指定なら対話端末で待機確認を行うことがあり、処理側も idle になるまで待つか拒否します。`--feed` はこの判定に関係しません（`terminal/strata_cli/update_cmd.py:467-469,500-515`、`terminal/strata_control/engine_library.py:221-225`）。

## 出力とエラー

成功時の人間向け出力は、既に使用中なら「変更なし」、切り替えた場合は選択した engine と tuning preset の扱いなどを表示します（`terminal/strata_cli/update_cmd.py:471-490`）。`--output json` または `jsonl` では成功結果を JSON で出力します（`terminal/strata_cli/update_cmd.py:303-305,471-474`）。どの出力モードでも feed 値自体は表示・使用されません。

engine 名が未導入または曖昧な場合は exit code 2、PC で動作しない engine や検証に失敗する engine は exit code 5、実行中 model が切り替えを妨げる場合は exit code 7 で失敗します（`terminal/strata_control/engine_library.py:184-197,202-208,238-254,296-312`、`terminal/strata_cli/update_cmd.py:466-471`）。これらは `--feed` の値とは無関係です。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,84-87` — 共通 parser での `--feed` 定義と `components use` への登録。
- `terminal/strata_cli/update_cmd.py:142-158,303-321,337-355` — feed source 解決の実装と、use 分岐がその手前で終了すること。
- `terminal/strata_cli/update_cmd.py:466-491` — installed engine の解決、切り替え呼び出し、成功出力。
- `terminal/strata_control/engine_library.py:184-197,211-228,277-312` — 対象 engine の解決、busy/適合性確認、署名・内容確認、Qwen engine の切り替え。
- `terminal/strata_control/updater.py:1701-1735` — engine 選択 pin の保存と、起動時選択の検証。
