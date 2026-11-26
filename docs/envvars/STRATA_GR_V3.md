# `STRATA_GR_V3`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

ハイパーコネクション read の down/up 投影を、通常の multi read からストリーム分割版（`gr_down_v3_kernel` と `gr_up_v3_kernel` の 2 kernel）へ切り替える。加算順が異なるため浮動小数点の丸め結果も異なり、出力が常に bitwise 一致する設定ではない。値は `fused_gr_read_multi_slice` の v3 分岐で使われる（`engine/src/kernels/cuda/fused_gr.cu:4090-4098, 4304-4355`）。

この切替は fused multi hyper-connection read 経路でのみ評価される。通常の単独 `fused_gr_read` にはこの環境変数の read がない（同 `:4470-4485`; `engine/src/core/verify.cpp:1816-1818`）。生成時に layer の fused read を使うかは別設定・条件にも依存し、`--no-fused-gr`、GPU stages、layer/half dump、stage timing ではその layer 経路が無効になる（`engine/src/program/generate.cpp:6104-6114`; `engine/src/core/layer.cpp:1500-1502`）。

## 値と判定

CUDA と SYCL の実装はいずれも環境値を `std::getenv` で取得し、`std::atoi(value) != 0` で判定する。文字列全体の数値検証はしない。未設定と明示設定は区別される。空文字、`0`、`0anything`、`true`、`false`、数値に変換できない文字列は `atoi` が 0 を返すため OFF。`1`、`1anything`、`-1`、`2` は 0 以外となり ON。先頭空白と符号は `atoi` の規則で処理される（`" 1"` は ON）。

| 実装・条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA `fused_gr_read_multi_slice` | GPU ごとの既定判定 | `1`, `1tail`, `-1`, `2` | 空文字, `0`, `0tail`, `true`, `false` |
| SYCL `fused_gr_read_multi_slice` | OFF | `1`, `1tail`, `-1`, `2` | 空文字, `0`, `0tail`, `true`, `false` |

CUDA で未設定の場合、`STRATA_DEFAULTS=026` でなければ、離散 compute capability 12.0 かつメモリが 13 GiB 超の GPU で既定 ON。ただし `STRATA_SM120_PERF=0` は sm_120 系の既定値を無効にする。sm_121 系では `kGb10GrV3`（現行値は `false`）、`STRATA_SM121_PERF`（未設定または `atoi != 0`）、`sm121_series()` が成立する場合に既定 ON。`STRATA_DEFAULTS=026` はこの自動既定値を OFF にするが、明示した `STRATA_GR_V3` が優先する（`engine/src/kernels/cuda/fused_gr.cu:4099-4113`; `engine/include/strata/core/sm120_series.hpp:60-79, 91-101, 139-144`; `engine/include/strata/core/defaults_026.hpp:1-12, 26-29`）。それ以外、統合 GPU、GPU 情報取得失敗、device index が既定配列の範囲外の場合は既定 OFF。SYCL 実装は GPU 世代に基づく既定値を使わず、未設定は常に OFF（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202`）。

## 有効になる条件

- 対象プロセスにこの変数を読む CUDA または SYCL の fused multi read 実装が組み込まれ、その read が呼ばれること。
- CUDA では、まず Q8 projection weights がある場合は Q8 read を実行して戻る。また `rdna_gr_enabled()` が true なら RDNA read に戻るため、その呼び出しでは `STRATA_GR_V3` を評価しない（`engine/src/kernels/cuda/fused_gr.cu:4286-4305`; RDNA 判定は `engine/src/kernels/cuda/rdna_gr.cu:555-571`）。このため AMD の RDNA 経路で同変数が使われるかは `STRATA_GR_RDNA`、`STRATA_HIP_FAST_DEC`、GPU arch によって変わる。
- CUDA で v3 が選ばれても、device index が `0..63` の範囲内で、対象 read の `s_down` と `s_up` が null であることが必要。範囲外または scale pointer がある場合は通常 read に進む（`engine/src/kernels/cuda/fused_gr.cu:4306-4312, 4351-4355`）。Q8 weights 自体はその前の分岐で除外される（同 `:4286-4294`）。
- v3 の down kernel に必要な共有メモリが確保できること。CUDA は必要量 `need1` が device の opt-in 上限（取得失敗時は 48 KiB）以内で、必要な kernel attribute 設定が成功すれば split 1 を選ぶ。SYCL は device local memory が `need1` 以上なら split 1 を選ぶ（`engine/src/kernels/cuda/fused_gr.cu:4311-4348`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3173-3199`）。
- 生成の通常 layer 経路では fused read の選択条件が先に適用される。`gr_native_mmvf` が有効で、`--no-fused-gr`、GPU-stage、dump、stage-timing の各除外条件に該当せず、さらに model geometry が `fused_gr_supported` を満たす必要がある（`engine/src/program/generate.cpp:6104-6114`; `engine/src/core/layer.cpp:1500-1502`）。Verifier の multi read 経路は `fused_gr_read_persist` が read を処理した場合には呼ばれない（`engine/src/core/verify.cpp:1816-1818`）。

## 実行時の詳細

CUDA では Q8/RDNA の早期 return を通過した最初の `fused_gr_read_multi_slice` 呼び出しで `static const int v3_env` が初期化され、以降プロセス内でキャッシュされる。未設定なら GPU 既定を問い合わせる。通常は verifier 初期化時に `fused_gr_check()` が各 card の read を確認する（`engine/src/core/verify.cpp:966-969`）。SYCL も v3 判定を関数内 `static const bool` に保持し、最初の対象 read で一度だけ読む。プロセス中の環境変更は再評価されない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3174`）。

CUDA は共有メモリに `need1` が収まらず、半分の `need2` は収まる場合、既知の S=2 split の検査不一致を理由に stderr へ警告し、その card の split を `-1` にして通常 read を使う。必要量が半分も収まらない場合や device index が範囲外の場合も v3 kernel を使わず通常 readへ進むが、この分岐で専用警告は出さない。SYCL も `need1` 不足で `need2` は収まる場合に同じ警告を出すが、両方とも収まらなければ警告なしで通常 read を使う（CUDA: `engine/src/kernels/cuda/fused_gr.cu:4311-4352`; SYCL: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3173-3202`）。

v3 経路は down kernel の部分和と平方和用 scratch を作り、続けて up kernel を起動する。CUDA では launch error を `fused_gr_read_multi v3: %s` と stderr に出して `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:4352-4397`）。SYCL は同 read で q8_1 出力を書かず `false` を返す（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3289-3296`）。

## ログと測定値

共有メモリ不足時の実装上の警告は次のとおり。

```text
strata: STRATA_GR_V3=1 needs the two-half split on this card, which fails its checks (#375): the default read is used
```

CUDA v3 kernel launch error は `fused_gr_read_multi v3: <CUDA error string>` を出してプロセスを終了する。v3 を選んだこと自体を知らせる通常ログはこの分岐にはない（`engine/src/kernels/cuda/fused_gr.cu:4342-4347, 4392-4397`; SYCL の警告は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3188-3192`）。

コードコメントと `docs/DETAILS.md` は RTX PRO 5000 72 GB で decode +1.2%（245.1→248.1 tok/s、同一 token）、story prompt +6.4%（token が変化したため速度の主張ではない）、held-out document prompt +4.3%、5 pairs と記載する。また 2x RTX A4000 sm_86 では decode/prompt が -3.0%/-5.9%、RTX 3060 sm_86 では +1.0%/-3.4% とされる。これは資料・コメントにある測定値であり、この調査で再測定していない（`engine/src/kernels/cuda/fused_gr.cu:4091-4097`; `docs/DETAILS.md:1303`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:4090-4113` — 役割と CUDA 未設定時の既定値。
- `engine/src/kernels/cuda/fused_gr.cu:4252-4309` — 引数・Q8/RDNA 先行経路と環境値の判定。
- `engine/src/kernels/cuda/fused_gr.cu:4311-4397` — split 判定、警告、v3 kernel 実行と失敗処理。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202, 3289-3296` — SYCL の判定、資源条件と戻り値。
- `engine/include/strata/core/sm120_series.hpp:139-144`; `engine/include/strata/core/defaults_026.hpp:1-12, 26-29` — GPU 既定ルールと `STRATA_DEFAULTS` との関係。
- `engine/src/program/generate.cpp:6104-6114`; `engine/src/core/layer.cpp:1500-1502`; `engine/src/core/verify.cpp:966-969, 1816-1818` — production call path の選択条件。
- `engine/src/kernels/cuda/rdna_gr.cu:555-571` — RDNA read が先に選ばれる条件。
- `docs/DETAILS.md:1303` — 資料記載の測定値。
