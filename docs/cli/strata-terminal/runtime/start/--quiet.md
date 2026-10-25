# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

人向け出力を抑制します。`runtime start` は保存済み profile のサーバーをバックグラウンドで起動し、このフラグは起動処理そのものではなく、Terminal CLI が表示する人向け stdout を制御します。

## 使い方

```sh
strata runtime start --profile my-profile --quiet
```

## 値と既定値

値は不要です。省略時は quiet ではありません。parser は `store_true` で登録され、明示した場合は真になります。短縮別名はありません。繰り返し指定しても真のままです。

## 実行時の動作

`runtime start` parser には `--quiet` の個別定義がありませんが、`strata_cli/cli.py` が `runtime_start` を含む one-shot parser 群すべてに、`action="store_true"`、`default=argparse.SUPPRESS` で追加します。未指定時には属性を作らず、`main()` は `getattr(a, "quiet", False)` で未指定を false として扱います。

人向け出力モード（既定）で `--quiet` が指定されると、`main()` はコマンド処理中の stdout をメモリ上の捕捉先へリダイレクトします。処理が成功した場合、捕捉した出力は表示しません。処理が失敗した場合は、捕捉した stdout を stderr に戻します。quiet でもエラー出力を確認できるようにする動作です。

`_runtime()` は `--quiet` を `management.runtime_action()` に渡しません。そのため quiet は runtime の起動条件や管理処理には影響せず、親 CLI の表示だけに適用されます。`runtime start` 自体は引き続きバックグラウンド owner host を起動し、端末終了後もサービスを稼働させます。

`--output json` と併用した場合は JSON 出力が優先され、quiet の stdout 抑制分岐を通りません。共通の `--json` alias も `output=json` に変更するため同様です。

## 適用条件と副作用

このオプション自体は stdout の表示だけを制御します。runtime 起動が行われるかは他の引数と profile によります。通常の `runtime start` は管理処理を通じて起動処理を実行し、起動結果を人向けまたは JSON 形式で報告します。

捕捉される出力は最大 64 KiB です。超過した場合、失敗時には stderr に省略通知を出してから保持された末尾の出力を返します。stderr への出力はリダイレクトされません。

## 出力とエラー

- 人向けモードで成功した場合、コマンド処理の stdout は抑制されます。
- 人向けモードで失敗した場合、捕捉した stdout は stderr に再出力されます。失敗メッセージや起動ログのヒントなど、処理から直接 stderr に書かれる内容も quiet では抑制されません。
- `--output json` または `--json` 併用時は JSON stdout が出力され、quiet による抑制は行われません。
- フラグに値を付ける、または対象外の場所に指定すると argparse の引数エラーになります。quiet 固有の validation や終了コード変更はありません。

## 根拠

- parser とスコープ: `strata_cli/cli.py:203-212` で `runtime_start` を定義し、`strata_cli/cli.py:508-515` で `runtime_start` を含む one-shot parser に `--quiet` を追加しています。
- 起動処理への非伝播と出力: `strata_cli/cli.py:1331-1373` で runtime の実行と結果表示を行いますが、`runtime_action()` 呼び出しに quiet は渡しません。失敗時のエラー・stderr 経路は `strata_cli/cli.py:2166-2183` にあります。
- quiet の捕捉・抑制・JSON 相互作用: `strata_cli/cli.py:2223-2247`。JSON 指定から出力形式を切り替える共通 alias は `strata_cli/cli.py:2232-2235`。
- `runtime start` の実際の起動: `strata_control/management.py:202-230` が start の検査・実行へ進み、`strata_control/runtime.py:518-530` がバックグラウンド owner host のライフサイクルを説明します。

## 関連文書

- [`--output`](--output.md)
- [`--plan`](--plan.md)
