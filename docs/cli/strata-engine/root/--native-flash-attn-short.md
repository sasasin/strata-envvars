# `--native-flash-attn-short`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--native-flash-attn-short` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

QSA 層の decode attention を、短い context 向けの診断用 pinned vector-attention CUDA kernel に切り替えます。通常の split-K decode attention との比較・検証用スイッチです。実行速度や精度が改善するという保証・測定結果をこのオプションの仕様としては確認していません。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --max-context 256 --native-flash-attn-short
```

`--pack` はモデル pack の場所、`--tokens` は事前 token 化済み prompt の token ID 列です。実行には有効な pack と、そのモデル・ビルドに合う GPU 実行環境が必要です。

## 値と既定値

- 値は不要です。parser はこの引数を見つけると bool を `true` にします。別名はありません。既定値は `false` です（`src/program/generate.cpp:447,2493`）。
- 複数回指定しても同じ bool を `true` にするだけで、追加の効果はありません（`src/program/generate.cpp:2493`）。
- フラグに値を続けても値として消費されません。未知の引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。
- `--max-context` の既定値は 4096 なので、このフラグだけを追加すると上限検査で拒否されます。`--max-context` を 256 以下に指定してください（既定値: `src/program/generate.cpp:422`、引数処理: `src/program/generate.cpp:2445`、上限検査: `src/program/generate.cpp:3378-3380`）。
- `--max-context` は prompt token 数と `--max-new` の合計を収容できなければ、別の通常検査でも拒否されます（`src/program/generate.cpp:3970-3974`）。

## 実行時の動作

- 初期化時に値を core layer の process-wide switch へ渡します（`src/program/generate.cpp:3926-3933`、setter と保存先: `src/core/layer.cpp:100-102,203`）。QSA 層では、通常の fast decode path が有効で dump がない場合の `qsa_decode_attn_step` ではなく、K/V gather 後に `native_flash_attn_short_step` を呼びます（`src/core/layer.cpp:1264-1290`）。
- 専用 kernel は Q=24 heads、KV=2 heads、head dimension 256、index block 4、selection top-k 256 以上、capacity 256 以上、最大 context 1〜256、明示 stream を要求します。満たさない kernel 呼び出し条件は `invalid_argument` になります。kernel は Q/K/V、step、出力、status、任意 mask の buffer alignment と重なりも検証します（`src/kernels/cuda/native_flash_attn.cu:192-210`）。このファイルは CMake の CUDA/HIP 用 source list に含まれます（`CMakeLists.txt:398-410,536-545`）。
- 実際の QSA decode step は `width == nkv`、`pos == width - 1`、`nbid == width / 4` かつ `1 <= width <= max_context` を要求します。不正 step では kernel が status を `UnsupportedStep` にし、出力を NaN にします（`src/kernels/cuda/native_flash_attn.cu:56-64`、status 値: `include/strata/kernels/native_flash_attn.hpp:8-26`）。
- kernel が書いた status は、生成 token の readback 後に QSA state ごとに検査されます。非ゼロなら `native attention status <値> at QSA layer <層>, position <位置>` を stderr に出し、終了コード 1 で停止します（`src/program/generate.cpp:16039-16057`）。status storage と pinned host-side step 領域は QSA state に確保されています（`src/core/layer.cpp:892-902`）。
- `--no-fast-attn` は通常の fast path を外しますが、このフラグが有効な場合は分岐後も専用 kernel を選びます（`src/program/generate.cpp:2783,3926-3933`、`src/core/layer.cpp:1264-1290`）。
- セッション fingerprint にも有効状態が記録されます（`src/program/generate.cpp:9450-9455`）。

## 適用条件と副作用

- CLI は `--max-context > 256` を終了コード 2 で拒否します。また `--gpu-only-full`、`--graph-only`、`--gpu-stages` のいずれかと併用すると、status 検証に通常 decode loop が必要なため拒否します。どちらも stderr に理由を出します（`src/program/generate.cpp:3378-3385`）。
- `src/core/layer.cpp` は state の `max_cells` が 1〜256 であること、status 領域が存在することも呼び出し前に検査します（`src/core/layer.cpp:1277-1285`）。対象 kernel の shape 制約を満たさないモデルでは、kernel 自身の引数検査で失敗します（`src/kernels/cuda/native_flash_attn.cu:196-210`）。
- このオプションは QSA decode の attention 計算を切り替え、status 用 GPU/host buffer を使います。その他のファイル・ネットワーク操作を追加するコードは確認できません。対応モデル、GPU 世代ごとの実行成否・性能はソース調査だけでは確定できないため、ここでは断定しません。

## 根拠

- Parser、既定値、help 表示、CLI validation: `src/program/generate.cpp:422,447,849,2445,2493,3378-3385`
- switch 設定、attention 分岐、status readback: `src/program/generate.cpp:3926-3933,16039-16057`; `src/core/layer.cpp:100-102,203,1264-1290`
- CUDA kernel とその前提・status 処理: `src/kernels/cuda/native_flash_attn.cu:50-64,192-210`; `include/strata/kernels/native_flash_attn.hpp:8-34`
- 索引上のスコープ: `docs/cli/README.md:1128-1135,1213`

