# `STRATA_GDN_QK_REG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の GDN multi-token recurrence で、条件に合う Battlemage GPU の Q/K 読み出しに register broadcast kernel を選びます。標準経路は Q/K 値を work-group local memory に置きますが、この経路は各 subgroup lane が担当する値を register に読み、subgroup 内から参照します。変数は `gdn_step_norm_multi()` 内で一度判定されます（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1916`）。

## 値と判定

名前を実際に読む箇所はこの関数の `bm_default_on("STRATA_GDN_QK_REG", ..., false)` だけです。同名の完全一致参照は `docs/INTEL.md` にもありますが、そこは説明資料です。helper は文字列を数値として parse せず、非空値の先頭文字だけを見ます（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1895`, `sycl/include/strata/sycl_queue.hpp:162-166`）。

| 環境値 | `qk_reg` 判定 |
|---|---|
| 未設定 | OFF。この呼び出しは `bm_default=false` を指定 |
| 空文字 | OFF。空文字は未設定と同様に既定値へ進む |
| 先頭文字が `0` の非空文字列 | OFF（例: `0`, `0anything`） |
| それ以外の非空文字列 | ON（例: `1`, `true`, `false`, `2`）。残りの文字列は検査しない |

ここでの ON は非 Battlemage に対しても `qk_reg` 自体を true にできますが、実際の kernel 選択には後述の Battlemage 条件が別途あります。値の読み取り結果は `static const bool` に保存されるため、最初の呼び出し後に環境値を変更しても再評価されません。既定判定に使う device も初回呼び出しの stream の device です（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1895`, `sycl/include/strata/sycl_queue.hpp:162-165`）。

## 有効になる条件

register broadcast kernel に切り替わるには、`qk_reg` が ON で、かつ次の条件をすべて満たす必要があります（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1896-1915`）。

- stream の device が `IntelGpuGen::Battlemage` と判定される。
- GDN shape が `h_k == 16`, `h_v == 48`, `conv_channels == 10240`。
- `xq` が null、`n_keep` が null、`t_out_begin == 0`。

Battlemage 判定は SYCL device の architecture 情報を優先し、取得できない場合は device 名や PCI ID の文字列から判定します。Arc A-series は Alchemist に分類されます（`sycl/include/strata/sycl_queue.hpp:119-157`）。対象条件に合わない場合は環境値が ON でもこの特別 kernel を使わず、同じ関数内の通常経路に進みます。

## 実行時の詳細

適用時は `GRF256` と `use_root_sync` の properties を付けて `gdn_qk_register` kernel を起動し、`gdn_step_norm_multi_kernel<true, false, true>` を実行します。QK_REG 経路では各 token の Q/K を register にロードし、`select_from_group` で subgroup 内の値を使って QK 積と状態更新を行います。条件に合わない場合の通常 kernel は Q/K を local memory の `sk` / `sq` に保持する経路です（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:389-392,421-436,454-462,1896-1915,2086-2125`）。

GDN の verifier 経路からは、通常の recurrence 呼び出しや commit/replay 呼び出しなどでこの関数が呼ばれます（`sycl/src/core/verify.cpp:1108-1121,1983-1994`）。ただし、ここに挙げた呼び出しすべてが分岐条件を満たすわけではありません。たとえば QFUSE の出力 quantization buffer `xq` が渡される場合や、commit のように `t_out_begin` が 0 でない場合はこの分岐に入りません（`sycl/src/core/verify.cpp:1120-1123,1988-1994`）。

条件を満たす最初の実行時に stderr へ `strata: GDN QK register broadcast enabled (GRF256)` を一度出します。特別 kernel の後は `check("gdn QK register")` を呼び、通常 kernel 経路では `check("gdn_step_norm_multi")` を呼びます。環境変数専用の警告、無効値エラー、条件不成立理由のログはこの実装にはありません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:1899-1915,2126-2127`）。

## 資料との照合

`docs/INTEL.md` はこの変数を既定 OFF（Battlemage 向け一覧の `no`）とし、対応する GDN geometry での register-broadcast QK と説明しています（`docs/INTEL.md:545`）。同資料は別途、8個の opt-in 制御が 2x Arc Pro B65 / IQ3_S で中立またはやや低速だったと記していますが、この注記は複数制御をまとめたもので、`STRATA_GDN_QK_REG` 単独の測定結果や一般的な性能差を示すものとしては扱えません（`docs/INTEL.md:547-549`）。

## 根拠

- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1917` — 値判定、GDN geometry・引数・GPU 条件、kernel 選択、ログ。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:341-355,389-436,454-462` — template parameter `QK_REG` による register broadcast と通常 Q/K 読み出し。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2086-2127` — 通常経路の kernel 起動と check。
- `sycl/include/strata/sycl_queue.hpp:119-166` — Intel GPU 世代判定と `bm_default_on` の値規則。
- `sycl/src/core/verify.cpp:1108-1123,1983-1994` — verifier の recurrence / commit からの呼び出し例。
- `docs/INTEL.md:545,547-549` — 対応機能と測定注記。
