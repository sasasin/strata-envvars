# `--kv-streaming`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` のセットアップ |
| オプション | `--kv-streaming` |
| 別名 | なし |
| 値 | `auto`、`on`、`off` |

## 役割

長いコンテキストで KV キャッシュをホスト RAM に置き、attention が使う窓だけを GPU の VRAM に保持する設定を、セットアップが生成する実行構成に反映します。VRAM に余裕を作ってモデルの expert cache に回せますが、KV の RAM 使用量が増えます。実際に有効にするとセットアップはエンジン引数へ `--kv-resident 32768` を追加します（`terminal/strata_control/setup_config.py:297-314`）。エンジン側はこの指定で各 QSA 層の KV をストリームし、指定したセル数を VRAM に保持します（`engine/src/program/generate.cpp:1234-1235,3907`）。

## 使い方

```sh
# セットアップ時に RAM 判定を上書きして有効化する。構成を書き、モデルは起動しない。
python setup.py --setup --kv-streaming on --yes --no-start

# RAM 判定に任せる（省略時と同じ）。
python setup.py --setup --kv-streaming auto --yes --no-start

# 明示的に無効化する。
python setup.py --setup --kv-streaming off --yes --no-start
```

実行場所にある `setup.py` を使う例です。セットアップは構成ファイルと起動スクリプトを書きます。`--no-start` はモデルの起動を省きますが、セットアップやダウンロードを省略する指定ではありません（`terminal/setup.py:11524-11525,12521-12527,12555-12562`）。

## 値と既定値

- parser は `auto`、`on`、`off` のみを受け付け、既定値は `auto` です。別名はありません（`terminal/setup.py:11598-11600`）。それ以外の値は `argparse` の choices 検証で受理されません（同: `11444,11598-11606`）。
- ストリーミング用 RAM の概算は、KV の種類とコンテキスト長から計算します。非 budget モデルでは「モデル RAM + KV RAM + 1 GB」と「expert arena + headroom + KV RAM」の小さい方、budget モデルでは `max(16 GB, headroom + KV RAM + 4 GB)` が自動判定の閾値です（`terminal/setup.py:7068-7091`）。
- KV RAM 概算は `ctx × 13 × KV_CELL_BYTES[kv] / 1e9` です。ソースコメントの目安は int8 で約 13.7 KB/トークン、K8V4 で約 10.6 KB、4-bit で約 7.5 KB です（`terminal/setup.py:7068-7071`; `terminal/strata_control/setup_config.py:297-304`）。

## 実行時の動作

| 値 | セットアップの判断 |
| --- | --- |
| `auto` | コンテキストが 65,536 以上で、計算した RAM 閾値を満たすと有効化します。閾値を満たさなければ KV は VRAM に残ります。 |
| `on` | 65,536 以上なら RAM 閾値を超えていても有効化します。RAM 不足時はページングまたはメモリ不足の可能性を警告します。65,536 未満では有効にならず、その旨を警告します。 |
| `off` | 自動判定の結果にかかわらず無効化します。 |

この分岐は `terminal/strata_control/setup_config.py:301-332` にあります。Windows Subsystem for Linux (WSL) では 65,536 以上のコンテキストでも常に無効です。`on` を指定しても WSL での制限と警告が表示されます（同: `305-309`）。また、セットアップが既存の実行構成を整える経路でも WSL 上の `--kv-resident` を削除して構成を書き直します（`terminal/setup.py:8288-8295`）。

ソース内の判定説明には差があります。`terminal/setup.py:7094-7104` の `kv_streaming_wanted` は、budget モデルかつ VRAM が 16.5 GB 以下なら 32,768 から有効化可能としています。一方、セットアップが実際に構成引数へ `--kv-resident` を追加する `terminal/strata_control/setup_config.py:312-313` は、モデル種別にかかわらず 65,536 以上を条件にしています。この文書では構成を書き出す側の分岐を実際の効果として記載しました。両方の条件が異なる理由はこの範囲のコードから確認できません。

有効時は `--kv-resident 32768` を生成引数に加えます。`--kv` の種類で KV の RAM 見積もりが変わり、`--context` の値が判定対象の長さになります（`terminal/setup.py:11452,11460-11462`; `terminal/strata_control/setup_config.py:301-314`）。budget があり、layer split でないモデルでは、明示的な `--resident-budget-gib` がない場合、セットアップは KV の RAM 分を差し引いて budget を計算します。明示 budget がある場合に KV RAM がその外に加算されると警告する場合があります（`terminal/strata_control/setup_config.py:319-326`）。

生成された構成は一時ファイルへ書いてから置換され、起動スクリプトも作成されます。通常はその後モデルを起動しますが、`--no-start` なら起動せず終了します（`terminal/setup.py:7531-7537,12521-12527,12555-12562`）。

## 適用条件と副作用

- `--kv-streaming` は `terminal/setup.py` の root parser にあります。通常の macOS セットアップ経路は parser の作成前に `metal/setup_mac.py` へ委譲されるため、この文書の説明は通常の macOS 経路には適用しません（`terminal/setup.py:11416-11417,11436-11437`）。索引でも macOS は別の `source-setup/mac` スコープです。
- `on` は RAM 判定を飛び越えるため、推定必要量を満たさない PC では警告後も設定が保持されます。負荷時のページングやメモリ不足の可能性があります（`terminal/strata_control/setup_config.py:312-318`）。
- `auto` で RAM が足りない場合、あるいは `off` の場合は KV キャッシュを VRAM に残し、その結果 cached experts が少なくなる旨を表示します（同: `310-330`）。
- セットアップの注記は `[ok]` または `[!]` として標準出力に出ます（`terminal/setup.py:997-1000,1039-1047`）。無効値は parser の検証で拒否されます。その他のエラー終了条件はセットアップ全体に依存し、このオプション固有のものとしては確認できません。

## 根拠

- parser の選択肢・既定値: `terminal/setup.py:11598-11600`。
- RAM 使用量と自動判定の閾値計算: `terminal/setup.py:7068-7104`。
- セットアップ構成への反映、RAM 判定、WSL と明示指定時の警告: `terminal/strata_control/setup_config.py:297-332`。
- エンジンへ渡す `--kv-resident` とその値の説明: `engine/src/program/generate.cpp:1234-1235,3907`。
- 構成の書き込み、起動スクリプト作成、起動省略: `terminal/setup.py:7531-7537,12521-12527,12555-12562`。
- 既存構成から WSL 上のストリーミング指定を除去: `terminal/setup.py:8288-8295`。
