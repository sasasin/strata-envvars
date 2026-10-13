# `STRATA_SPLIT_RING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

layer split で複数 GPU に分けた `serve` の prompt path が使う streamed ring の slot 数を指定します。これは prompt path の buffer と expert cache の貸し借りに使う slot 数に影響します。`STRATA_SPLIT_RING` は ring の上書き値を選び、実際に確保される ring は chunk 長、上限、別環境変数 `STRATA_PREFILL_RING` にも左右されます。

CUDA/HIP の `src/program/generate.cpp` では stage cache の residency 比率を求め、`strata::program::split_ring_slots()` で値を決めます。SYCL の `sycl/src/program/generate.cpp` にも同じ用途の直接実装があります。どちらも設定は prompt buffer のサイズ計算より前に適用されます (`src/program/generate.cpp:6702-6718,6750-6752,7031`、`sycl/src/program/generate.cpp:6560-6575`)。

## 値と判定

環境変数は `std::atoi` で整数化されます。文字列全体の妥当性検査はなく、先頭の空白や符号を含む数値の後ろに文字が続いていても、`atoi` が変換した整数を使います。数値に変換できない文字列や空文字は 0 になります。負数も最終的に 0 として扱われます。範囲 clamp は split helper では行わず、positive 値の実リング適用時に行われます。

| `STRATA_SPLIT_RING` | split helper の結果 | 動作 |
|---|---:|---|
| 未設定、かつ cache residency が 75% 以上 | 96 | 96 slot の split 用 override を設定 |
| 未設定、かつ residency が 75% 未満 | 0 | split 用 override は設定せず、通常の pinned-share / ring budget 規則へ |
| 整数に変換される正数 | その整数 | split 用 override を設定。実際の ring は別途 clamp される |
| `0`、負数、空文字、非数値文字列 | 0 | split 用 override は設定せず、通常規則へ |

閾値は `res_share >= 0.75` です。residency は `host_res` のうち slot 番号が 0 以上の要素数を `host_res.size()` で割って算出します。これは (layer, expert) pair のうち何割がいずれかの stage cache にあるかを表します (`src/program/generate.cpp:6707-6713, include/strata/program/split_ring.hpp:17-23`)。

helper が正数を返すと `Prefill::set_ring_override()` が値を保持します。一方、Prefill の実 ring は `STRATA_PREFILL_RING` が設定されていればその `atoi` 値を優先します。これも未設定時の pinned-share 規則、ring budget より優先です。明示値が `STAGE` の場合は routed-only staging になり、それ以外は chunk が `stream_all_min()` 以上のとき ring を使います。使う場合の slot 数は 16 未満なら 16、`ring_cap()` 超過なら cap までに制限されます。chunk が閾値未満なら ring slot 数は `STAGE` です (`src/prefill/prefill.cpp:277-298`)。

## 有効になる条件

- CUDA/HIP 側では `--serve`、複数 GPU の layer split、および初期化済みの `host_res` が必要です。これらを満たさない場合、`decide_split_ring()` は変数を読みません (`src/program/generate.cpp:6707-6713`)。
- SYCL 側も `--serve` の処理内で、複数 GPU split かつ `host_res` が空でない場合に判定します (`sycl/src/program/generate.cpp:6501,6564-6569`)。
- `--resident-experts` は必須ではありません。resident RAM mode では lend region を計算する前の経路で判定し、そうでない場合も split の prompt-path 準備前に判定します (`src/program/generate.cpp:6720-6752,7031`)。
- single GPU や非 serve 実行には適用されません。
- `STRATA_PREFILL_RING` が設定されていると、split 側が決めた値よりそちらの slot 数が優先されます (`include/strata/prefill/prefill.hpp:85-90`, `src/prefill/prefill.cpp:277-298`)。

## 実行時の詳細

CUDA/HIP の ring 決定 lambda は `split_ring_decided` で一度だけ実行されます。`host_res` の residency 比を計算し、環境変数をこの初期化時に読みます。決定値が正数なら `Prefill::set_ring_override()` を呼び、stderr に次の形式で出します: `strata serve: layer split: %.0f%% of the experts resident, the prompt path's streamed ring %d slots`。値が 0 の場合、このログも出ません (`src/program/generate.cpp:6706-6718`)。SYCL 側も正数のとき同じログ形式で設定します (`sycl/src/program/generate.cpp:6564-6574`)。

Prefill の `bytes_needed()` は ring の slot 数と `MAXBLOB()` を使って ring buffer 分の bytes を数えます。split で resident RAM mode を使う場合、この値が prompt path に貸す cache tail の大きさを決めるため、ring override は lend region の sizing より前に行われます。起動時の `lend sizing` ログは prompt path が借りる slot 数、実 ring、RAM にも保持される expert 数を示し、RAM copy にない借用 slot があれば `WARNING` を出します (`src/prefill/prefill.cpp:1836-1890`, `src/program/generate.cpp:6750-6752,7237-7255`)。

`atoi` の範囲外数値は C/C++ の `atoi` の範囲外変換に委ねられ、Strata 独自のエラーや clamp はありません。設定は生成処理の初期化で ring override に反映されるので、その後に環境を変更しても既に決まった ring には反映されません。

## 文書との照合

`docs/MULTI_GPU.md` は、residency 75% 以上で未設定時 96 slot、`STRATA_SPLIT_RING=N` で slot 数指定、0 で pinned-share rule に戻ることを説明しており、実装と一致します。同資料が記す `STRATA_SPLIT_RING=384` 時の借用 5,396 slot / resident RAM copy 内 4,662 slot、以前の実装で毎 chunk 734 expert がモデルファイルから読まれた例もコードの意図と整合します。ただし、これらは同資料に記載された特定環境（2x RTX 3080 20 GB、UD-Q4_K_XL 等）の測定値であり、今回独立に再測定した値ではありません (`docs/MULTI_GPU.md:153-167`)。

## 根拠

- `include/strata/program/split_ring.hpp:17-23` — unset 時の residency 閾値、`atoi`、正数以外を 0 にする判定。
- `src/program/generate.cpp:6702-6718,6750-6752,7031` — CUDA/HIP の適用条件、読み取り時期、override 設定とログ。
- `sycl/src/program/generate.cpp:6560-6575` — SYCL 側の判定と適用。
- `src/prefill/prefill.cpp:277-298,1836-1890` — 別変数による優先順位、chunk に応じた slot 数、ring の bytes 計算。
- `include/strata/prefill/prefill.hpp:83-90` — override が `bytes_needed` / `init` 前に設定され、`STRATA_PREFILL_RING` が優先する契約。
- `src/program/generate.cpp:7237-7255`、`docs/MULTI_GPU.md:153-167` — borrow/resident-lend の観測ログと資料中の測定条件。
