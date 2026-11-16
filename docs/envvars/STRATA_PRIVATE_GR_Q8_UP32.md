# `STRATA_PRIVATE_GR_Q8_UP32`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL backend の hyper-connection read（GR）で、条件を満たす single-token 経路の up projection と出力 Q8_1 画像の生成に、Battlemage 向け `b60_gr_q8_up32_t1_kernel` を選ぶ private opt-in です。標準経路の up projection の代わりに専用 kernel を起動し、その kernel は `mixed` と `q8_mixed` を書きます。コードコメントは「より多くの block、warp あたりの直列 row を減らす」「stream sum は変更しない」としていますが、現 commit の文書・レジストリにこのスイッチの測定結果はありません。性能や出力の同一性を実測済みとは扱えません。読み取りと kernel 選択は `sycl/src/kernels/cuda/fused_gr.dp.cpp:2386-2387,3466-3500` にあります。

## 値と判定

値は `std::getenv` で取得し、ポインタが非 null かつ `p[0] == '1'` の場合だけ有効です。文字列全体の parse・比較はせず、空文字は無効です。先頭が ASCII `'1'` なら後続文字を問わず有効（例: `1`, `1anything`）。未設定、`0`, `true`, `TRUE`, 空文字、` 1`, `01` は無効です。大文字小文字、空白、数値としての妥当性は検査しません。加えて `STRATA_PRIVATE_B60_DECODE_LAYOUT` も同じ先頭文字判定で有効でなければ、この変数の有効判定は false になります。`sycl/include/b60_layout_state.hpp:7-9`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 共通の値判定 | false | 先頭文字が `1`（`1`, `1anything`） | 空文字、`0`, `true`, ` 1`, `01` |
| Battlemage layout 条件 | `STRATA_PRIVATE_B60_DECODE_LAYOUT` が unset なら機能判定も false | 対象変数と `STRATA_PRIVATE_B60_DECODE_LAYOUT` の両方が先頭 `1` | いずれかが未設定、空、または先頭が `1` 以外 |

対象変数の判定は `b60_gr_q8_requested()` と `b60_gr_q8_up32_enabled()` にそれぞれ関数内 `static const bool` として保存されます。layout 側も独立した関数内 static です。したがって各判定関数の初回呼び出し後にプロセス環境を変更しても、その関数の値は更新されません。CLI 引数による上書きはこのコードにはありません。`sycl/include/b60_layout_state.hpp:7,9`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386`。

## 有効になる条件

値判定を通過しても、実際の専用 kernel 起動には以下すべてが必要です。

- Battlemage 世代の SYCL device であること。基礎となる `gf_enabled()` は `strata::intel_gpu_gen(...) == Battlemage` を要求します。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`。
- `gf_enabled()` の他条件を満たすこと: `STRATA_PRIVATE_GR_F32_REG` が `atoi` で非ゼロ、token 数 1〜4、down sliced が有効、more-groups と large-GRF が無効、norm split 有効、up columns が 16、up ILP が無効。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`。
- 専用 kernel の分岐では token 数が 1、`a[0].q8_mixed` が非 null、`q8_down` と `q8_up` が null であること。`sycl/src/kernels/cuda/fused_gr.dp.cpp:3466-3468`。
- `STRATA_PRIVATE_GR_F32_PHASE` が `down` を選び、`up` を選ばないこと。値が unset のとき `gf_phase()` は両 phase を true とするため、unset のままでは専用分岐に入りません。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693,3466-3469`。
- `STRATA_PRIVATE_GR_SILU_FROM_LO` が `atoi` で非ゼロであること。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2529-2532,3466-3469`。
- 呼び出し元が `q8_mixed` を用意する経路であること。Verifier の read と head 経路、および MTP の複数 GR 経路は、`b60_gr_q8_requested()` が true で token 数 1 の場合に `xq_` を割り当てます。`sycl/src/core/verify.cpp:1144-1148,1811-1813,1829-1831,1844-1846`、`sycl/src/core/mtp.cpp:936-948,1066-1079,1194-1207,1208-1218`。

## 実行時の詳細

変数の値は上記 helper の初回評価時に読み取られ、static cache されます。環境値を反映させるには、その helper が初めて呼ばれる前に設定されている必要があります。専用分岐に入ると `launch_b60_gr_q8_up32_t1()` が `(N/32) * THREADS` work-item の SYCL kernel を起動します。kernel は up projection を計算して `mixed` に書き、同じ出力から `q8_mixed` の 32 値ごとの量子化値と scale/sum を書きます。`fused_gr_read_multi()` はこの分岐を選んだとき true を返し、呼び出し元は戻り値を使って後続の Q8_1 再量子化を省きます。条件に合わなければ既存の up 経路へ進みます。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2387-2506,2510-2515,3466-3500`、`sycl/src/core/mtp.cpp:948-952,1079-1088`、`sycl/src/core/verify.cpp:1811-1814,1861-1862`。

## ログと測定値

この変数を読んだり専用分岐を選んだりしたことを示す専用ログは確認できません。`data/settings-register.json` は SYCL の private switch、既定 off、先頭値 `=1` で opt-in と登録し、「integration lane measured nothing on it」と記録しています（`data/settings-register.json:30990-31018`）。`docs/DETAILS.md` に本変数の記載はなく、性能値・正確性の測定根拠は確認できません。kernel コメントの「same bits」は実装意図の記述であり、この調査で検証した測定結果ではありません。

## 根拠

- 全参照と値判定・layout 依存: `sycl/include/b60_layout_state.hpp:7-9`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386`。
- 専用 kernel、Q8_1 出力、選択条件と fallback: `sycl/src/kernels/cuda/fused_gr.dp.cpp:2378-2387,2491-2515,2685-2693,3466-3500`。
- verifier / MTP からの q8 buffer 設定と後続利用: `sycl/src/core/verify.cpp:1144-1150,1811-1814,1829-1831,1844-1846,1861-1862`、`sycl/src/core/mtp.cpp:936-952,1066-1088,1194-1218`。
- 登録状態と測定の有無: `data/settings-register.json:30990-31018`。
