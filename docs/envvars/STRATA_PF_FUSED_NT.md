# `STRATA_PF_FUSED_NT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の native fused prompt-expert 経路で、NT=256（256 threads）の WideBatch カーネル群を要求する opt-in 変数。`=256` が認識されてセットアップにも成功すると、対象形式の expert launch は 256-thread カーネルを使えるようになり、`STRATA_PF_BATCH` が `kMaxBatch` を超える場合は WideBatch でより大きな expert batch を渡せる。NT カーネルは同じ thread 内で同じ順序に積和する設計で、ソースコメントは通常 NT カーネルと同じ出力 bit としている。通常の Batch / NT=128 経路の既定値を変数単独では変更しない（`engine/src/prefill/moe_fused_iq.cu:822-825, 3856-3863, 3972-3990`; `engine/src/prefill/prefill.cpp:5784-5794`）。

## 値と判定

読み取りは `std::getenv` の後に `std::atoi(v) == 256`。未設定は無効、空文字は `atoi("") == 0` 相当で無効。文字列全体の一致検査・末尾文字検査・範囲検査はないため、先頭に空白や `+` を含む `" 256"` / `"+256"`、または `"256junk"` も変換結果が 256 となり有効。一方 `"256.0"` も整数部分で 256 となり有効、`"0256"` も有効。`"255"`、`"257"`、`"0"`、`"true"`、`"0anything"`、空文字は無効。負値は 256 にならない。数値として表現できないほど大きい文字列の `atoi` の結果は C/C++ の変換仕様上保証できず、Strata 側の検査・fallback はない（`engine/src/prefill/moe_fused_iq.cu:2783-2785`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA の NT セットアップが評価される場合 | 無効（`nt256_requested()` は false） | `256`, `+256`, ` 256`, `256junk`（`atoi` の結果が 256） | 空文字、`255`, `257`, `true`, `0anything` |
| `STRATA_PF_FUSED_F16` が先に有効な場合 | 本変数が unset または無効でも NT セットアップを要求 | `STRATA_PF_FUSED_F16` の値の先頭文字が `1` なら要求される | ただし F16 の同変数側の文字判定が別途適用される |

`STRATA_PF_FUSED_F16` は `v[0] == '1'` で判定されるため、`1`, `10`, `1tail` でも有効で、空文字や先頭が `1` 以外なら無効。この場合は NT=256 の F16 積和カーネルになり、丸めレベルで出力が変わり得る。対象変数自体の `atoi` 判定とは別のスイッチである（`engine/src/prefill/moe_fused_iq.cu:2777-2785, 2803-2809`）。

## 有効になる条件

- CUDA ビルドであること。HIP ビルドでは NT=256 の該当セットアップがコンパイル対象外であり、この実行時読み取りは行われない（`engine/src/prefill/moe_fused_iq.cu:2672-2673, 2803-2811, 2887-2890, 3007-3015`）。
- 現在の CUDA device の compute capability major が 8 以上であること。`dev_info()` はそれ未満（sm_75 を含む）では NT セットアップ箇所に達せず、その device の NT=256 は有効にならない（`engine/src/prefill/moe_fused_iq.cu:2887-2902, 3007-3015`）。
- CUDA Toolkit のコンパイラが 12.1 以降であること。nvcc 12.1 未満では WideBatch カーネルの parameter サイズ制限を理由に `setup_nt()` が常に false を返す（`engine/src/prefill/moe_fused_iq.cu:2693-2700, 2803-2809`）。
- 必要な各 NT カーネルの属性取得、共有メモリ設定、occupancy 問い合わせがすべて成功し、occupancy が 1 以上であること。どれか一つでも失敗すると `occ_nt` は 0 となる。追加の Q2_0 gate/up セットアップが `STRATA_PF_FUSED_Q2N=1` により必要になる構成では、そのセットアップも全体の成功条件に含まれる（`engine/src/prefill/moe_fused_iq.cu:2748-2764, 3007-3015`）。
- fused native prompt 経路そのものが対象 layer を選ぶこと。`STRATA_PF_FUSED=0`、小カード経路の fused override、対象外の形式・down 形式などでは本変数だけでその layer を fused 経路へ強制しない。適用形式は native 判定にも依存し、NT=256 用に列挙されたのは IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS gate/up、Q2_0 / IQ4_NL down、および `STRATA_PF_FUSED_Q2N=1` 時の Q2_0 gate/up。Q5_0 / K-quant / Q5_1 / Q8_0 / trellis / NVFP4 など NT form のない形式は WideBatch 経路では対象外（`engine/src/prefill/moe_fused_iq.cu:3415-3432, 3443-3463, 3491-3505, 3958-3968, 3979-3989`）。
- `STRATA_PF_FUSED_WS=1` が同時に指定されても、NT=256 とは別に WS カーネルのセットアップを試みる。`d.ws` が成功した場合は WideBatch の起動時に WS 側が選ばれる（`engine/src/prefill/moe_fused_iq.cu:3016-3021, 3972-3977`）。

## 実行時の詳細

`nt256_requested()` は初回評価時に `static const bool` へ結果を保存する。さらに `dev_info()` は device index ごと（32 枠）の `DevInfo` を初回取得時に構築・キャッシュし、初期化中に対象変数を読む。したがってプロセス起動後の環境変更は、判定済みのこのプロセスでは反映されない。対象変数は CLI 引数や設定ファイルによって上書きされる経路を持たない（`engine/src/prefill/moe_fused_iq.cu:2690-2691, 2783-2785, 2847-2853, 3007-3015`）。

NT セットアップが使えると、native fused の選択済み layer は通常 batch launch から WideBatch の `experts_native()` に進む。ここで `STRATA_PF_BATCH` が正数なら最大 `kBatchRoom` に clamp され、`kMaxBatch` を超える値を WideBatch が受けられるのは NT=256 または WS がセットアップ済みの場合に限る。`STRATA_PF_BATCH` 未設定・非正数なら既定の `kMaxBatch` であり、この変数だけでは expert 数を変えない（`engine/src/prefill/prefill.cpp:5784-5794`; `engine/src/prefill/moe_fused_iq.cu:3856-3863, 3952-3990`）。

## ログと測定値

要求された NT セットアップが失敗した場合、stderr に `prefill fused experts (native): STRATA_PF_FUSED_NT=256 is not available here` を出す。これは `d.ok && nt256_requested()` の場合だけで、device が sm_80 未満など `d.ok` に達しない経路ではこの警告行は出ない。通常値のままの起動時に有効化ログはない（`engine/src/prefill/moe_fused_iq.cu:3007-3015`）。

別形式を WideBatch 経路へ渡した場合は `prefill fused experts (native, NT = 256): types %d / %d are not covered here` を stderr に出し `exit(1)` する。通常の native batch 経路で対応外形式なら `prefill fused experts (native): types %d / %d are not covered here` を出して終了する（`engine/src/prefill/moe_fused_iq.cu:3697-3700, 3965-3969`）。

`docs/DETAILS.md:1817-1824` は CMP 170HX 上の著者測定として 3,256 token の MoE layer 8.27 ms を載せ、NT=256 は bitwise と記す。ただしこの箇所にはモデル、量子化、OS、実行回数など測定条件の詳細がないため、本書では一般化できる性能値として扱わない。ソースコメントでは NT カーネルの積和結果を同一 bit と説明している（`engine/src/prefill/moe_fused_iq.cu:822-825`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:2670-2700, 2777-2810` — キャッシュ対象、値の変換、F16 との OR、ビルド時の parameter サイズ条件。
- `engine/src/prefill/moe_fused_iq.cu:2847-2902, 3007-3023` — device ごとのセットアップと失敗時ログ。
- `engine/src/prefill/moe_fused_iq.cu:3415-3432, 3491-3533, 3572-3586` — native fused layer の選択条件。
- `engine/src/prefill/moe_fused_iq.cu:3856-3863, 3952-3990`; `engine/src/prefill/prefill.cpp:5784-5794` — WideBatch への dispatch と `STRATA_PF_BATCH` の関係。
- `docs/DETAILS.md:1815-1824` — 資料記載の測定値とその出典表記。
