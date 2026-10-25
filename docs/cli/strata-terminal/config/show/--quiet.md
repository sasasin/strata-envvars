# `strata config show --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

## 概要

`strata config show` が解決した接続設定を表示するとき、通常の成功出力を抑制します。接続設定の解決・検証は実行されるため、設定エラーは通常どおり報告されます。

## 使い方

```sh
strata config show --quiet
```

JSON 出力では `--quiet` を付けても結果が出力されます。

```sh
strata config show --quiet --output json
```

## 値と既定値

- 値を取らない真偽値オプションです。parser は `action="store_true"` で定義し、指定がなければ `False`、指定すると `True` になります。
- `--quiet` は `strata config show` の parser に定義されています。`config` 親コマンドや他のサブコマンドの `--quiet` とは別のスコープです。
- 繰り返し指定の特別な処理や追加 validation はありません。

## 実行時の動作と相互作用

- `strata config show` は URL、保存済み接続、資格情報を参照する環境変数、タイムアウトを解決し、JSON 形式の結果を標準出力へ書きます。`--quiet` が有効で機械可読出力でない場合、処理中の標準出力を `StringIO` にリダイレクトして捨てるため、成功時の結果は表示されません。
- `--output json` または alias の `--json` を併用すると機械可読出力として扱われ、`--quiet` による抑制は適用されません。JSON は標準出力に出ます。`--output` の既定値は `human` です（このサブコマンドの「human」出力も解決結果の整形 JSON です）。
- quiet は出力だけに作用します。`connections.resolve()` は引き続き実行され、URL・接続記録・タイムアウトなどを検証します。解決にネットワークアクセスはなく、設定ファイルへの書き込みもしません。
- `--effective` は同じ parser に定義されていますが、`config show` の実装はフラグの値を参照せず、常に解決済み設定を返します。したがって `--quiet` の効果や既定動作は変わりません。

## 出力と失敗

- 人間向けモードで成功した場合、通常は解決結果を標準出力に表示し、`--quiet` を付けるとその出力だけがなくなります。
- 接続や値の解決でエラーが起きた場合、`--quiet` があっても `strata: <エラー>` が標準エラーに出力され、エラーに対応する終了コードが返ります。JSON モードではエラーオブジェクトを標準出力に出します。
- 結果には URL、prefix、資格情報環境変数名、およびその環境変数に値があるか (`credential_present`) が含まれます。資格情報の値そのものを出力する処理は確認した範囲にありません。

## 根拠

- parser とスコープ: `strata_cli/monitor_commands.py:96-103`（`config show` と `--quiet` の定義）。
- トップレベル `strata` への parser 登録: `strata_cli/cli.py:488-493`。
- quiet と機械可読出力の判定、および標準出力の抑制: `strata_cli/monitor_commands.py:132-139,167-175`。
- 結果の URL・prefix・資格情報参照・timeout 解決と既定値: `strata_cli/connections.py:273-303`。
- 設定解決エラーの表示経路: `strata_cli/monitor_commands.py:124-129,231-240`。
- 調査時点の Strata checkout は `git status --short --branch` で `## main...origin/main` のみを確認しました。
