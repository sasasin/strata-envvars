# `STRATA_GR_FAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

複数トークンをまとめて処理する hyper-connection read の通常経路で、norm と up projection に latency-hidden カーネルを選ぶ。対象カーネルは `gr_norm_fast_kernel` と `gr_up_fast_kernel`。単一トークン用の `fused_gr_read` はこの値を参照せず、`gr_down_kernel` / `gr_up_kernel` を起動する。複数トークン経路でも down projection のカーネル選択はこの変数では変わらない（`engine/src/kernels/cuda/fused_gr.cu:1514-1520`, `1778-1795`, `1882-1930`, `4528-4555`）。

## 値と判定

`gr_fast()` の初回呼び出し時に `std::getenv("STRATA_GR_FAST")` を一度だけ読み、設定されていれば `std::atoi(v) != 0` を有効とする。`atoi` は文字列全体の妥当性検証をせず、先頭の空白と符号の後の十進数字を読み、最初の非数字以降を無視する。このため空文字、数字に変換できない文字列、`0`、`0anything` は無効、`1`、`1anything`、`-1` は有効。`true` / `false` はいずれも先頭から数値を変換できないため無効であり、大文字小文字の比較はしない。範囲検査や clamp はない。`atoi` の表現範囲を超える数値の結果はこの実装で規定されない（`engine/src/kernels/cuda/fused_gr.cu:4073-4084`）。

| ビルド条件 | unset | 設定時に fast を選ぶ値 | 設定時に fast を選ばない値 |
|---|---|---|---|
| CUDA（`!__HIPCC__`） | `STRATA_SM70_TABLE` が設定され、`atoi` が非 0 で、現在の device が Volta (`sm_70`) の場合だけ on。それ以外は off | `atoi` が非 0（例: `1`, `-1`, `1x`） | `atoi` が 0（例: 空文字、`0`, `0x`, `true`, `false`） |
| HIP gfx906（`STRATA_HIP_GFX906`） | on | `atoi` が非 0 | `atoi` が 0 |
| その他の HIP build | この fast path は build macro によりコンパイルされず、変数の読み取りもない | 該当なし | 該当なし |

CUDA の unset 時は、`STRATA_SM70_TABLE` 自身が `nullptr` でないことと `atoi(v) != 0` の両方が必要。したがって空文字は off、`1tail` は on。Volta 判定は現在 device の compute capability major/minor が 7.0 の場合に成立する（`engine/src/kernels/cuda/fused_gr.cu:48-53`, `1404-1424`, `4075-4084`）。

## 有効になる条件

- `STRATA_GR_FAST_BUILD` が有効な build であること。ソース上では全 CUDA build と `STRATA_HIP_GFX906` build が該当し、それ以外の HIP build では fast kernels と環境変数読み取りがコンパイルされない（`engine/src/kernels/cuda/fused_gr.cu:48-53`, `4073-4087`）。
- 複数トークン read が `fused_gr_read_multi_slice` の通常経路から `launch_multi` に到達すること。Q8 の専用経路と `rdna_gr_enabled()` の経路は先に return する。V3 read が選ばれた場合も専用 kernels を起動して return するため、この変数は適用されない（`engine/src/kernels/cuda/fused_gr.cu:4286-4303`, `4304-4309`, `4351-4398`, `4424-4431`）。
- gfx906 HIP では `STRATA_GR_SPLIT=1` かつ `s_down == nullptr` の専用 split 経路も `gr_fast()` を使う。ただし `STRATA_GR_V3` が先に選ばれて return する場合や Q8 / RDNA 経路では到達しない（`engine/src/kernels/cuda/fused_gr.cu:4295-4303`, `4304-4309`, `4399-4422`）。
- 通常経路の norm は、選択された `variant` が split / staged の場合 `STRATA_GR_NORM_FAST` 側の `norm_fast_on()` で決まり、`STRATA_GR_FAST` は up の fast kernel 選択にだけ関与する。plain variant では norm にもこの変数が使われる（`engine/src/kernels/cuda/fused_gr.cu:1782-1795`, `1882-1885`）。
- `q8w`（`m.a[0].s_down != nullptr`）なら fast norm の選択は残るが、fast up kernel は `!q8w` 条件により選ばれない。`STRATA_GR_UP_WIDE` が有効で Q8 混合出力もない場合は wide up kernel が先に選ばれ、fast up kernel に進まない（`engine/src/kernels/cuda/fused_gr.cu:1780-1795`, `1870-1885`）。
- ベンチ用 API `fused_gr_set_fast(int)` が `g_gr_fast >= 0` を設定していればその値（0 は off、正数は on）が環境変数と既定値より優先される。ヘッダーはこの API を bench only としている（`engine/src/kernels/cuda/fused_gr.cu:4074-4088`, `engine/include/strata/kernels/fused_gr.hpp:78-80`）。

## 実行時の詳細

環境値はプロセス起動時ではなく、`gr_fast()` が最初に呼ばれたときに function-local `static const int env` としてキャッシュされる。同じプロセス内で後から環境値を変えても、このキャッシュ値は更新されない。`fused_gr_set_fast` による上書きは別の `g_gr_fast` を毎回参照するため、setter が変更すれば優先値が切り替わる。未設定時の CUDA fallback に使う `STRATA_SM70_TABLE` は `gr_fast()` の呼び出しごとに参照され、`cur_dev_volta()` は device ごとに判定を cache する（`engine/src/kernels/cuda/fused_gr.cu:1404-1424`, `4073-4088`）。

通常の `fused_gr_read_multi` は 8 トークン以下をそのまま slice 処理し、それを超える場合は最大 8 トークンずつに分ける。各 slice の通常経路で `launch_multi` が fast 判定を使う。単一トークン API `fused_gr_read` には `gr_fast()` の呼び出しがない。Strata のこの実装箇所には、対象変数を子プロセスへ渡す・上書きする処理はない（`engine/src/kernels/cuda/fused_gr.cu:4424-4431`, `4470-4485`, `4528-4555`）。

## ログと測定値

この変数の読み取りや on/off 判定自体はログを出さない。選択経路で GPU launch error が検出された場合は `fused_gr_read_multi: <cuda error string>` を stderr に出して `exit(1)` する。これは fast 値専用のエラーではなく、通常 read の共通エラー処理（`engine/src/kernels/cuda/fused_gr.cu:4424-4431`）。

## 根拠

- build 条件と fast kernels 宣言: `engine/src/kernels/cuda/fused_gr.cu:48-53`, `1514-1520`
- parse、既定値、cache、bench override: `engine/src/kernels/cuda/fused_gr.cu:4073-4088`
- CUDA Volta 判定: `engine/src/kernels/cuda/fused_gr.cu:1404-1424`, `4079-4084`
- 通常の norm / up 選択、Q8・wide の除外: `engine/src/kernels/cuda/fused_gr.cu:1778-1795`, `1870-1930`
- Q8 / RDNA / V3 / gfx906 split と通常経路への分岐: `engine/src/kernels/cuda/fused_gr.cu:4286-4309`, `4351-4429`
- 単一・複数トークン API と slice: `engine/src/kernels/cuda/fused_gr.cu:4424-4485`, `4528-4555`; API の bench-only 注記: `engine/include/strata/kernels/fused_gr.hpp:78-80`
