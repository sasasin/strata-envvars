# `setup.py --rope-scaling`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `terminal/setup.py` |
| オプション | `--rope-scaling` |
| 別名 | なし |
| 値 | `none`、`linear`、`yarn` のいずれか |

## 役割

Flash-Next のセットアップで、モデルが学習した 262,144 token を超える context を使う際の RoPE 拡張方式を選びます。指定値はセットアップが生成するモデル実行設定に `--rope-scaling` として記録され、以後の起動でエンジンに渡されます。`linear` と `yarn` は拡張方式、`none` は学習長を超える context では拒否される明示指定です（`terminal/setup.py:12170-12187`、`terminal/strata_control/setup_config.py:218-223`）。

## 使い方

```sh
# Flash-Next を 384K context、YaRN で設定する例
python terminal/setup.py --family qwen --context 393216 --rope-scaling yarn
```

このコマンドはセットアップを実行し、モデル設定や起動スクリプトを作成します。上の例は実行例であり、この調査では実行していません。

## 値と既定値

- parser は `none`、`linear`、`yarn` のみを受け付けます。値は必須で、別名や parser 上の既定値はありません（`terminal/setup.py:11452-11456`）。未指定時の方式はセットアップ経路で決まります。
- Flash-Next の最終 context が学習長以下なら、未指定または `none` は RoPE 拡張を設定しません。`linear` / `yarn` を明示すると、その方式が設定され、`--rope-scale` がなければ係数は `max(1, context / 262144)` です（`terminal/setup.py:9251-9257, 9274-9280`）。
- 最終 context が 262,144 を超え、方式を省略した場合、対話実行では `yarn` を初期選択にして `yarn` / `linear` を尋ねます。`--yes` では質問せず `yarn` が使われます（`terminal/setup.py:12170-12181`）。どちらの場合も、`--rope-scale` を省略すれば係数は最終 context ÷ 262,144（最低 1）です。
- 262,144 を超える context に明示的な `none` を指定すると拒否されます。方式を明示しても係数は自動計算されますが、併用する `--rope-scale` があれば、その値が使用されます（`terminal/setup.py:9260-9286`）。
- 無効な方式は parser の choices 検証で拒否されます。重複指定の個別検査は実装されていません（`terminal/setup.py:11453-11456`）。

## 実行時の動作

セットアップは解決した方式と係数を確認メッセージに表示し、実行設定の `args` に `--rope-scaling <方式> --rope-scale <係数>` を加えます。方式が `None`（未指定かつ学習長以下、または明示 `none` かつ学習長以下）の場合、この2引数は追加されません（`terminal/setup.py:12180-12188`、`terminal/strata_control/setup_config.py:218-225`）。生成設定は `cfg` の `args` として組み立てられ、セットアップが設定ファイルに書き込みます（`terminal/strata_control/setup_config.py:433-435`、`terminal/setup.py:12521-12527`）。

## 適用条件と副作用

- この設定処理で有効なのは Flash-Next のセットアップ経路です。Qwen3.6 および Hy4 の経路では、値が指定されていると Flash-Next 専用設定として警告します（`terminal/setup.py:9908-9910, 10328-10329`）。
- 通常の Apple Silicon Mac 経路は `setup.py` の parser より前に `engine/metal/setup_mac.py` へ引数を転送します。同スクリプトはこのオプションを解釈せず、未使用引数として警告します。Hy4 / Inkling-2-Mini 等の分岐はこの Mac 委譲を通らない場合があります（`terminal/setup.py:11434-11437`、`engine/metal/setup_mac.py:376-403`）。
- 既存のモデル設定が更新される場合、セットアップは変更前のファイルを `.bak` に保存してから新しい設定を書き込みます（`terminal/setup.py:7739-7747`）。

## 出力とエラー

- RoPE 拡張を設定した場合、方式・係数と、係数が自動算出か指定値かを `[ok]` メッセージで表示します（`terminal/setup.py:12184-12188`）。
- 学習長を超える context での明示 `none`、または拡張方式なしでの `--rope-scale` は `ValueError` となり、セットアップはエラーを表示して終了コード 1 で停止します（`terminal/setup.py:9272-9286, 12180-12183, 1049-1056`）。無効な方式の parser エラーは `argparse` の引数検証で処理されます。
- Mac 委譲経路では、この値は適用されず、「not used on a Mac」の警告対象です（`engine/metal/setup_mac.py:403-405`）。

## 根拠

- `terminal/setup.py:11444-11459` — `argparse` parser と値の choices、隣接する係数オプション。
- `terminal/setup.py:9251-9286` — 自動係数、学習長以下・超過時の解決規則と拒否条件。
- `terminal/setup.py:12170-12188` — 対話時の方式選択、`--yes` 時の既定、解決後の表示とエラー処理。
- `terminal/strata_control/setup_config.py:218-225, 433-435` — 解決した値のエンジン引数と実行設定への格納。
- `terminal/setup.py:9908-9910, 10328-10329` — 他モデル系統での未適用警告。
- `terminal/setup.py:11434-11437`、`engine/metal/setup_mac.py:376-405` — Mac への委譲と未使用引数の扱い。
- `terminal/setup.py:7739-7747` — 既存設定変更時のバックアップと書き込み。
