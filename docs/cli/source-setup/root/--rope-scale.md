# `--rope-scale`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などから同じ setup に渡される） |
| オプション | `--rope-scale` |
| 別名 | なし |
| 値 | 浮動小数点数 `F`。有限値かつ `F >= 1` |

## 役割

標準の Qwen3.8-Flash-Next 系モデルセットアップで、RoPE のコンテキスト拡張係数を指定します。セットアップは選択されたコンテキスト長と `--rope-scaling` の方式から最終設定を解決し、方式が有効な場合は `--rope-scaling` と `--rope-scale` を生成する run config のエンジン引数に記録します。エンジンはその設定をプロセス起動時に読み、RoPE 設定を確定します。

## 使い方

```sh
# Qwen3.8-Flash-Next を 384K context、YaRN、係数 1.5 で設定する
./setup.sh --family qwen --model Q2_0 --context 393216 \
  --rope-scaling yarn --rope-scale 1.5 --yes --no-start
```

この例では `--no-start` によりセットアップ完了後のモデル起動を省きます。セットアップ自体は実行され、run config と起動スクリプトを作成します。係数を省略すると、方式が有効であれば最終 context を学習済み長 `262144` で割った値（最低 `1`）が使われます。

## 値と既定値

- parser は `type=float` で変換し、既定値は `None`（未指定）です。数値変換に失敗する値は parser が拒否します（`terminal/setup.py:11457-11459`）。
- `resolve_rope()` は明示値が有限で `1` 以上かを検証します。`nan`、`inf`、`-inf`、`1` 未満はセットアップで拒否されます（`terminal/setup.py:9260-9273`）。
- 未指定時、拡張方式が有効なら `max(1, 最終context / 262144)` を係数にします。たとえば `393216` では `1.5`、`524288` では `2` です（`terminal/setup.py:9251-9257, 9263-9268, 9280, 9286`）。明示値は context の調整後も自動変更されず、そのまま使われます（`terminal/setup.py:9263-9268`）。
- 同じ引数を複数回渡した場合の特別な重複処理はありません。重複時の選択規則はこのソース調査では確認していません。

## 実行時の動作

- 選択 context が `262144` 以下の場合、`--rope-scale` を指定するには `--rope-scaling linear` または `--rope-scaling yarn` が必要です。方式の省略または `none` との組み合わせはセットアップエラーになります。方式を明示して係数を省略した場合は係数 `1` になります（`terminal/setup.py:9274-9280`）。
- context が `262144` を超え、方式が省略されている場合、対話セットアップは方式を尋ね、`yarn` を初期選択にします。`--yes` の非対話経路では質問を出さず、`resolve_rope()` が省略方式を `yarn` にします（`terminal/setup.py:12170-12183, 9260-9268, 9281-9286`）。
- context が `262144` を超えるときに `--rope-scaling none` を明示すると、標準セットアップは方式を黙って上書きせず拒否します（`terminal/setup.py:9281-9286`）。
- 有効な方式と係数は `[ok] rope scaling: ...` として表示され、`strata_control/setup_config.py` が `--rope-scaling <方式> --rope-scale <係数>` をエンジン引数へ追加します（`terminal/setup.py:12180-12188, 12521-12525`; `terminal/strata_control/setup_config.py:218-225`）。設定は `write_setup_config()` に渡され、既存のモデル設定が変更される場合は `.bak` を作成してから書き込みます（`terminal/setup.py:7715-7747, 12525-12527`）。
- エンジン側では明示係数がモデルファイル由来の係数より優先され、RoPE 設定は session 初期化前に確定されます。リクエスト単位の切替ではありません（`engine/src/program/generate.cpp:788-796, 5715-5717, 5752-5759`）。

## 適用条件と副作用

- この文書は `setup.py` の root parser が処理する標準セットアップ経路を対象にします。Qwen3.6 などの独自エンジン経路、および Hy4-Flash / Inkling-2-Mini の専用経路は別の処理へ分岐し、この引数を Flash-Next 用設定として使わない旨を警告します（`terminal/setup.py:9908-9910, 10328-10330, 12019-12025`）。
- 通常の macOS 経路は root parser を作る前に `metal/setup_mac.py` へ引数を転送します。索引の mac scope に `--rope-scale` はなく、macOS 側での受理・効果はこの root 文書の対象外です（`terminal/setup.py:9290-9294, 11434-11444`; `docs/cli/README.md:1725-1748`）。
- `--backend sycl` は通常のモデル設定処理より先に `sycl_setup()` へ分岐します。この分岐で `--rope-scale` が受理・適用されるかは調査範囲から確認できないため、標準経路と同じ動作とは扱いません（`terminal/setup.py:11635-11638`）。
- `--no-start` を付けない場合の起動時挙動はこのオプション自体が決めるものではありません。ここで確認できる副作用は、setup が run config と起動スクリプトを生成し、RoPE 引数を設定に保存することです。

## 出力とエラー

- 数値へ変換できない値は `argparse` の型変換で拒否されます（parser 定義: `terminal/setup.py:11457-11459`）。
- 有限値でない、または `1` 未満の値、および context と方式の不整合は `resolve_rope()` が `ValueError` にし、呼び出し元が `fail()` に渡します。`fail()` は `[X]` と停止案内を表示し、error event を出して終了コード `1` で終了します（`terminal/setup.py:9272-9286, 12180-12183, 1049-1056`）。
- 設定が有効で拡張方式がある場合は方式・係数とその由来を `[ok]` 行に表示します。最終 context が学習済み長以下で方式なしの場合は、`resolve_rope()` が `(None, None)` を返すため、この `[ok] rope scaling` 行は出ません（`terminal/setup.py:9278-9280, 12184-12188`）。

## 根拠

- `terminal/setup.py:11444-11459` — root parser と `--rope-scale` の型・既定値。
- `terminal/setup.py:9251-9286` — 自動係数、明示値の検証、方式との組み合わせ、学習済み context 外の解決。
- `terminal/setup.py:12170-12188` — 対話時の方式選択、解決呼び出し、エラー処理、表示。
- `terminal/setup.py:9908-9910, 10328-10330, 12019-12025` — 独自セットアップ経路での警告と分岐。
- `terminal/setup.py:7715-7747, 12521-12527`; `terminal/strata_control/setup_config.py:218-225` — run config 生成とエンジン引数への保存。
- `engine/src/program/generate.cpp:788-796, 5715-5717, 5752-5759` — エンジンの係数既定・優先順位・プロセス設定。
- `terminal/setup.py:9290-9294, 11434-11444, 11635-11638`; `docs/cli/README.md:1725-1748` — macOS / SYCL の委譲境界。

調査は上記 commit のソースを対象に行い、CLI 実行、build、GPU 実行、性能測定、テストは行っていません。セットアップから分岐する SYCL 側および macOS 専用 parser での本オプションの扱いは、この root scope から確定できません。
