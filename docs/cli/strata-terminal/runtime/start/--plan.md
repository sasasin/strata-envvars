# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `false` |

## 役割

保存済み profile を実際には起動せず、起動候補の設定を計算して表示します。計画には有効設定、起動時の server 引数、engine 実行ファイルと引数、source config の SHA-256、`--shutdown-timeout` の値が含まれます。`would_start` は常に `false` です。

## 使い方

```sh
strata runtime start --profile local --plan
```

機械可読形式が必要なら `--output json`（または同コマンドに後付けされる alias `--json`）を併用できます。

## 値と既定値

`--plan` 自体は値を受け取らず、`argparse` の `store_true` で定義されています。省略時は偽、指定時は真です。同じフラグを複数回指定しても真のままです。値を後ろに付ける構文ではありません。

このコマンドでは `--profile` が必須です。計画に出る `shutdown_timeout` は `--shutdown-timeout` の値で、既定値は 30 秒、受理範囲は有限な数値の 0〜300 秒です。`--wait` は既定 300 秒、範囲 0〜600 秒ですが、計画出力には使われません（管理処理で範囲検証は行われます）。

## 実行時の動作

CLI は `--plan` を `management.runtime_action(..., plan=...)` に渡します。start の計画経路では execution precondition があれば拒否し、対応 platform かを確認して profile を読み込み、`_start_candidate` を2回実行して候補と source digest が一致することを確認します。一致しなければ再試行を促すエラー（終了コード 6）になります。候補には profile revision、source config、effective 設定、server/engine の引数などが含まれます。

この経路は `runtime.start()`、owner host の生成、engine の起動を呼び出さず、journal に start 操作を記録しません。したがって runtime を起動・停止する操作ではありません。`--die-with-pid` は実起動時にのみ `runtime.start()` へ渡されるため、`--plan` と併用しても候補に反映されません。`--shutdown-timeout` は候補の server 引数と plan の `shutdown_timeout` に反映されます。

## 適用条件と副作用

`strata runtime start` は保存済み profile を要求します。指定した profile が未保存、構造不正、source config が読めない、effective 設定が矛盾する、API key が不正、候補計算中に設定が変わる場合など、候補を確定できなければ失敗します。runtime の制御 transport が利用できない platform も拒否されます。

この plan 分岐自体は runtime state や journal を変更しません。ただし profile の読み込みは `profiles.load()` を通り、アクセス権修復を伴う読み込み関数を使います。そのため、保護設定の問題がある profile では、確認処理に付随してファイルアクセス権が修復される場合があります。候補計算では source config を読み、engine 引数生成を行いますが、エンジンの preflight／起動は実行しません。plan 成功は実際の起動成功を保証しません。

## 出力とエラー

成功時は終了コード 0 です。通常の human 出力では plan オブジェクトを整形 JSON で stdout に出し、`--output json` / `--json` では `schema_version: 1`、`ok: true`、`plan` を含む JSON を出します。エラーは通常 stderr に `strata: ...` として出力され、JSON 出力時は `ok: false` と error 情報を JSON にします。profile や設定の不備は主に終了コード 5、候補が計算中に変わった場合などは 6 です。OS ファイル操作エラーは CLI の共通処理で終了コード 6 に変換されます。

## 根拠

- parser と既定値: `strata_cli/cli.py:203-212`。`--json` / `--quiet` の後付け: `strata_cli/cli.py:508-515`。
- CLI から管理処理への引き渡しと出力: `strata_cli/cli.py:1331-1373`。
- plan 分岐、検証範囲、二重計算と戻り値: `strata_control/management.py:188-230`。
- 候補生成、設定の優先順位・相互作用、API key validation、plan 内容: `strata_control/runtime.py:458-462`、`strata_cli/cli.py:745-826`。
- profile 読み込み・形式検証: `strata_control/profiles.py:120-166`。
- 共通 human/JSON 成功・エラー形式、および例外の終了コード処理: `strata_cli/cli.py:527-542`、`strata_cli/cli.py:2119-2183`。
- plan が起動 state と journal を変更しないことを検証する既存ケース（実行はしていない）: `tests/terminal/test_runtime.py:923-928`。

## 調査範囲

指定 revision の checkout にあるソースを確認しました。CLI help、Release 配布物、build、テスト、runtime 実行は調査していません。
