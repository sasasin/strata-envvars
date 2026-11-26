# `--no-quiet-check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--no-quiet-check` |
| 別名 | なし |
| 値 | 取らない。指定すると真になるフラグ |

## 役割

自動チューニングの各エンジン計測を始める前に行う「他の Strata エンジンが動いていないこと」と「CPU が高負荷でないこと」の確認・待機を無効にします。別のエンジンが動いている PC や CPU が忙しい PC でも待ち時間を省いて計測を進めたい場合に使えます。通常は指定せず、計測前の静穏確認を有効にします（`terminal/strata_cli/tune_commands.py:45`、`terminal/strata_control/autotune.py:70-72,252-275`）。

## 使い方

```sh
strata tune auto <モデル・プロファイル・JSON設定> --no-quiet-check
```

`target` は `strata tune auto` の必須位置引数です。計画だけを表示する `--plan` と併用した場合は、計画を返して終了するため、計測前の確認処理自体は実行されません（`terminal/strata_cli/tune_commands.py:27-28,349-353`）。

## 値と既定値

値は不要です。`argparse` の `store_true` フラグであり、未指定時は `False`（静穏確認を行う）、指定時は `True` です。parser に独自の値検証はありません。値を付けた形式は受理されず、複数回指定しても真偽値が変わるだけで効果は増えません（`terminal/strata_cli/tune_commands.py:21-49`）。

## 実行時の動作

`strata tune auto` はこの値を `check_busy=not a.no_quiet_check` として tuner に渡します。通常は各エンジン起動の直前に、別の Strata エンジンの稼働を調べ、該当しなければ CPU 使用率を 1 秒間測定します。CPU 使用率が 25% を超える場合も待機理由になります。Linux と Windows では CPU 使用率を読み取る実装があります。値を読み取れない場合や他の OS では CPU 判定は `None` となり、その判定だけでは待機しません。待機条件に該当すると 10 秒間隔で再確認し、最大 300 秒待った後は計測を続行して「PC が忙しい状態で測定した」旨を結果ノートに加えます（`terminal/strata_control/autotune.py:70-72,252-276`、`terminal/strata_control/tune_machine.py:201-229,232-255`）。

このフラグを指定すると、その静穏確認・待機ループをスキップします。チューニングの計測や結果保存の設定を変えるものではありません。計測前のメモリガードはこの確認の後に別途実行されるため残ります。`--gpu-lock` または `STRATA_TUNE_GPU_LOCK` でロック先が指定されていれば、そのロックも各エンジン実行に使われます（`terminal/strata_control/autotune.py:327-340`、`terminal/strata_cli/tune_commands.py:43-45,185-189,342-345,371-384`）。したがって、このフラグはメモリ不足時の開始拒否や設定済みロックの待機を無効にはしません。

デスクトップ側の headless チェックは、別の環境変数 `STRATA_TUNE_NO_QUIET_CHECK=1` が設定されている場合にこの CLI フラグを引数へ追加します。これは `strata tune auto` の parser による環境変数既定値ではなく、デスクトップの呼び出し側による引数変換です（`app/host/server/native-autotune.mjs:97-101`）。また、同じオプション名は `strata presets recheck` にも別スコープで定義されています。この文書は索引上の `strata tune auto` 用です（`terminal/strata_cli/tune_commands.py:88-96`、`docs/cli/README.md:736-755`）。

## 適用条件と副作用

効果があるのは通常の自動チューニングで実際にエンジン計測を開始するときです。`--plan` は計画を表示して終了するため適用されません。静穏確認を省くと、他の Strata エンジンの実行中や CPU 負荷中にも計測する可能性があり、比較結果へ影響し得ます。ソースは待ち時間を省略する動作を示しますが、このフラグによる性能改善量や計測値への定量的な影響は規定していません（`terminal/strata_cli/tune_commands.py:349-353,383-387`、`terminal/strata_control/autotune.py:252-276`）。

## 出力とエラー

このフラグ固有のエラー経路はありません。指定時に静穏確認の「Waiting for the PC to be quiet」進捗は出ません。通常の human 出力では進捗を stderr に出し、JSON 出力では進捗行を出さず最終結果を stdout に出します（`terminal/strata_cli/tune_commands.py:358-369,421-425`）。対象設定の読込、未対応モデル、RAM 条件などによる失敗は別の処理であり、このフラグでは回避されません（`terminal/strata_cli/tune_commands.py:314-338`、`terminal/strata_control/autotune.py:327-340`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-49` — `strata tune auto` parser とフラグ宣言。
- `terminal/strata_cli/tune_commands.py:342-345,349-353,371-387` — tuner への真偽値の受渡し、`--plan` の早期終了、計測実行。
- `terminal/strata_control/autotune.py:70-72,252-276,327-340` — 既定値、静穏待機条件、待機後の継続、別のメモリガード。
- `terminal/strata_control/tune_machine.py:201-229,232-255` — CPU 使用率と他エンジンの検出。
- `app/host/server/native-autotune.mjs:97-101` — デスクトップ呼び出し側の環境変数から CLI 引数への変換。
- `docs/cli/README.md:736-755` — `strata tune auto` の索引リンクとコマンド階層。
