# `strata tune auto --no-quiet-check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--no-quiet-check` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `True` |

## 役割

自動チューニング中、測定を始める前に他の Strata エンジンや CPU の混雑が解消するまで待つ処理を無効にします。測定を早く始めたい場合に使えますが、同時稼働エンジンや CPU 負荷が測定値に影響し得ます。

## 使い方

```sh
strata tune auto "My profile" --no-quiet-check
```

`target` には保存済み profile 名または run configuration の JSON を指定します。この文書の対象は `strata tune auto` の parser scope です。`strata presets recheck` にも同じ綴りの別スコープの parser 定義があります（索引は [`strata-terminal` 節](../../../README.md#strata-terminal)）。

## 値と既定値

値や引数は不要です。省略時は `argparse` の `store_true` の既定値により無効（`False`）、指定時は有効です。繰り返し指定しても真偽値のままで、値の validation はありません。`strata tune auto` の parser は `strata_cli/tune_commands.py:20-46`、フラグ宣言は同 `:41` です。

## 実行時の動作

CLI は `--no-quiet-check` の否定を `autotune.Options.check_busy` に渡します（`strata_cli/tune_commands.py:194-197`）。既定では各 engine run の直前に、GPU lock が設定されている場合はその lock を取得した後、混雑確認をします（`strata_control/tune_session.py:443-450`）。確認対象は別の Strata エンジンと CPU 使用率です。CPU 使用率が 25% を超えると混雑扱いにし、通常は 10 秒間隔で最大 300 秒待ちます。待機上限に達してもその時点で測定へ進み、混雑理由を結果の note に記録します（`strata_control/autotune.py:66-68,242-266`）。

このフラグを指定すると `_wait_for_quiet()` が直ちに戻るため、別エンジンや CPU 使用率を理由とする待機は行いません（`strata_control/autotune.py:242-245`）。同じ tuner の測定すべてに適用され、基準設定の測定と候補設定の試行も対象です（同 `:303-324,379-386`）。

## 適用条件と副作用

- 混雑確認だけを無効化します。メモリー空き容量の確認・待機は別の `_ram_guard()` で行われ、このフラグでは無効になりません（`strata_control/autotune.py:311-319`）。
- `--gpu-lock` を指定した場合の lock 取得も維持されます。未指定時は `STRATA_TUNE_GPU_LOCK` 環境変数の値が既定値として使われます（`strata_cli/tune_commands.py:39-42,217-219`）。
- 混雑した状態でもチューニング用 engine を起動して測定するため、ほかの処理との競合で結果が揺れたり、改善を正しく判定できなかったりする可能性があります。チューナーは測定ノイズや速度の変動を評価し、判定不能なら `inconclusive`（JSON の `busy_pc`）として「変更なし」を返す経路があります（`strata_control/autotune.py:621-647,353-359`）。
- フラグ自体は設定保存の可否を変更しません。結果が `improved` または `default_confirmed` で `--no-save` が指定されていなければ、preset を作成します（`strata_cli/tune_commands.py:246-251`）。

## 出力とエラー

このフラグ専用のメッセージや失敗コードはありません。既定動作では待機中に進捗メッセージを出しますが、このフラグでその待機がなくなります（`strata_control/autotune.py:251-257`）。JSON 出力は `--output json` が選択されたときの通常の tuner 結果形式です（`strata_cli/tune_commands.py:178-179,257-261`）。

混雑確認をしないこと自体はエラーとして扱われません。チューニングは通常どおり完了・保存判定まで進みます。混雑による測定の影響をどのような理由コードに分類するかは実測結果に依存し、フラグ単独で固定されません。

## 根拠

- `strata_cli/cli.py:486,1652-1653` — `tune auto` parser の登録と `tune_commands.auto` への振り分け。
- `strata_cli/tune_commands.py:20-46` — `auto` の引数、フラグの宣言と既定値。
- `strata_cli/tune_commands.py:194-197` — CLI 値から `Options.check_busy` への反映。
- `strata_cli/tune_commands.py:217-227` — session 作成時の lock と tuner の構築。
- `strata_control/autotune.py:242-266,303-324` — 混雑確認の条件・検査内容・待機・engine 起動前の適用。
- `strata_control/tune_session.py:443-450` — lock 取得後に事前確認を実行。
- `strata_control/autotune.py:621-647` — 測定の不確実性や候補未試行時の結果。
- `strata_cli/tune_commands.py:246-261` — preset 保存条件と出力・戻り値。
