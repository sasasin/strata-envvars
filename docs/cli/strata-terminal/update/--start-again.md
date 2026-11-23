# `--start-again`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点。`main` / `origin/main`、未コミット変更なし）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--start-again` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ（`store_true`、既定 `False`） |

## 役割

更新のために停止したモデルを、更新後に同じ設定で起動し直すことを、質問なしで確定する。対話端末では「同じ設定で起動し直しますか」という質問への「はい」を先に与える意味になり、スクリプトや `--yes`、`--output json`/`jsonl` のように誰にも質問できない実行では、再起動を行う唯一の手段になる。停止の許可を与える `--stop-model` とは別の判断であり、`--start-again` だけではモデルを停止しない（`terminal/strata_cli/update_cmd.py:67-69`、`terminal/strata_control/engine_update.py:286-294`）。

## 使い方

```sh
# スクリプト: 停止を許可し、更新後に同じ設定で起動し直す
strata update --yes --stop-model --start-again

# 対話端末: 停止の確認だけ答え、再起動は質問させない
strata update --start-again

# アプリ連携: JSONL のイベントを読みながら、停止と再起動を任せる
strata update --output jsonl --stop-model --start-again
```

## 値と既定値

値を取らない。指定すると真、省略すると偽で、複数回指定しても真のままである。`--start-again=true` のような値の付与は argparse の usage エラーになる。モデルが稼働中で、`--stop-model` も `--start-again` もなく、質問もできない実行では、更新は何も変更せずに終了コード 7 で「`--stop-model` を付けて再実行し、その後に起動し直すなら `--start-again` も付ける」と案内する（`terminal/strata_cli/update_cmd.py:68-69`、`terminal/strata_control/engine_update.py:310-317`）。

## 実行時の動作

`strata update` の parser はこの値を `ModelGate` の `start_again` にそのまま渡す（`terminal/strata_cli/update_cmd.py:414-417`）。更新処理は、ダウンロード前に `ModelGate.consent` でモデルの停止同意を取り、ダウンロード後のステージング直前に `ModelGate.release` で実際に停止する（`terminal/strata_control/updater.py:395-401,2060-2074`）。更新本体が終わると `ModelGate.finish` が停止済みモデルを一件ずつ処理し、`start_again` が真なら質問を省いて起動する（`terminal/strata_control/engine_update.py:370-399`）。再起動は保存済みプロファイル（run config と overrides）をそのまま使い、モデル設定は書き換えない（`terminal/strata_control/engine_update.py:230-249`）。

`--yes`、`--output json`/`jsonl`、標準入力か標準出力が端末でない実行では質問役が `None` になるため、`--start-again` がない限り停止したモデルは停止したままになり、手動起動の方法が表示される（`terminal/strata_cli/update_cmd.py:400-403`、`terminal/strata_control/engine_update.py:380-388`）。逆に対話端末で `--start-again` を付けると、停止の質問には答えが必要だが、再起動の質問は出ない。

## 適用条件と副作用

- 再起動の対象は、この更新が実際に停止したモデルだけである。`--wait` でモデルが先に停止した場合や、ダウンロードが停止前に失敗した場合、停止対象が存在しない場合は何も起きない（`terminal/strata_control/updater.py:2066-2070`、`terminal/strata_control/engine_update.py:421`）。
- 更新が失敗して旧 engine が使われている場合でも、停止済みモデルは旧 engine 上で起動し直される（`terminal/strata_control/engine_update.py:374-377`）。
- Strata 自身が起動したモデル（`launch-*` プロファイルや保存プロファイル）だけが対象で、`strata serve` やサービスなど外部プロセスが保持するサーバーは `--start-again` があっても停止できず、終了コード 7 で中断する（`terminal/strata_control/engine_update.py:146-158,301-307`）。
- 起動し直したモデルは更新後の engine で動く。Cloudflare access を使うモデルではトンネルの再開も試み、失敗してもモデル自体は起動済みとして扱い、その旨を表示する（`terminal/strata_control/engine_update.py:243-249`）。
- 再起動に失敗した場合、`runtime.stop` と `runtime.cleanup` で中途半端なプロセスを残さない（`terminal/strata_control/engine_update.py:257-262`）。
- `--check` はフィードを読むだけで `ModelGate` を作らないため、`--start-again` を同時に指定しても効果はない（`terminal/strata_cli/update_cmd.py:357-363`）。

## 出力とエラー

- 人間向け出力では更新結果の表示後に `Starting <model> again (loading can take a few minutes)...` と再起動結果を出し、成功時は「同じ設定で提供中」と表示する（`terminal/strata_cli/update_cmd.py:367`、`terminal/strata_control/engine_update.py:391-393`、`terminal/strata_control/engine_update.py:249`）。
- 終了コードは、更新成功かつ再起動成功なら 0、更新成功だが再起動失敗なら 8（このとき「更新は完了したが停止したモデルが起動しなかった」と表示）、更新失敗なら 6、停止同意が得られない・外部サーバーの場合は 7（`terminal/strata_cli/update_cmd.py:369-373`、`terminal/strata_control/engine_update.py:404-425`）。
- 更新が 6 で失敗し、その後の再起動にも失敗した場合、終了コードは 8 ではなく 6 のままである（`terminal/strata_control/engine_update.py:423-424`）。モジュール冒頭の説明は失敗時も 8 と読めるが、現行コードは 0 のときだけ 8 に変える（`terminal/strata_control/engine_update.py:33-34`）。
- `--output json`/`jsonl` では `models.restarts` に `restarted` と `asked` が入り、`json` の `ok` は終了コード 0 のときだけ真になる。`jsonl` では再起動の各段階が `models` イベントとして流れる（`terminal/strata_cli/update_cmd.py:369-370`、`terminal/strata_control/engine_update.py:387-399`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:67-69` — `strata update` parser の `--stop-model` と `--start-again` の定義。
- `terminal/strata_cli/update_cmd.py:400-417` — 質問役の有無と、値を `ModelGate` へ渡す処理。
- `terminal/strata_cli/update_cmd.py:357-373` — `--check` の早期終了、更新実行、終了コードの返却。
- `terminal/strata_control/updater.py:395-401,2060-2074` — ダウンロード後の停止と、停止同意が必要な条件。
- `terminal/strata_control/engine_update.py:301-322,370-399` — 停止同意と再起動の質問・実行。
- `terminal/strata_control/engine_update.py:230-262` — 保存済み設定での再起動と失敗時の後始末。
- `terminal/strata_control/engine_update.py:404-425` — 再起動結果の反映と終了コード 8 の条件。
- 補助: `terminal/tests/terminal/test_update_with_model.py:234-247` — スクリプト指定と失敗後の旧 engine 再起動の確認。
