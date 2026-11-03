# `strata components remove --feed`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 1 個の文字列。parser の help では署名付き update feed の URL またはフォルダーと説明されていますが、このコマンドでは値を使用しません。 |

## 役割

`--feed` は共通 parser によって `strata components remove` でも受理されます。ただし remove はローカルに導入済みの engine package を削除するコマンドであり、この実行経路では feed の参照もダウンロードも行いません。したがって、ここで指定する値は削除対象や削除動作に影響しません（`strata_cli/update_cmd.py:47-58,88-91,272-273,358-400`）。

## 使い方

構文上は次のように値を指定できますが、remove では値は利用されません。

```sh
strata components remove 0.1.54 --feed https://example.invalid/strata-feed.json
```

`engine` には導入済み engine の版またはフォルダー名を指定します。削除に使う feed を切り替える効果はありません（`strata_cli/update_cmd.py:88-91`）。

## 値と既定値

parser は `_common()` から `--feed` を登録し、`default=None` としています。型変換や URL・フォルダーの検証はこの宣言では設定されていません。値を省略すると通常の `argparse` により引数エラーになります。空文字列を含め、構文上受理された値も remove の処理では参照されません（`strata_cli/update_cmd.py:47-48,88-91`）。

## 実行時の動作

`strata_cli/cli.py` は `components remove` を `update_cmd.run()` に委譲します。`run()` は共通 context を作成した後、`components_command` が `remove` の場合に `_engines_command()` を呼びます。そこでは導入済み engine 一覧から位置引数 `engine` と `--family` に一致する項目を選び、`delete_engine()` を実行します。この経路は `_feed_source()` を呼び出さず、`a.feed` も読みません（`strata_cli/cli.py:2136-2138`; `strata_cli/update_cmd.py:123-132,244-256,272-273,358-360,378,395-400`）。

`_feed_source()` が `--feed` を参照するのは更新処理向けの feed source を選ぶ場合です。`remove` はその後の更新分岐にも進みません（`strata_cli/update_cmd.py:123-132,284-301`）。

## 適用条件と副作用

remove で `--feed` を指定しても、ネットワークアクセス、署名確認、feed の読み込みは発生しません。ローカル engine の削除自体は指定値にかかわらず実行され得ます。削除処理は engine が使用中の場合に拒否し、対象ディレクトリを一時名へ rename してから削除します。Qwen engine の場合は関連する更新 state/history も更新します（`strata_control/engine_library.py:294-334`）。

## 出力とエラー

成功時、通常出力では削除した engine の版、解放容量、およびモデルと設定には触れなかった旨を表示します。`--output json` または `jsonl` の場合は成功結果を JSON として出力します。対象 engine が見つからない場合や削除不可の場合は `UpdateError` 経由で失敗します（`strata_cli/update_cmd.py:237-242,395-400`; `strata_control/engine_library.py:198-211,294-316`）。

`--feed` 固有の出力・失敗経路は確認できません。remove ではその値を使用しないためです。

## 根拠

- `strata_cli/update_cmd.py:47-58,88-91` — 共通 parser における `--feed` の宣言と remove への適用。
- `strata_cli/cli.py:2136-2138` — `components remove` の実装への委譲。
- `strata_cli/update_cmd.py:123-139,244-256,272-273,284-301,358-400` — feed 解決経路と remove の分岐・出力。
- `strata_control/engine_library.py:198-211,294-334` — engine の照合、削除条件、副作用。
