# `strata launch --mtp`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | `on` または `off` |

## 役割

モデルの MTP draft layer を使うかどうかを、この launch の設定として指定する。`off` は起動構成に無効状態を記録して MTP 用 engine 引数を除き、MTP を使わずに起動する。`on` は保存済みの無効状態を上書きして有効にする。MTP は通常の draft に使うモデル内の補助レイヤーであり、`--drafting` が DFlash2 を選ぶ場合の DFlash2 drafter とは別の設定である（`strata_cli/launch/cmd.py:98-104`、`strata_cli/launch/settings.py:96-99`、`strata_control/draft_layer.py:1-18`）。

## 使い方

```sh
# 変更を加えず、MTP を使わない場合の計画を表示する
strata launch --plan --model iq3_xxs --mtp off

# モデルを MTP なしで起動する
strata launch --model iq3_xxs --mtp off --no-tui

# 保存済み preset の MTP を有効にして起動する
strata launch --preset "IQ3_XXS 128K" --mtp on
```

## 値と既定値

- 値は `on` / `off` の二択。parser の変換関数は前後の空白を除き小文字化してから候補と照合するため、たとえば `ON` も `on` として受理される（`strata_cli/launch/cmd.py:35-43,98-100`、候補定義は `strata_cli/launch/settings.py:28`）。
- 省略時の parser 値は `None`。したがって、preset があればその値を引き継ぎ、そうでなければ既存のモデル設定に従う。新規セットアップでは既定で MTP が有効になる（`strata_cli/launch/cmd.py:206-211,245-246`、`strata_cli/launch/settings.py:98`、`setup.py:9471-9474`）。
- `--mtp` の値を省略した場合や `yes` など候補外の値を指定した場合は argparse が拒否する。誤った値では候補一覧と近い値の提案を含む usage error になり、終了コードは 2（`strata_cli/launch/cmd.py:35-43,98-100`、`strata_cli/cli.py:2256-2265`）。
- 同一コマンドで複数回指定した場合の個別検証はありません。argparse の通常の単一値引数として処理され、後に指定した値が残ります（登録は `strata_cli/launch/cmd.py:98-100`）。

## 実行時の動作

- CLI 値は preset の設定に重ねて `LaunchSettings.mtp` に入る（`strata_cli/launch/cmd.py:206-211,245-246`）。
- `off` の場合、launch 用 config に `"mtp": false` を設定し、MTP が選ばれている場合の engine 引数から `--mtp`、`--spec-min-p`、`--batch-mtp` とその値を取り除く。server は各 engine 起動時にも `"mtp": false` を適用し、engine 引数に MTP 用フラグが残っていれば除去する（`strata_cli/launch/runner.py:495-512`、`strata_control/draft_layer.py:25-56`、`serve/server.py:3934-3940`）。
- `on` の場合、launch 用 config に `"mtp": true` を書き、保存済みの `false` を引き継がない（`strata_cli/launch/runner.py:497-502`）。ただし `--drafting off` が同時に指定されると `drafting off` 側も MTP を無効化する（`strata_cli/launch/runner.py:495-502`）。
- `--drafting dflash2` との併用では、MTP layer と DFlash2 drafter は別々に扱われる。launch のセットアップ引数では DFlash2 が選択されたとき `--drafter dflash2` を渡し、`--mtp off` なら MTP layer を fetch しない。engine 起動時も DFlash2 用の選択引数がある場合は、MTP layer の引数除去条件から除外される（`strata_cli/launch/runner.py:944-952`、`serve/server.py:3934-3940`）。選択の詳細は [`--drafting`](--drafting.md) を参照。
- 初回モデル設定などで helper files が必要な launch では、`--mtp off` により MTP のダウンロード計画からも MTP が除外される。指定がなく、別の drafter が選ばれていない場合は、必要なモデル family で MTP が計画に含まれる（`strata_cli/launch/modelstate.py:121-126,143-160`、`strata_cli/launch/runner.py:2261-2283`）。セットアップに渡す値は `qwen`、`swift`、`coder`、`unsloth`、`gyro` family に限られ、それ以外の family には渡されない（`strata_cli/launch/modelstate.py:80-83`、`strata_cli/launch/runner.py:944-950`）。
- launch はモデル設定を準備した後、今回の起動用 config を作って保存し、その設定で server を起動する。オフライン等で必要な MTP を fetch できない場合、通常の MTP 選択では launch は停止せず、MTP なしで続行する経路がある（`strata_cli/launch/runner.py:2432-2455,2543-2581`）。

## 適用条件と副作用

- `off` は MTP の重み・draft head を使わず、利用可能 VRAM と RAM を減らす代わりに、MTP を使う場合より生成が遅くなると CLI の説明にある。数値での効果はこの文書では再測定していない（`strata_cli/launch/cmd.py:98-100`、`strata_control/draft_layer.py:8-18`）。
- 明示した `on` / `off` は launch の設定に反映される。`off` はセットアップが書き戻す `--mtp` 引数より優先され、次回以降の engine 起動でも反映される。セットアップが再実行されるモデルでは、`--mtp off` / `--mtp on` も `setup.py` に渡され、モデルの run config に `mtp` の真偽値が記録される（`strata_cli/launch/runner.py:497-512,944-950`、`setup.py:9471-9474`、`strata_control/setup_config.py:528-538`、`serve/server.py:3934-3940`）。
- MTP が既に有効なモデルに対する `--plan` は、実行計画を表示して変更しない。一方、通常の launch はモデル設定の確認・取得、起動用設定の保存、engine/server 起動を行う（`strata_cli/launch/cmd.py:14-26`、`strata_cli/launch/runner.py:2543-2581`）。

## 出力とエラー

- 有効化・無効化時のセットアップ出力は、`the draft layer (MTP) is on` または `the draft layer (MTP) is off for this model` とする。off で engine 引数を除いた場合は、取り除いたフラグ名も出力に含む（`strata_control/setup_config.py:528-538`）。
- server 起動時に既存 run config の `mtp` が `false` で MTP 引数も残っていれば、`"mtp": false - starting without the draft layer (...)` を標準出力へ出す（`serve/server.py:3934-3940`）。
- 無効値は parser の usage error となり、終了コード 2（`strata_cli/launch/cmd.py:35-43,98-100`、`strata_cli/cli.py:2256-2265`）。MTP の取得失敗時は、オフラインの場合を含めて launch が続行する fallback が実装されている。全ての失敗条件や外部取得処理の詳細はこのオプションの parser だけからは確定できない（`strata_cli/launch/runner.py:2432-2455`）。

## 根拠

- `strata_cli/launch/cmd.py:35-43,73-80,98-100` — `strata launch` parser の option scope、値の正規化・validation、既定値未指定。
- `strata_cli/launch/settings.py:28,81-99,124-137` および `strata_cli/launch/cmd.py:206-211,245-246` — 値候補、設定表現、preset への上書き。
- `strata_cli/launch/runner.py:470-513,928-987` — launch config への適用、セットアップへの引数転送と family 条件。
- `strata_cli/launch/modelstate.py:80-83,121-160` および `strata_cli/launch/runner.py:2261-2283` — helper family と download plan 上の扱い。
- `strata_control/draft_layer.py:1-56`、`strata_control/setup_config.py:528-538`、`setup.py:9471-9478`、`serve/server.py:3882-3940` — MTP flag 除去、setup config への保存、server 起動時の適用。
- `strata_cli/launch/runner.py:2432-2455,2543-2581` — 不足 drafter の fallback と launch 実行順。
