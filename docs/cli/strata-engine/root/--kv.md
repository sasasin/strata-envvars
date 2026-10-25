# `--kv`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--kv` |
| 別名 | なし（値 `q4` は `q4_0` の互換表記） |
| 値 | `fp16`、`int8`、`q4_0`、`k8v4`。`q4` も受理され `q4_0` に正規化される |

## 役割

QSA 層の attention K/V cache の保存形式を選びます。値は起動時に検証され、エンジン内の QSA cache 状態へ設定されます。cache の形式により確保する GPU メモリ量と K/V の保存・読み出し処理が変わります。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --kv int8
```

## 値と既定値

- 省略時は `fp16` です。Options 構造体の初期値が `fp16` です。
- `fp16`: K/V を FP16 で保持します。
- `int8`: INT8 のコードと、64 値ごとの FP16 scale を使います。
- `q4_0` または `q4`: Hadamard 回転を伴う Q4_0 K/V 形式です。`q4` は内部で `q4_0` に置き換えられます。
- `k8v4`: INT8 K と回転済み Q4_0 V を組み合わせます。
- 値は大文字小文字を区別する文字列比較で検証されます。上記以外は受理されません。重ねて指定した場合、引数ループが同じフィールドを更新するため最後の値が使われます。
- 値を省略すると `--kv needs a value` を stderr に出して終了コード 2 になります。

## 実行時の動作

parser は値を `Options::kv` に格納し、validation 後に INT8、Q4、K8V4 の各 QSA cache 設定を切り替えます。QSA state 初期化では選択形式に応じて FP16 pool、INT8 コードと scale、Q4 pool、または K8V4 の K/V 用 pool を確保し、append 経路も形式に応じた処理を使います。

`STRATA_KV_ROT` が先頭文字 `1` の場合、`int8` の K/V にも Hadamard 回転を有効にします。このとき `--kv int8` なら stderr に opt-in の通知が出ます。`q4_0` は常に回転を使い、`k8v4` は K を INT8 のまま使って V のみ回転します。この環境変数は `--kv` の値そのものを上書きしません。

`k8v4` の draft MTP cache は通常の INT8 として初期化されます。`--kv-resident` が正値なら cache streaming も別途設定され、ヘルプでは `k8v4` と Q4 も streaming 対象とされています。

## 適用条件と副作用

形式設定は `qsa_state_init` が作る QSA state に反映されます。QSA state を持つモデル経路で cache のメモリ確保量と K/V append・attention 読み出し形式に影響します。QSA を持たないモデルでどのように扱われるかは、この調査では個別モデル実行まで確認していません。

`src/program/generate.cpp` は通常 parser に入る前に Qwen3.6 (`qwen35moe`) を専用実装へ振り分けます。この文書の `--kv` の受理・動作は `generate.cpp` の通常経路についての記述で、専用実装側の挙動は確認対象外です。

Q4_0 / K8V4 は量子化された K/V cache を使います。ソース help は Q4_0 を INT8 の半分のメモリ、K8V4 を cell あたり 816 B（INT8 は 1,056 B）と記述していますが、実際の確保量は QSA shape に依存します。これらの設定が精度・速度へ与える定量的な効果は、この調査では測定していません。

## 出力とエラー

- 不正値: `strata generate: --kv must be fp16, int8, q4_0 or k8v4` を stderr に出し、終了コード 2。
- 値の不足: `--kv needs a value` を stderr に出し、終了コード 2。
- `STRATA_KV_ROT=1` と `--kv int8` の組み合わせ: `strata generate: STRATA_KV_ROT=1: INT8 K/V through the Hadamard rotation (opt-in)` を stderr に出します。

## 根拠

- parser の既定値: `src/program/generate.cpp:486`
- help の値説明: `src/program/generate.cpp:827-832`
- 値の取得、欠落値エラー、重複時の代入経路: `src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2480`
- Qwen3.6 専用実装への parser 前振り分け: `src/program/generate.cpp:2393-2407`
- `q4` の正規化、許容値の検証、エラー終了と cache 設定: `src/program/generate.cpp:3186-3199`
- 量子化形式ごとの QSA state 設定と pool 確保: `src/core/layer.cpp:793-865`
- K8V4 の K/V append と Q4/INT8 の append 分岐: `src/core/layer.cpp:1207-1227`
- draft MTP が K8V4 時に INT8 cache を使う処理: `src/core/mtp.cpp:350-366`

本調査は上記 commit の checkout 内ソースを対象とし、ビルド済みバイナリ、全 backend/platform、Release 配布物との照合は行っていません。
