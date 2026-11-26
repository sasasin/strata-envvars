# `STRATA_GR_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

gfx906 向けの `fused_gr_read_multi` で、hyper-connection の down 投影を K 方向に分割する経路を opt-in する。`STRATA_GR_SPLIT=1` のとき、通常の norm/down/up の multi read に代えて norm、K-split down、固定順での down finish、up の各 kernel を同じ stream に投入する。合計順序が単一 token read と異なり、multi read の結果は単一 token 呼び出し T 回と bitwise 一致しなくなるため、既定では無効である（`engine/src/kernels/cuda/fused_gr.cu:4399-4425`）。

この読み取りは `STRATA_HIP_GFX906` でコンパイルした場合に限り存在する。これは CUDA コードを HIP で gfx906 向けにビルドする互換 backend であり、wave32 の通常 HIP backend や CUDA build にはこの環境変数の分岐は含まれない（`engine/CMakeLists.txt:91-103`、`engine/cmake/backends/hip.cmake:6-23`、`engine/include/strata/platform/hip_compat/strata_hip.h:24`）。

## 値と判定

コードは `getenv` で値を得て、その文字列全体が厳密に `"1"` と一致するかを比較する。数値変換や trim はしない。未設定、空文字、`0`、`true`、`01`、` 1`、`1 `、`0anything` はすべて無効である（`engine/src/kernels/cuda/fused_gr.cu:4404`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_HIP_GFX906` build の `fused_gr_read_multi` が split 判定まで到達 | 無効 | 文字列全体が `1` | 空文字、`0`、`true`、`01`、前後に空白がある `1` |
| gfx906 以外の build | この変数の分岐なし | なし | 値はこの実装では参照されない |

## 有効になる条件

- 実行ファイルが `STRATA_HIP_GFX906` build であること。実機の GPU 種別を実行時に判定してこのマクロ分岐に入る仕組みではない。
- `fused_gr_read_multi_slice` が split 判定に到達すること。q8 down/up weights がある場合は先行する `launch_q8` 経路から戻る。`rdna_gr_enabled()` が true の場合も RDNA read 経路から戻る（`engine/src/kernels/cuda/fused_gr.cu:4286-4303`）。
- `STRATA_GR_V3` 経路が選ばれてそこで戻る場合、`STRATA_GR_SPLIT` の分岐には到達しない。V3 の条件を満たさず標準 read にフォールバックした場合は、後続の split 判定に進む（`engine/src/kernels/cuda/fused_gr.cu:4304-4352`）。
- `a[0].s_down == nullptr` であること。scale 付き q8 down weights の場合は split 経路を使わず、その後の標準 multi read に進む（`engine/src/kernels/cuda/fused_gr.cu:4404-4425`）。
- `STRATA_GR_FAST` は split の有効・無効を決めない。gfx906 では `STRATA_GR_FAST` が未設定なら fast norm/up kernel を選び、`atoi` が 0 になる値なら通常の multi norm/up kernel を選ぶ。split down と finish はどちらでも投入される（`engine/src/kernels/cuda/fused_gr.cu:4073-4084,4404-4415`）。
- CLI 引数による優先順位や上書きはこの分岐にはない。該当箇所で確認できるのは環境変数と上記のコード条件である。

## 実行時の詳細

`fused_gr_read_multi` は通常、verify の GR group read などから呼ばれ、各 token の `FusedGrArgs` と scratch、stream を `fused_gr_read_multi_slice` に渡す（`engine/src/core/verify.cpp:1805-1818`）。split 判定はこの slice 関数の q8/RDNA/V3 経路の後にある（`engine/src/kernels/cuda/fused_gr.cu:4254-4260,4286-4405`）。

判定値は関数内 `static const bool` に保存され、最初にこの宣言まで到達した時点で初期化される。同一プロセス内の以後の呼び出しでは環境を再読しないため、実行中の環境変更は反映されない（`engine/src/kernels/cuda/fused_gr.cu:4404`）。初期化式はまず `getenv` で未設定かを調べ、設定されている場合にもう一度 `getenv` した文字列を `std::string` にして完全一致を調べる。

分岐に入ると `gr_fast()` の選択に応じて `gr_norm_fast_kernel` または `gr_norm_multi_kernel` を起動し、`gr_down_split_kernel` と `gr_down_finish_kernel` を続けて起動する。その後 `gr_up_fast_kernel` または `gr_up_multi_kernel` を起動し、q8_1 出力はこの経路からは返さず `false` を返す（呼び出し側が必要な量子化を行う）（`engine/src/kernels/cuda/fused_gr.cu:4405-4421`）。

## ログと測定値

この分岐が選ばれたことを示す専用の有効ログはない。最後の kernel launch 後に `cudaGetLastError()` が成功以外を返すと、stderr に `fused_gr_read_multi: <GPU error string>` を出して `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:4416-4419`）。

ソースコメントは「~3% faster per verify window」と記し、`docs/AMD_HIP.md:607` も「about 3% per window」と記載する。ただし、これらの箇所には測定機種・モデル・設定・測定方法が示されていないため、この文書では一般的な性能値として扱わない。ソースコメントは summation order が変わり、`gr_parity` の単一 token 呼び出しとの bitwise 一致契約を満たさなくなるとも説明している（`engine/src/kernels/cuda/fused_gr.cu:4400-4403`）。

## 根拠

- 候補名の実コード参照と値判定: `engine/src/kernels/cuda/fused_gr.cu:4404-4405`。
- 先行 read 経路と V3 判定: `engine/src/kernels/cuda/fused_gr.cu:4286-4309,4351-4352`。
- kernel 起動、結果、失敗経路: `engine/src/kernels/cuda/fused_gr.cu:4405-4421`。
- gfx906 build macro: `engine/CMakeLists.txt:91-103`、`engine/cmake/backends/hip.cmake:6-23`。
- verify からの呼び出し例: `engine/src/core/verify.cpp:1805-1818`。
