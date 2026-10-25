# `--boot-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--boot-timeout` |
| 別名 | なし |
| 値 | 秒数。`float` として解釈される |

## 役割

各チューニング測定用 worker を起動してから、準備完了の応答を待つ時間を秒単位で指定します。これはチューニング全体の時間予算ではなく、worker ごとの起動待ち期限です。

## 使い方

```sh
strata tune auto my-profile --boot-timeout 1200
```

`my-profile` は対象の保存済み profile 名、または実行設定 JSON です。parser は `strata tune auto` の `target` 位置引数と `--boot-timeout` を定義しています（`strata_cli/tune_commands.py:20-46`）。

## 値と既定値

- 省略時は `900.0` 秒（15 分）です。
- `argparse` の `type=float` で変換されます。数値に変換できない値や空文字列は parser error となります。範囲・正数の追加検証はありません（`strata_cli/tune_commands.py:45`）。
- そのため 0 または負数は期限到達扱いとなり、通常の起動待ちをほぼ行いません。`nan` は期限比較が成立せず待機ループを通らず、その後 timeout 理由の `int(nan)` 変換で `ValueError` になります。`inf` は有限の期限を作らないため worker が終了しない限り待ちが終わらない値です（`strata_control/tune_session.py:489-507`）。これらの特殊値は推奨値ではなく、parser が拒否しない場合の実装上の帰結です。
- 同じ option を複数回指定した場合に独自処理はありません。`argparse` の通常の `store` 動作で後の値が採用されます。

## 実行時の動作

`strata_cli/cli.py:486` で `strata tune auto` parser が登録され、`:1652-1653` で `tune_commands.auto()` に dispatch されます。そこで `a.boot_timeout` は `WorkerSession(boot_timeout_s=...)` に渡されます（`strata_cli/tune_commands.py:217-219`）。

`WorkerSession` は測定ごとに設定のコピー、engine/worker log、run 設定 JSON を作り、`serve.server` を子プロセスとして起動します。`--boot-timeout` の期限はその起動時刻から計算され、ランダムな loopback port の `/health` に認証付きで問い合わせ、HTTP 200 が返るまで待つ上限になります。問い合わせ間隔は最大 2 秒の request timeout を設け、失敗時には 0.5 秒待って再試行します（`strata_control/tune_session.py:452-479`, `:489-508`）。

この値は `--time`（チューニングの測定予算。`strata_cli/tune_commands.py:37`, `:194-196`）とは別です。起動期限を延ばしても、他の測定・候補数や全体予算は変更されません。`strata tune auto` では各測定 run の worker 起動に使われます。

## 適用条件と副作用

値は `strata tune auto` の測定セッションでのみ使われます。worker は設定コピーを `STRATA_NO_PRESET=1` で起動し、候補設定を測定します。起動時に run ごとの設定 JSON とログファイルを書き、loopback HTTP health check を行います（`strata_control/tune_session.py:452-479`, `:498-505`）。worker がまだ動いている状態で timeout などにより処理を抜けると、`finally` で terminate し、最大 60 秒待った後に kill し、worker log を閉じます（`:510-521`）。

timeout 時に出る `StartFailed("TIMEOUT", ...)` は自動チューナーが測定結果として記録します（`strata_control/tune_session.py:506-507`; `strata_control/autotune.py:322-338`）。最初の基準測定が失敗した場合、結果は `base_failed` となり、その後の候補探索は進みません（`strata_control/autotune.py:397-407`）。

## 出力とエラー

- 数値変換できない値は `argparse` が usage とエラーを出し、終了コード 2 で拒否します。正負や有限性についての独自 validation はありません（`strata_cli/tune_commands.py:45`）。
- worker が期限までに `/health` へ応答しない場合は `TIMEOUT` と理由 `the engine was not ready within … s` が記録されます（`strata_control/tune_session.py:506-507`）。
- 基準測定で起動 timeout となった場合、通常出力では測定失敗の結果が stdout に表示され、`strata tune auto` は終了コード 6 を返します。JSON 出力では結果オブジェクトが stdout に出力されます。進捗メッセージは human 出力時に stderr へ出ます（`strata_cli/tune_commands.py:205-215`, `:257-262`; `:264-284`; `strata_control/autotune.py:403-407`）。候補測定での失敗は trial として扱われ、直ちに CLI parser error にはなりません（`strata_control/autotune.py:322-338`）。

## 根拠

- 索引ではこの文書を `strata tune auto` の option として掲載し、同じ `--boot-timeout` を別 command path の `strata tune run` と分けています（`docs/cli/README.md:804-811`; `:745-750`）。
- parser、既定値、型: `strata_cli/tune_commands.py:20-46`。
- command 登録と dispatch: `strata_cli/cli.py:486-487`; `:1652-1653`。
- 値の worker session への引き渡し: `strata_cli/tune_commands.py:217-219`。
- worker 起動、期限、health check、timeout、後始末: `strata_control/tune_session.py:420-435`; `:452-479`; `:489-521`。
- 失敗の測定記録と基準測定失敗時の扱い: `strata_control/autotune.py:303-338`; `:397-407`。

調査時に CLI `--help` は実行していません。parser 定義と実際の使用箇所をソースで照合しています。Release artifact や他 OS での実行は確認していません。
