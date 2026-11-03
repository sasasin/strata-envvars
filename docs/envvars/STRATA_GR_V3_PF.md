# `STRATA_GR_V3_PF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA/HIP fused hyper-connection read の v3（stream-split）経路で、`gr_down_v3_kernel` と `gr_up_v3_kernel` が使う load-ordering variant を bit mask で選びます。対象は読み込み順や shared-memory staging の variant で、kernel 内の計算結果は plain variant と bitwise 同じになるよう実装されています。環境変数自体は kernel 選択を直接有効化しません。v3 read が別途選ばれた場合に限り、その一部の dispatch を変えます。

## 値と判定

`std::getenv` の結果を `std::atoi` で整数に変換します。文字列全体の検証はなく、先頭の空白と符号を受け付け、数字の先頭部分を変換し、後続文字は無視します。数字が始まらない値（空文字を含む）は `0` になります。

| 値 | mask の扱い |
|---|---|
| 未設定 | device ごとの既定値を使う（以下参照） |
| `0`、空文字、数字で始まらない文字列 | 明示 mask `0`。PF variant を無効化 |
| 0 以上の整数 | その整数を bit mask として使う。例: `5tail` は `5` |
| 負の整数 | `env >= 0` の条件を満たさず、未設定時と同じ device 既定値へ進む |

使われる bit は次のとおりです。

| bit | 対象 | variant |
|---:|---|---|
| 0 | down | staging の token load をまとめて発行 |
| 1 | down | weight prefetch |
| 2 | up | partial sum と row input の load を先行 |
| 3 | up | weight prefetch |
| 4–5 | down | warp あたり 2 / 4 rows（`T <= 4` の dispatch） |
| 7 | down | register-blocked dot。dispatch は `n_tok >= 5` で R2V=2 の場合 |
| 8 | down | register-blocked dot。dispatch は R2V=4 の場合 |

bit 6 と上記以外の bit はこの dispatch では参照されません。mask は bits の組み合わせなので、`1` は down の bit 0、`5` は down bit 0 と up bit 2、`133` は bit 0・2・7 を指定します。負値を「全 bit 有効」として扱うことはなく、device 既定値に戻ります。

未設定時の既定 mask は CUDA compute capability 12.0 で `133`、それ以外では `0` です。compute capability 12.0 の既定値は `STRATA_SM120_PERF` が無効化していないこと、かつ `STRATA_DEFAULTS=026` 相当でないことを条件にします。明示した 0 以上の値はこの既定値に優先し、これらの既定値スイッチが off でも使われます。

根拠: `src/kernels/cuda/fused_gr.cu:2669-2693,2901-2907`; `include/strata/core/bw_dense_defaults.hpp:14-16`; `include/strata/core/sm120_series.hpp:30-40,58-64`; `include/strata/core/defaults_026.hpp:21-29`。

## 有効になる条件

- `fused_gr_read_multi` が v3 read に進む必要があります。`STRATA_GR_V3` が明示されていれば `atoi(...) != 0` が on/off を決め、未設定時は CUDA の compute capability 12.0、離散 GPU、13 GiB 超などの既定規則で決まります。HIP build の v3 既定値は off です。別環境変数 `STRATA_GR_V3` が off、または v3 が選ばれなければ、この mask は read に影響しません。
- Q8 down/up の入力がある read は先に Q8 kernel 経路へ return するため、v3 mask は適用されません。
- v3 が選ばれ、shared-memory 属性設定に成功して `split == 1` となった経路で mask を読み、down/up kernel の dispatch に使います。必要な shared memory が収まらない場合は `split` が `-1` のままで、v3 read 自体が使われず mask も適用されません。二分割が必要なカードでは stderr に `strata: STRATA_GR_V3=1 needs the two-half split on this card, which fails its checks (#375): the default read is used` と出します。
- bit 7 の down variant は `n_tok >= 5` で R2V=2、bit 8 は R2V=4 の dispatch を試します。bit 4–5 の row-per-warp variant は 1〜4 token 用です。これら mask 指定の dispatch が選ばれないとき、`STRATA_GR_R2` が 5〜8 token の通常 down kernel の R2V を選びます（既定 2、1/2/4 以外は 0 として generic kernel）。

## 実行時の詳細

環境値は `v3_pf_mask()` 内の function-local `static const int` で初回評価時に一度だけ読みます。初回評価は v3 read が `split == 1` となり dispatch に到達した時です。それ以降、プロセス内で環境を変更しても再評価しません。既定値の GPU 判定は別に device ごとに cache します。

通常の read ではこの環境値が採用されます。ベンチマーク用 API `fused_gr_v3_pf(mask)` が呼ばれて global override が 0 以上なら、その mask が環境値に優先します。`-1` を設定すると環境値に戻ります。この API はヘッダーで bench only とされており、通常の CLI option ではありません。該当する環境変数の読み取り・警告・ログ出力以外に、値をユーザーへ表示するログはありません。

v3 kernel launch の直後に `cudaGetLastError()` を確認します。失敗時は stderr に `fused_gr_read_multi v3: <CUDA error>` を出して `exit(1)` します。ここで調べた範囲では、mask の値自体が不正であることを知らせる警告や fallback はありません。`atoi` が整数 0 を返す値は mask 0 として通常 dispatch に進みます。

根拠: `src/kernels/cuda/fused_gr.cu:2675-2693,2838-2853,2854-2894,2901-2940,2983`; `include/strata/kernels/fused_gr.hpp:78-82`。

## 根拠

- 候補名の全参照を確認したところ、実際の環境読み取りは `src/kernels/cuda/fused_gr.cu:2676` のみです。ほかの一致はコメント、既定値 helper の説明、kernel variant の説明、bench/test 用 API 呼び出しです。
- bit の意味、kernel variant のロード順・計算順は `src/kernels/cuda/fused_gr.cu:736-755,773-785,961-991` にあります。mask による呼び分け、通常 dispatch、および `STRATA_GR_R2` の fallback は `src/kernels/cuda/fused_gr.cu:2894-2934,1592-1597` にあります。
- `docs/DETAILS.md` にはこの変数名の記述が見つからず、外部測定値は本書に転記していません。
