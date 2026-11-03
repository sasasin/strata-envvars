# `strata update --yes`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真 |

## 役割

更新時に対話確認を行わないためのフラグです。スクリプトから実行する場合に使えます。ただし「すべての確認に肯定する」フラグではありません。モデルが稼働中でも、このフラグだけでは停止許可にならず、更新は変更前に拒否されます。

## 使い方

```sh
# 既存モデルを停止せずに更新を試みる。モデル稼働中なら exit 7 で変更されない。
strata update --yes

# 稼働モデルの停止と、更新後の同じ設定での再起動まで自動化する。
strata update --yes --stop-model --start-again
```

`strata update` は署名済み feed を使ってエンジンと Control を更新し、エンジンはテスト起動後に切り替えます。実更新を行うため、最初の例も更新が必要な場合はダウンロードとインストールを実行します（`strata_cli/update_cmd.py:1-7,59-69`）。

## 値と既定値

`argparse` の `action="store_true"` で定義され、未指定時は偽、指定時は真です。値は取りません。明示的な値指定や値の範囲検証はありません（`strata_cli/update_cmd.py:59-69`）。同一フラグの複数回指定について、独自の処理はありません。

## 実行時の動作

`strata update` の parser がこのフラグを受理し、`update_cmd.run()` は更新処理に `ModelGate` を渡します。`--yes` があると `_ask_factory()` は質問関数を返さず `None` にします。一方、モデル停止を許す `ModelGate.allow_stop` は別の `--stop-model` だけから設定されます（`strata_cli/update_cmd.py:67-69,297-301,333-350`）。

更新対象の変更があり、モデルが稼働中なら、更新前の `ModelGate.consent()` は停止許可がない場合に `UpdateError`（exit 7）を発生させ、何も変更せず、`--stop-model` を付けて再実行する方法などを示します。したがって `--yes` 単独では稼働モデルを停止しません（`strata_control/updater.py:1696-1710`、`strata_control/engine_update.py:307-330`）。モデルがなければ、このゲートによる質問は発生せず通常の更新処理へ進みます。

`--stop-model` を併用すると、同意済みモデルはダウンロード後、更新のステージングやテスト起動の前に停止されます。更新が終わった後（更新失敗時を含む）にモデルを再起動するかは別の `--start-again` が制御します。`--yes` だけでは再起動せず、停止済みモデルは停止状態のままです（`strata_control/updater.py:325-331`、`strata_control/engine_update.py:334-363,376-406,412-432`）。

`--check` は feed を確認して結果を返す分岐で、モデルゲートを通る通常更新処理より前に終了します。この場合 `--yes` による確認抑止は実質的に使われません（`strata_cli/update_cmd.py:290-306`）。

## 適用条件と副作用

- この文書は `strata update` のスコープです。索引では `strata components update` にも同名オプションが掲載されていますが、コマンド階層が別のため別文書の対象です（[`docs/cli/README.md`](../../README.md) の該当節）。両 parser は同じ `update_cmd.py` 内で同じ `store_true` と同じ確認ゲートに接続されています（`strata_cli/update_cmd.py:59-79,2136-2138`）。
- `--yes` は質問関数を無効にするだけで、`--stop-model` や `--start-again` を暗黙に有効化しません。自動化でモデルを止めて更新し、戻す場合は3つを明示します（`strata_cli/update_cmd.py:333-350`）。
- このフラグ自体がファイルやネットワークを操作するのではなく、通常更新経路で質問を抑止します。更新経路は署名済み feed の取得、コンポーネントのダウンロード・検証・導入を行い得ます（`strata_cli/update_cmd.py:284-301`）。

## 出力とエラー

モデルが稼働中で停止許可がないと、`--yes` により対話質問は行わず、通常出力では `strata: ...` のエラーを stderr に出して exit 7 を返します。更新前ゲートのため変更はありません（`strata_cli/update_cmd.py:237-242,307-311`、`strata_control/engine_update.py:317-324`）。`--output json` または `jsonl` では、失敗は `ok: false` と `error` を含む JSON 出力になります（`strata_cli/update_cmd.py:98-108,237-242,303-311`）。

更新が成功しても、停止したモデルを再起動できなかった場合は exit 8 になり得ます。これは `--start-again` を指定して再起動を試みた後の失敗も含みます（`strata_control/engine_update.py:376-406,426-431`）。

## 根拠

- `strata_cli/update_cmd.py:59-69` — `strata update` parser と `--yes` / 関連フラグの定義。
- `strata_cli/update_cmd.py:297-306,333-350` — 更新への受け渡し、質問関数の抑止、停止・再起動許可との分離。
- `strata_control/updater.py:1696-1710,325-331` — 変更がある場合の事前モデル確認と、停止処理のタイミング。
- `strata_control/engine_update.py:307-330,334-363,376-406,412-432` — モデル停止の許可条件、ダウンロード中に後から開始されたモデルへの扱い、再起動と失敗時の結果。
- `strata_cli/update_cmd.py:237-242,290-319` — 出力形式、更新前確認分岐、失敗出力と終了コード。
