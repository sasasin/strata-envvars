# `strata launch --yes`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は偽。 |

## 役割

`strata launch` の通常実行で、利用可能なエンジンがない場合にモデルをダウンロードする前の確認を省略します。すべての確認や停止条件を一括で無効化するフラグではありません。

## 使い方

```sh
strata launch --model q2_0 --no-tui --yes
```

この例はモデルを指定して非対話起動します。エンジンがこの PC で利用できず、モデルのダウンロードが必要でも、そのダウンロード確認を求めずに先へ進みます。通常の起動はモデルや必要ファイルの取得、設定、サーバー起動を伴うため、`--yes` はそれらの実行を許可する選択として扱ってください。

## 値と既定値

`argparse` の `store_true` フラグで、値は不要です。省略時の `a.yes` は偽です。値の範囲や別名はありません（`strata_cli/launch/cmd.py:137`）。

## 実行時の動作

- 通常のフラグ起動では `a.yes` が `Runner(assume_yes=...)` に渡されます（`strata_cli/launch/cmd.py:715-716`）。Runner がエンジン更新後にも利用可能なエンジンを確認できないとき `no_engine()` に進み、`assume_yes` が真なら確認関数を呼ばずに戻ります。その後のモデル処理は継続可能です（`strata_cli/launch/runner.py:610-616,653-669`）。エンジン自体を導入する指定ではありません。
- `--output json` の機械可読モードも `assume_yes` を真にします。従って、この確認の抑止は `--yes` を明示した場合に限りません（`strata_cli/launch/cmd.py:634,715-716`）。
- `--data-dir` と併用した場合、`--yes` は既存モデルライブラリを新しい場所へ移動する問いへの回答にはならず、移動を行わない側に倒します。移動するには `--move-data` が必要で、こちらの判定が `--yes` より先です（`strata_cli/launch/cmd.py:504-526`）。
- `--plan` は Runner の計画を表示して終了し、変更しません。計画モードでは既存モデルの移動も行いません（`strata_cli/launch/cmd.py:731-760`, `strata_cli/launch/cmd.py:504-512`）。

## 適用条件と副作用

- `--yes` は `Runner` を使う通常経路の `no_engine()` 確認に作用します。対話画面を開く経路では `run_tui()` に `a.yes` が渡されず、画面側 Runner は別の確認 callback を持ちます。ダウンロード量が 1 GB 以上の場合、画面は独自の確認画面を表示します（`strata_cli/launch/cmd.py:688-710,780-783`; `strata_cli/launch/app.py:280-300`）。
- 既存サーバーが別設定で同じ port を使う場合、画面経路は再起動の確認を行い、画面のない Runner 経路は `--restart` がなければ拒否します。`--yes` では再起動しません（`strata_cli/launch/cmd.py:132-137`; `strata_cli/launch/runner.py:1505-1538`）。
- 画面を出せない対話端末の「今すぐ起動するか」という別の質問も `--yes` を参照せず、ユーザー入力で判定されます（`strata_cli/launch/cmd.py:697-705,772-779`）。
- 既存モデルライブラリの移動以外に、`--yes` 専用のファイル操作はありません。ただし通常の launch を続行すれば、モデルのダウンロードやサーバー起動など通常処理の副作用は発生し得ます。

## 出力とエラー

`--yes` がない通常 Runner 経路で確認を拒否すると、「Stopped. Nothing was downloaded.」を含む `LaunchError`（コード 130）になります。人向け出力では `strata:` を付けて stderr に出し、JSON モードではエラー JSON を stdout に出します（`strata_cli/launch/runner.py:668-669`; `strata_cli/launch/cmd.py:636-641,785-787`）。`--yes` はこの確認拒否経路を通らないようにしますが、他の validation や起動失敗を無効にはしません。

同じ文字列 `--yes` は `strata connect --write` にもありますが、別 parser・別コマンドの確認用です。本書の対象は `strata launch` のオプションです（`strata_cli/launch/cmd.py:75-82,137,148-165`）。

## 根拠

- `strata_cli/launch/cmd.py:75-82,127-140` — `strata launch` parser、`--yes` の宣言。
- `strata_cli/launch/cmd.py:504-526,630-641,688-716,731-760,772-783` — 既存モデル移動の選択、実行モード、Runner への値の受け渡し、計画・質問経路。
- `strata_cli/launch/runner.py:610-616,653-669` — エンジンなしの検出、モデルダウンロード確認、および拒否時のエラー。
- `strata_cli/launch/runner.py:1505-1538` — 稼働中サーバーとの衝突および `--restart` の条件。
- `strata_cli/launch/app.py:280-300` — 対話画面側の独立したダウンロード確認。
