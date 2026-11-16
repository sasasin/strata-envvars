# `STRATA_PRIVATE_DOWN_S4`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の Battlemage 向け Q2 down-projection において、packed-register 実装を選んだ後の down kernel を、既定の `DownPackedRegisterKernel` から S4 向け `DownPackedS4Kernel` に切り替える private opt-in である。S4 側は Q2 の重みを nibble に展開し、XMX の `dpas` を `s4` 重み・`s8` 活性値で実行して down 出力へ蓄積する。コードからは、この切替による出力の同一性や性能差は確認できない。読み取りは `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `p4_enabled()`、切替は `launch_ps_down()` にある（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721-4725, 4740-4788, 5598-5603`）。この `.dp.cpp` は SYCL の kernel source に含まれる（`sycl/CMakeLists.txt:34-41`）。

この変数だけでは S4 kernel を有効にしない。Q2 型の down 経路、形状、デバイス、モデルの重み状態、および別の opt-in が揃った場合だけ評価される（「有効になる条件」参照）。CUDA/HIP の実装でこの変数を読む箇所はなく、確認できた読み取りは SYCL ソース内の 1 箇所だけである。

## 値と判定

`std::getenv` が返す文字列の先頭 1 byte が ASCII `'1'` かを判定する。文字列全体の比較や数値変換はしない。関数内 `static const bool` に保存される。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `p4_enabled()` が初めて呼ばれたとき | 無効 | `1`, `10`, `1anything` | 空文字、`0`, `true`, `2`, `01`, ` 1` |

未設定・空文字・先頭が `1` 以外の値はすべて無効で、警告や別のエラーにはならず既定 kernel に進む。空白除去、大文字小文字変換、後続文字の検証、数値範囲の検証はない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721`）。

## 有効になる条件

S4 kernel が選択されるには、次の条件がすべて必要である。

- SYCL backend の grouped expert down 呼び出しで、down weight type が `42`（Q2）であること。`launch_down<42>()` は旧 kernel でなく、multi-split でなく、`STRATA_DOWN_LANES` による実効 lane 数が `8` で、`STRATA_SYCL_Q2_WORD_EXPAND` が無効化していないときに Q2 word-expand 経路へ入る。後者は未設定なら有効、値の先頭が `0` なら無効（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3702-3714, 4243-4249, 5863-5868`）。
- Q2 word-expand 経路の中で `L.n_embd == 2560` かつ `L.n_ff == 640` であること（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5727-5732`）。
- `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字が `1` であり、現在の actor が main actor、重みが packed 状態で、実行 device の世代が `Battlemage` であること。どれかを満たさない場合、Q2 word-expand の通常 kernel に進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469, 5730-5740`）。
- 上の条件を満たしたうえで `STRATA_PRIVATE_DOWN_S4` の先頭文字が `1` であること。そうでなければ `DownPackedRegisterKernel` が選ばれる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5598-5603`）。

## 実行時の詳細

down weight type `42` の grouped expert kernel から、条件に応じて Q2 word-expand launcher に入り、対象形状と packed-register 条件が一致すれば `launch_ps_down()` を呼ぶ。この関数は `p4_enabled()` が真なら `launch_pvr_s4<true, DownPackedS4Kernel>`、偽なら `launch_pvr<true, DownPackedRegisterKernel>` を投入する。S4 launcher は down 専用 packet を使用し、packet 内で Q2 code を変換して `dpas` し、scale を掛けた値を destination row に加算する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4791-4814, 4722-4788, 5598-5603, 5714-5725`）。

環境値は `p4_enabled()` の初回呼び出し時に一度だけ読み、プロセス内 static に保持する。初回評価後に環境を変更しても、この判定には反映されない。CLI 引数や設定ファイルによる上書きはこのコード経路にはない。リクエストごとの再読込や子プロセスへの転送も実装されていない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721, 5601-5603`）。

## ログと測定値

この変数の判定、S4 kernel の選択、または fallback を示すログ出力は該当経路にない。対象変数についての測定値も、今回確認した Strata のソースと `docs/DETAILS.md` には見当たらないため記載しない。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721` — 対象環境変数の唯一の実読取と先頭文字判定。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4722-4788` — S4 向け Q2 packet の変換・演算・出力。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469, 5598-5603` — packed-register 条件と S4/default kernel の分岐。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3704-3714, 5863-5868, 5727-5740` — Q2 word-expand 条件と形状・デバイス条件。
- `sycl/CMakeLists.txt:34-41` — SYCL kernel source としての登録。
