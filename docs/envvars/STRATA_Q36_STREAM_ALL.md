# `STRATA_Q36_STREAM_ALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6-35B-A3B 用 CUDA/HIP エンジンの hybrid streamed prompt path で、GPU に置かれた expert も含めて各対象層の expert weight 全体をホストメモリから staging buffer へ転送するかを切り替える。設定されていない通常経路では、常駐 expert の連続区間は VRAM から device-to-device、非常駐区間はホストから転送する。ただし GPU 常駐 slot が expert の半数未満の層では、変数が未設定でも層全体をホストから一括転送する。設定するとこの半数判定を越えて常に全体をホストから転送するため、常駐 expert についてもホスト側コピーを使う。重みの転送元とコピーのまとめ方を変える設定であり、これだけから生成結果や速度の変化は断定できない。読み取りは `Engine::stream_kick` 内の `std::getenv` で行う（`engine/src/qwen35/q36_engine.cu:3120-3148`）。

## 値と判定

文字列の内容や数値は parse せず、`std::getenv(...) != nullptr` の設定有無だけを判定する。環境変数が未設定なら `all == false`、空文字を含め何らかの値が設定されていれば `all == true` となる。従って `1`、`0`、`true`、`false`、`0anything` はすべて有効（有効化）で、空文字も有効。大文字小文字、空白、数値妥当性の検査はない。これは値による ON/OFF ではなく、存在による切替である（`engine/src/qwen35/q36_engine.cu:3127`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `stream_kick` が実行される経路 | `all` は false。半数未満の slot がある層は別条件で全体をホストからコピーし、それ以外は常駐・非常駐の連続範囲ごとに転送 | 空文字を含む任意の設定値。`all` が true になり、層全体をホストメモリからコピー | なし（unset のみ無効） |

## 有効になる条件

- `strata-q36` の Qwen3.6-35B-A3B (`qwen35moe`) エンジンを使う必要がある。このエンジンは他のモデル family を拒否する（`engine/src/qwen35/q36_engine.cu:1387-1395`）。
- hybrid placement が必要で、少なくとも一部の対象層に GPU slot がないこと。すべての expert が VRAM に収まる場合は `place_experts` が全常駐経路で戻り、streaming は使われない（`engine/src/qwen35/q36_engine.cu:1810-1815,4328-4335`）。VRAM に収まらない場合の hybrid placement は `STRATA_Q36_CPU_POOL` 定義の build に限られる（`engine/src/qwen35/q36_engine.cu:4337-4345`）。
- メインモデルの hybrid 経路で `use_pf` が有効であり、forward の行数 `T` が `hybrid_t` より大きい必要がある。この条件で `forward` が hybrid 層の sequence を作って streaming を始める。層で staging weights を実際に使う prompt 分岐には、さらに `T > kGemmT` が必要で、そこでは `stream_take` が staging buffer を返す（`engine/src/qwen35/q36_engine.cu:3030-3034,2902-2915,2954-2955`）。`use_pf` が無効なら `hybrid_t` は `tmax` にされ、streamed prompt path は使われない（`engine/src/qwen35/q36_engine.cu:4346-4350`）。
- staging 用 VRAM が足りず計画または確保が fallback した場合も `use_pf=false` となり、設定があってもこの分岐は実行されない（`engine/src/qwen35/q36_engine.cu:4370-4376,4494-4501`）。
- 通常の小さい hybrid batch（`T <= hybrid_t`）は `hy_rows` 経路で expert slot / CPU pool を使い、streaming copy の分岐に入らない。MTP-only hybrid も `main_hybrid` が false なので、この streamed path の対象外（`engine/src/qwen35/q36_engine.cu:1805-1815,2902-2915,3030-3034,4344-4348`）。`--prefill` / `--chunk` 等は chunk と placement 条件に関係するが、この環境変数自体に対する CLI 上書きはない（`engine/src/qwen35/q36_engine.cu:5348-5364`）。

## 実行時の詳細

`forward` は `main_hybrid && T > hybrid_t && use_pf` のとき、GPU slot が全 expert に満たない各 main layer の index を sequence に入れる。`stream_begin` は先頭最大2層のコピーを先行開始する。各 `stream_kick` は staging buffer の前回利用完了を event で待ち、環境変数を関数内 `static const bool` として初回呼び出し時に一度評価する。以後そのプロセスでは値の変更は反映されない（`engine/src/qwen35/q36_engine.cu:3030-3034,3114-3129`）。

`all` が true、または `2 * L.n_slots < n_expert` の場合は、`L.hblobs` から `L.stride * n_expert` byte を staging buffer へ `cudaMemcpyAsync(..., cudaMemcpyHostToDevice, cst)` でコピーする。それ以外では expert index を走査し、VRAM slot の連続区間を device-to-device、slot がない連続区間を host-to-device でコピーする。転送完了 event を記録し、`stream_take` が compute stream 上でその event を待って staging buffer を返す。層処理後に `stream_done` が利用完了 event を記録し、必要なら2つ先の層のコピーを開始する（`engine/src/qwen35/q36_engine.cu:3120-3168,2954-2955,2996`）。

この変数はコピー分岐のみに使われ、CLI 引数や別の環境変数との値優先順位はない。placement や `use_pf`、chunk の条件が不成立なら読み取り・効果ともに streamed path に現れない。

## ログと測定値

この変数の判定または全 expert の host-to-device コピーを直接知らせるログはない。stream sequence と event の順序がずれた場合は stderr に `strata-q36: the expert stream is out of step (layer %d)` を出して `exit(1)` する（`engine/src/qwen35/q36_engine.cu:3154-3158`）。ソースコメントには RTX 3060、UD-Q4_K_XL、256 expert 中37 slot、pp2048 における全体コピー1970対区間コピー1540という比較が記されているが、測定方法や回数などの条件はこの箇所にないため、一般的な性能値とは扱わない（`engine/src/qwen35/q36_engine.cu:3130-3132`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1387-1395` — 対象モデル family の確認。
- `engine/src/qwen35/q36_engine.cu:1805-1815,3030-3034,3114-3168` — hybrid/stream 条件、cache、copy と event の順序。
- `engine/src/qwen35/q36_engine.cu:2902-2915,2954-2955,2996` — prompt 層での staging buffer 利用。
- `engine/src/qwen35/q36_engine.cu:4328-4350,4370-4376,4494-4501` — slot 配置、build 条件、streaming fallback。
- `engine/src/qwen35/q36_engine.cu:5348-5364` — CLI 引数処理。
