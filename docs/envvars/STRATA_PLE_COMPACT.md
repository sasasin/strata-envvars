# `STRATA_PLE_COMPACT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt prefill の PLE (Prompt Lookup Embedding) 行を、ホストで float に展開してから転送する代わりに、IQ4_NL の raw 行のまま GPU へ転送し、GPU 上で float に展開する経路を選びます。PLE 行の表現と計算経路を切り替えるもので、トークン選択を直接変更する設定ではありません。実装は `engine/src/prefill/prefill.cpp` の `ple_compact_on`、`ple_gather`、`ple_land` です。`STRATA_PLE_COPY_STREAM=1` も有効なら raw 行の DMA に専用 stream を使いますが、この変数だけでは転送 stream は切り替わりません（`engine/src/prefill/prefill.cpp:291-303, 4544-4568`）。

## 値と判定

`std::getenv` で読み、値が存在し、かつ先頭の 1 byte が `'1'` の場合だけ true です。文字列全体の数値 parse や trim、大文字小文字変換はしません。空文字は false、`1anything` や `10` は true、`0`、`true`、` 1`、未設定は false です。`ple_compact_on()` 内の function-local `static` に初回評価結果を保存します（`engine/src/prefill/prefill.cpp:294-297`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| エンジン内の判定 | false。ただし下記 CUDA 世代では起動時に Strata が `1` を設定する場合あり | 先頭文字 `1`（`1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1` |
| CUDA の同一 compute capability の全可視 GPU による既定値注入 | 対象世代の既定値表にあれば、`apply_nv_defaults` が未設定時に `1` を設定 | ユーザーが設定した値はそのまま優先 | ユーザーが空文字や `0` を設定すると注入されず、判定は false |

CUDA の既定値表では sm_86 は `STRATA_SM86_PERF=0` で表全体が無効、sm_89 / sm_120 / sm_121 はそれぞれ `STRATA_SM89_PERF=0` / `STRATA_SM120_PERF=0` / `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` で表全体が無効になります。これらの条件を通った表に `STRATA_PLE_COMPACT=1` が含まれます。`sm_86` の分岐には `defaults026` による除外がありません。対象は NVIDIA CUDA の既定値注入条件であり、HIP/AMD での自動注入はこのコードにはありません（`engine/src/core/nv_defaults.cpp:41-73, 75-103, 104-129, 176-213`）。

## 有効になる条件

- PLE を使う prompt 経路であること。`ss.ple.ready()` が true で、実行範囲が `LB <= 1 && 1 < LE` の場合に prompt PLE 処理を行います（`engine/src/prefill/prefill.cpp:4324-4327`）。
- 環境値が上記判定で true であること。
- chunk 用 GPU raw buffer の `cudaMalloc` が成功していること。確保に失敗すると null のままになり、raw 経路を選ばず通常の `gather_batch` に戻ります（`engine/src/prefill/prefill.cpp:2605-2610, 4346-4354`）。
- ホスト側 PLE バッファが pinned であること。`ple_pageable[buf]` が空の場合にだけ raw gather を試します。pinned allocation を使えない fallback では通常の float gather を使います（`engine/src/prefill/prefill.cpp:2597-2602, 4346-4354`）。
- PLE 表が IQ4_NL 形式であること。`gather_raw_iq4nl` はデータがあり、形式 ID が IQ4_NL で、行サイズが `PLE_ROW_BYTES` の場合だけ成功します。失敗時は float gather に fallback します（`engine/src/kernels/ngram.cpp:843-860`）。
- Metal の prompt 経路では有効になりません。Metal は別の window 経路を使い、この compact 対象の `prefill.cpp` 経路に入らない旨が Metal stub に記されています（`engine/metal/src/engine/stubs_0145.cpp:164`）。CUDA 以外での既定値自動注入もありません。

## 実行時の詳細

CUDA の `generate` は、ビルドが HIP / Metal でなく、全可視 NVIDIA GPU の compute capability が同一である場合、起動時に `apply_nv_defaults` を呼びます。既定値は環境変数が未設定のときだけ追加し、空文字を含むユーザー設定は保持します。従って対象 GPU 世代では明示的な空文字で自動 ON を抑止できます。異なる capability の複数 GPU ではこの既定値適用ブロックを通りません（`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:222-239`）。

compact 判定は関数内 static にキャッシュされ、プロセス中に後から環境を変更しても再評価されません。該当 chunk では `ngram_rows` で行番号を作り、raw gather が成功すれば raw バイトを pinned host buffer に置きます。失敗すれば通常の float 行を gather します（`engine/src/prefill/prefill.cpp:294-297, 4335-4354`）。raw gather は表外行を scale 0 / code 8 の表現で埋め、通常読取の +0.0f と同じ値になるようにしています（`engine/src/kernels/ngram.cpp:843-860`）。

`ple_land` は `T * PLE_N_HEADS * PLE_ROW_BYTES` 分を raw device buffer に非同期転送し、その後 `ple_iq4nl_dequant` で `m.ple_emb` に展開します。通常経路では float 行を `m.ple_emb` へ転送します。次の層 1 の PLE block はこの `m.ple_emb` を消費します。つまり環境変数は転送表現と dequant の場所を切り替えます（`engine/src/prefill/prefill.cpp:4550-4568, 5013-5060`）。dequant API の宣言は CUDA kernel と同様に 160 floats/row の出力を記載しています（`engine/include/strata/kernels/ple.hpp:128-130`、kernel は `engine/src/kernels/cuda/ple.cu:397-412`）。

この変数に対応する CLI 引数は見当たりません。CUDA の GPU 世代既定値とユーザー環境値の優先順位以外に、設定ファイルや CLI との上書き規則はありません。トークン decode 用の別経路は `gather_batch` を呼び、`STRATA_PLE_COMPACT` を参照しません（`engine/src/prefill/prefill.cpp:8460-8550`）。

## ログと測定値

この変数の ON/OFF 自体を知らせるログはありません。CUDA 既定値群が一つ以上注入された場合は、`apply_nv_defaults` が `strata: <世代>: ... speed switches on by default ...` の行に設定スイッチ名を列挙します。PLE raw gather が失敗した場合は明示ログなしで float gather に fallback します（`engine/src/core/nv_defaults.cpp:240-255`, `engine/src/prefill/prefill.cpp:4346-4354`）。

upload の CUDA API 呼び出しに失敗すると `prefill: the PLE rows' upload failed: <CUDA error>` を設定して prompt を失敗させ、通常の `generate` は `strata generate: <error>` を stderr に出して終了コード 1 で戻ります（`engine/src/prefill/prefill.cpp:4552-4568`, `engine/src/program/generate.cpp:24163-24167`）。

`docs/DETAILS.md` は `STRATA_PLE_COMPACT=1`, `STRATA_PLE_COPY_STREAM=1`, `STRATA_EMBED_VRAM=1`, `STRATA_DEQUANT_SIDE=1` の組合せについて「All bitwise」、prompt +2.2%〜+2.6% と記載しています。これは4変数をまとめた測定値であり、本変数単独の効果ではありません。記載行には測定機種以外の条件が十分そろっていないため、単独の速度・正確性としては扱えません（`docs/DETAILS.md:1826`）。

## 根拠

- 値判定・キャッシュ: `engine/src/prefill/prefill.cpp:291-303`
- prompt 条件、gather と fallback: `engine/src/prefill/prefill.cpp:4324-4354`
- raw buffer、pinned fallback、転送と GPU dequant: `engine/src/prefill/prefill.cpp:2597-2610, 4535-4568`
- raw IQ4_NL 形式条件・表外行: `engine/src/kernels/ngram.cpp:843-860`
- GPU 世代別既定値とユーザー値の優先: `engine/src/core/nv_defaults.cpp:41-73, 75-103, 104-129, 176-239`
- 既定値適用が行われる CUDA 起動条件: `engine/src/program/generate.cpp:4421-4449`
- decode path が対象外であること: `engine/src/prefill/prefill.cpp:8460-8550`
- 既定値ログ、upload failure 経路、測定資料: `engine/src/core/nv_defaults.cpp:240-255`, `engine/src/program/generate.cpp:24163-24167`, `docs/DETAILS.md:1826`
