# `STRATA_LEND_MIRROR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の `--stream-experts` 経路で、プロンプト処理に貸し出す expert-cache 末尾のスロットに元々入っている expert も、pinned host memory のミラー候補に加える。プロンプト中はそのスロットが作業バッファとして使われ、終了後に expert が戻されるため、その間の routed expert を GGUF から再読せずミラーから読む機会を作る。GPU キャッシュに収まらない expert のミラー候補が先に並び、末尾スロットの expert はその後に追加されるため、ミラー容量が足りない場合は後者が容量制限で採用されないことがある（`engine/sycl/src/program/generate.cpp:5426-5428,5438-5466`）。

この環境変数は末尾候補数を決めるだけで、ミラー自体の有効化を単独で保証しない。ミラー容量は `STRATA_MIRROR_MIB` とメモリー状況にも左右される（`engine/sycl/src/program/generate.cpp:5475-5488`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atoll` で変換する。文字列全体の検証はない。したがって未設定と空文字は別扱いで、空文字は `atoll` の結果 0 となり末尾追加を無効にする。整数として読める先頭部分があれば後続文字列は判定されず、例として `12junk` は 12、`0anything` は 0 になる。先頭空白と符号は `atoll` の変換規則に従い、数値に変換できない文字列は 0 となる。負数も `want_tail > 0` を満たさない。正数は実キャッシュ slot 数を上限として扱われる（`engine/sycl/src/program/generate.cpp:5454-5465`）。

| 条件 | unset | 有効になる値（例） | 末尾候補を追加しない値（例） |
| --- | --- | --- | --- |
| 借用条件を満たす単一デバイス | 統合メモリー（UMA）デバイスでは 0。それ以外は `min(cache slots / 10, 1200)` | `1`, `10`, `1200`, `999999`（最後は slot 数までに制限） | 空文字, `0`, `0anything`, `-1`, `true`, `false`, `junk` |
| 借用条件を満たさない場合 | 読み取り自体をしない | 該当なし | この変数による追加なし |

## 有効になる条件

- 実装は `engine/sycl/src/program/generate.cpp` の SYCL 経路にある。CUDA/HIP 固有実装での読み取りは確認できない。
- expert の初期化が `--stream-experts` を選び、native IQ pack と `--native SHARD1` を使って `GgufExpertSource` を選ぶこと。stream モードでこの pack 条件を満たさない場合は `strata generate: --stream-experts needs a native (IQ) pack and --native SHARD1` と出して終了する（`engine/sycl/src/program/generate.cpp:4711-4721`）。
- `o.expert_cache > 0` であること。ここを満たさなければミラー候補作成ブロック自体を通らない（`engine/sycl/src/program/generate.cpp:5431`）。
- `--no-prefill-borrow` が有効でなく、`--prefill` により `prefill_chunk > 0`、かつ `multi_gpu` でないこと。`--prefill-borrow` は borrow を明示的に有効にする引数（`engine/sycl/src/program/generate.cpp:2018-2031,5453-5454`）。
- 正の末尾数を指定しても、ミラー作成には非ゼロの `STRATA_MIRROR_MIB` または算出された容量が必要。UMA デバイスで `STRATA_MIRROR_MIB` が未設定の場合、自動 expert cache では容量を 0 にし、明示 cache では pool の空きから `--vram-reserve-mib` 分を引いた容量にする（`engine/sycl/src/program/generate.cpp:5475-5485`）。
- `STRATA_LEND_MIRROR` 未設定時は UMA 判定で既定値が分岐する。明示値があればその数値が使われ、UMA でも既定の 0 は適用されない。ただし上記のミラー容量条件は別に残る（`engine/sycl/src/program/generate.cpp:5455-5465,5475-5488`）。

## 実行時の詳細

変数は generate の初期化中、通常の VRAM miss を集めた後、`miss` リストを pinned mirror に作成する前に読み取られる。一度ローカル変数 `want_tail` に変換され、以後再読・static cache はしないため、プロセス実行中に環境値を変えても今回の起動中の判定には反映されない（`engine/sycl/src/program/generate.cpp:5436-5466`）。

正数の場合、`first_tail = slots - min(want_tail, slots)` 以降の cache slots に現在 resident な `(layer, expert)` を走査して `miss` の末尾に追加する。実際の prompt loan も cache 末尾を使う。通常の miss を優先して `gguf_src.mirror(miss, cap, 8, err)` に渡し、容量の範囲で先頭から pinned memory に複製する（`engine/sycl/src/program/generate.cpp:5447-5466,5486-5497`; `engine/sycl/src/core/gguf_expert_source.cpp:123-136`）。ミラー作成後はアドレス表を device に転送し、resident plan に登録する（`engine/sycl/src/program/generate.cpp:5498-5505,7683-7694`）。

借用中の slot は resident 表から一時的に外される。device plan は expert が cache slot にいない場合に mirror address を参照し、アドレスがあればその expert をミラーから読む経路に進む。ミラーがなく host-side plan の fallback もない場合は plan error を記録する（`engine/sycl/src/program/generate.cpp:13312-13349`; `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2521-2549`）。この変数は候補を足すもので、どの expert が prompt で選ばれるかや prompt loan の slot 数自体は決めない。

## ログと測定値

この変数専用のログはない。ミラー処理が失敗すると stderr に `strata generate: mirroring the experts missing from VRAM: ... (they stay on the SSD)` が出る。成功時は `strata generate: N of M experts missing from VRAM (+ K in the prompt loan's slots) mirrored in pinned host memory (...)` の形式で、ミラーされた通常 miss 数と prompt loan slot の expert 数が表示される。これは両種の候補を合算した作成結果であり、環境変数の値そのものは表示しない（`engine/sycl/src/program/generate.cpp:5486-5497`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:4711-4721` — stream source 選択と pack 条件。
- `engine/sycl/src/program/generate.cpp:5426-5466` — mirror miss と貸出末尾候補、環境値の変換・既定値。
- `engine/sycl/src/program/generate.cpp:5475-5509` — ミラー上限、作成、成功・失敗ログ。
- `engine/sycl/src/program/generate.cpp:13312-13356` — prompt loan が末尾 slots を使う箇所。
- `engine/sycl/src/program/generate.cpp:7683-7694` — device mirror table の登録。
- `engine/sycl/src/core/gguf_expert_source.cpp:123-136` — 候補リストを容量内で選ぶ処理。
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2521-2535` — resident でない expert の mirror address 判定。
