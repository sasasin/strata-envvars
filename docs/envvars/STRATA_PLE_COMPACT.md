# `STRATA_PLE_COMPACT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

CUDA/HIP の通常 prompt prefill で、PLE（n-gram embedding）用 IQ4_NL 行をホストで float に復号してから転送する代わりに、raw 行を転送して GPU 上で float に復号する opt-in です。`src/prefill/prefill.cpp` の `ple_compact_on()` が環境変数を読みます。compact 経路では 1 token あたり 16 行を読み、各行 90 bytes の raw データを host buffer から device に転送し、各行 160 個の float に復号します。通常経路は `gather_batch()` が復号済みの float を host buffer に書きます（`src/prefill/prefill.cpp:154-159,3069-3077,3247-3268`; `include/strata/kernels/ngram.hpp:32,35,47`; `src/kernels/ngram.cpp:603-654,692-709`）。

## 値と判定

値全体や数値としての妥当性は検査せず、最初の文字だけを `'1'` と比較します。大文字小文字や後続文字は判定に影響しません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF（値は設定済みでも先頭文字が `\0`） |
| 先頭文字が `1` | ON。例: `1`, `10`, `1anything` |
| それ以外 | OFF。例: `0`, `true`, ` 1`, `01` |

根拠: `src/prefill/prefill.cpp:156-159`。

## 有効になる条件

ON 判定に加えて、次の条件が必要です。

- 通常の CUDA/HIP prefill の `run_impl` で PLE が有効であること。`ple_on` は PLE state が ready で、現在の stage が layer 1 を含む場合に true になります（`src/prefill/prefill.cpp:3047`）。
- PLE table の raw gather が成功すること。raw API は table data がメモリにあり、format が IQ4_NL、行サイズが `PLE_ROW_BYTES` の場合だけ true を返します。API の説明では `--ple-io ram` / `mmap` が対象で、それ以外は false となって通常の `gather_batch()` に戻ります（`include/strata/kernels/ngram.hpp:190-193`; `src/kernels/ngram.cpp:692-709`; `src/prefill/prefill.cpp:3071-3077`）。
- host buffer が pageable fallback ではなく、raw row 用 device buffer の確保に成功すること。条件を満たさない場合は通常の float gather に戻ります。raw buffer は環境変数が ON と判定された場合に確保を試みますが、`cudaMalloc` 失敗はエラーを消費して null のままにし、ここでは警告を出しません（`src/prefill/prefill.cpp:1686-1700,3071-3077`）。

`--ple-io` は CLI 側で PLE table の I/O mode を選びますが、環境変数の値を上書きする設定ではありません。raw API が使えるかどうかには table がメモリ上にあるかが影響します（`src/program/generate.cpp:3062,4716-4763`; `src/kernels/ngram.cpp:692-709`）。

Metal では `Prefill::init()` が Metal window 経路に早期 return するため、この CUDA/HIP の chunk 実装は実行されません。Metal 用 stub のコメントも、この関数は Metal prompt から到達しないとしています（`src/prefill/prefill.cpp:1538-1547`; `metal/src/engine/stubs_0145.cpp:161-162`）。また、複数 segment の `lm_run` は別の gather lambda で常に `gather_batch()` を呼ぶため、そこでは compact 化しません（`src/prefill/prefill.cpp:6299-6314`）。

## 実行時の詳細

`ple_compact_on()` の結果は関数内の `static const bool` に保存されます。最初の helper 呼び出しで評価され、その後同じプロセス内では再評価されません。helper は prefill 初期化時の raw buffer 確保判定と、各 PLE chunk の gather 判定から呼ばれます（`src/prefill/prefill.cpp:156-159,1696-1700,3071-3077`）。

compact 経路では `gather_raw_iq4nl()` が token ごとに 16 行の raw data を pinned host buffer に書きます。layer 1 の PLE block を実行する直前に `ple_land()` が raw bytes を device に非同期転送し、`ple_iq4nl_dequant()` を compute stream 上で起動して `m.ple_emb` に float を生成します。dequant kernel は IQ4_NL の scale と nibble code を用いて 160 float/row を出力します（`src/prefill/prefill.cpp:3069-3077,3239-3272,3630-3634`; `src/kernels/cuda/ple.cu:391-410`）。`STRATA_PLE_COPY_STREAM` が別途有効で stream/event の初期化にも成功した場合、raw upload は専用 stream に移り、compute stream は dequant の前に upload 完了を待ちます。専用 stream の初期化に失敗した場合は stderr に fallback 警告を出し、compact のまま compute stream から転送します（`src/prefill/prefill.cpp:160-165,1702-1710,3249-3270`）。

raw upload または関連 event 操作が失敗すると、`prefill()` は `prefill: the PLE rows' upload failed: ...` をエラー文字列に設定して false を返します。raw table gather が利用できない場合や raw device buffer がない場合は、このエラーではなく通常の `gather_batch()` に fallback します（`src/prefill/prefill.cpp:3071-3077,3243-3271`）。

## 根拠

- 環境変数の唯一の読み取りと先頭文字判定: `src/prefill/prefill.cpp:154-159`。この名を読む別の実装箇所はありません。ほかの参照はコメント、宣言、テスト用ターゲット、設計資料です。
- 初期化時の buffer 確保と失敗時の fallback: `src/prefill/prefill.cpp:1686-1700,3071-3077`。
- raw table gather の形式・メモリ条件と通常 gather: `include/strata/kernels/ngram.hpp:186-193`; `src/kernels/ngram.cpp:603-654,692-709`。
- 転送・device dequant とエラー: `src/prefill/prefill.cpp:3239-3278`; `src/kernels/cuda/ple.cu:391-410`。
- `docs/DETAILS.md` は `STRATA_PLE_COMPACT=1`、`STRATA_PLE_COPY_STREAM=1`、`STRATA_EMBED_VRAM=1`、`STRATA_DEQUANT_SIDE=1` を同時に挙げ、4 変数を合わせた測定として prompts +2.2%〜+2.6% を記載しています。これは組み合わせ全体の報告値であり、この変数単独の効果としては扱えません（`docs/DETAILS.md:1535-1546`）。
