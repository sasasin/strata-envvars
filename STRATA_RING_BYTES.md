# `STRATA_RING_BYTES`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

prompt prefill の expert streaming ring と、`--prefill auto` が決める chunk サイズを連動させる方式を選びます。既定では ring を pack の blob サイズに応じた byte budget で扱い、旧方式の固定 slot 数・chunk 候補リストへ戻すには値の先頭を `0` にします。対象実装は CUDA/HIP 系の `src` と SYCL 系の `sycl/src` にあります。

## 値と判定

値は文字列全体を parse せず、`std::getenv()` の結果の先頭文字だけを判定します。判定結果は関数内の `static const bool` に保存され、最初の評価後にプロセス環境を変更しても再評価されません。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 有効（byte-budget 方式） |
| 空文字 | 有効（先頭文字は `\0` であり `0` ではない） |
| 先頭文字が `0`（例: `0`, `0anything`） | 無効（旧方式へ戻る） |
| それ以外（例: `1`, `true`, `false`, `anything`） | 有効 |

数値変換、空白除去、大文字小文字の変換はありません。したがって `false` も有効です。根拠: `src/prefill/prefill.cpp:266-269`、`sycl/src/prefill/prefill.cpp:185-188`。

## 有効になる条件

byte-budget の ring と chunk の組み合わせを選ぶのは、expert cache から prompt 用バッファを借りる `--prefill auto` の計画経路です。CUDA/HIP 系では単一 cache の `plan_lend` と複数 stage の `scan`、SYCL 系でも対応する同じ経路に判定があります。explicit な `--prefill N` はこの auto chunk scan を使いませんが、バッファ必要量の見積もりにはこの変数の分岐が使われます（`src/program/generate.cpp:6317-6386,6975-7066`、`sycl/src/program/generate.cpp:5973-6040,6529-6615`）。

有効時の ring byte budget は Q2_0 blob のサイズと pinned share から定め、実際の pack の最大 blob サイズで slot 数へ換算し、ring 上限で clamp します。自動計画は cache の空き byte 数を見て ring と chunk の組を探します。非 pinned share の経路は従来どおり slot 数 96 を使います。`STRATA_PREFILL_RING` が設定されている場合は、その値から得た ring 数が計算上の budget より優先されます。また、`--prefill auto` 自体が選ばれない経路（利用可能な expert cache loan がない場合など）では、この auto scan の効果はありません。根拠: `src/prefill/prefill.cpp:241-274,276-297`、`src/program/generate.cpp:6282-6317,6360-6386`。

## 実行時の詳細

- **有効時（既定）:** auto chunk scan は 256-token grid 上で byte budget に収まる chunk を探します。従来の auto chunk で収まる場合はその ring を維持し、それより大きい chunk を選ぶ場合に、chunk と ring の byte budget を合わせて ring slot 数を決めます。auto planner が選んだ budget は `Prefill::set_ring_budget()` で保存されます。
- **先頭文字が `0` の場合:** auto planner は旧候補 `{32768, 16384, 8192, 6144, 4096, 3072, 2048, 1024, 512, 256}` から最初に適合する chunk を選び、ring budget を設定しません。候補は `--prefill auto:N` の上限、context、loan 可能 slot 数などでも制限されます。実際の ring 数は、明示的な `STRATA_PREFILL_RING` や split ring override がなければ pinned-share に応じた従来の 1024/384/96 slot（ring 上限内）です。
- **バッファ見積もり:** `Prefill::bytes_needed_impl()` は有効時に実際の carve に合わせた `xn` / `grs` / `HC` バッファの数え方を使い、無効時は旧版の数え方を使います。この見積もりは loan 可否や chunk/ring が収まるかの判定に使われ、GPU メモリの実割当そのものをこの環境変数が直接切り替えるわけではありません。根拠: `src/prefill/prefill.cpp:1830-1855`、SYCL 実装 `sycl/src/prefill/prefill.cpp:1862-1886`。

auto 選択時の serve 経路は stderr に `strata serve: prompt chunk auto: ... tokens, a ...-slot ring` と実際に解決した chunk / slot 数を出します。変数専用の警告やエラーは見つかりません。CUDA/HIP 系と SYCL 系で判定・auto planning の分岐が並行して実装されています。根拠: `src/program/generate.cpp:7095-7105`、`sycl/src/program/generate.cpp:6615-6621`。

## 文書・測定値との照合

`docs/DETAILS.md:1843-1856` は、既定の byte-budget ring と `--prefill auto` の連動、および `STRATA_RING_BYTES=0` による旧 ring / loan / chunk choice の復元を説明しています。同資料では RTX 5070 の 32K prompt の比較として IQ3_XXS +18.5%（別 memory state で +9%）、Coder +3%、IQ3_S は変化なし、4K prompt は -0.7%〜+1.1% の範囲で同一出力と記載されています。長い prompt では cached / streamed experts の組み合わせが変わり、出力 bits も変わる旨も記載されています。これらは資料に記載された環境・測定条件での結果であり、他の GPU やモデルでの性能を保証しません。固定 `--prefill 2048` の Q2_0 は影響を受けなかったと同資料にあります。
