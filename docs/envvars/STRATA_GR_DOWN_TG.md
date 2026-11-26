# `STRATA_GR_DOWN_TG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA の fused hyper-connection read が staged down projection を使うとき、1 block row が処理する token 数 `tg` を指定する。`tg` を `ct`（その down launch の token 数）の約数にすると、down kernel の grid y は `ct / tg`、dynamic shared memory は `tg` token 分となる。これは同じ down projection を処理する kernel の分割方法を変える設定で、norm や up projection の選択を直接変えるものではない（`engine/src/kernels/cuda/fused_gr.cu:1580-1607,1836-1845`）。

## 値と判定

CUDA build では `down_tg()` の最初の呼出し時に `std::getenv` で読み、`std::atoi` で整数化した結果を関数内 `static const int` に保存する。`atoi` は数値の先頭部分を読むため、空文字や数値で始まらない文字列は `0`、`"2tail"` は `2` になる。真偽文字列としては解釈しない。数値変換で表現できない範囲の入力はここでは規定しない（`engine/src/kernels/cuda/fused_gr.cu:1582-1589`）。

| 条件 | unset | 有効になる値（例） | 無効・特別扱いの値（例） |
|---|---|---|---|
| CUDA、staged down read、`ct >= 2` | GPU に応じた既定値 | `1`、`2`、`3` のうち `ct` を割り切る値。さらに `tg < ct` のとき専用分割 launch を使う | `0` は分割なし。正の値 `1..3` でも `ct` を割り切らない、または `tg == ct` なら専用分割 launch なし。`4` など範囲外の非負値も分割なし。負値は自動既定値へ |
| CUDA、`ct < 2` | `0` | なし | `ct` を見て直ちに `0` を返す |
| HIP build | `0` | なし | この関数は引数を使わず `0` を返し、環境変数を読み取らない |

具体例では、空文字、`0`、`0anything`、`true` は `atoi` の結果が `0` なので分割を無効化する。`1` は `ct` が 2 以上で割り切れ、`tg < ct` の場合に使われる。`3` は `ct=6` なら使われるが、`ct=3` では `tg == ct` のため専用分割にはならない。`-1` や `-2` は負値なので unset と同様に自動既定値へ進む（`engine/src/kernels/cuda/fused_gr.cu:1587-1607,1839-1845`）。

unset 時の CUDA 既定値は device ごとに初回判定時に保存される。Turing（compute capability 7.5）は `STRATA_SM75_PERF` が有効な場合に `ct=4` または `6` で `2`。compute capability 12.0 は `STRATA_SM120_PERF` が有効なら 80 SM 以上で `ct>=2` に `1`、80 SM 未満では偶数 `ct` に `2`。GB10（12.1）は `kGb10GrDownTg=true` の対象で、`STRATA_SM121_PERF` が有効かつ `STRATA_DEFAULTS=026` 相当の既定無効化がない場合に同じ 12.0 系判定を適用する。その他の device や条件では `0`（分割なし）。世代別 helper は各系列の環境変数を `atoi(...) != 0` で判定する（`engine/src/kernels/cuda/fused_gr.cu:1592-1607`; `engine/include/strata/core/sm75_series.hpp:24-37`; `engine/include/strata/core/sm120_series.hpp:32-38,66-81,93-97`）。

## 有効になる条件

- この読み取りと分割 launch は CUDA build に限られる。HIP build では `down_tg()` が常に `0` を返す（`engine/src/kernels/cuda/fused_gr.cu:1582-1587`）。
- fused multi-token hyper-connection read が `launch_multi()` に到達する必要がある。Q8 weight の早期経路と RDNA 専用経路は `launch_multi()` より前に戻り、`STRATA_GR_V3` が選ぶ v3 経路も対象外（`engine/src/kernels/cuda/fused_gr.cu:4286-4303,4304-4310,4424-4429`）。
- `launch_multi()` 内で `variant >= kHcStaged` かつ `s_down == nullptr` の staged down read が必要。Q8 weight は staged を使わない（`engine/src/kernels/cuda/fused_gr.cu:1173-1174,1808-1815`）。`STRATA_HC_SPLIT=0` で plain read が選ばれる場合も staged ではない。read variant の選択は `STRATA_HC_SPLIT` と fused read check による（`engine/src/kernels/cuda/fused_gr.cu:1933-1943,4732-4740,4756-4803`）。
- `STRATA_NO_MULTI_GR` が空でなく、先頭文字が `0` でもない場合は `exact_t=false` になり、`down_tg()` の結果を使う専用 launch 条件を満たさない。その場合は generic staged kernel 側へ進む（`engine/src/kernels/cuda/fused_gr.cu:1816-1820,1836-1854`）。
- launch 時点の `ct` は `down_chunk()` が決める staged chunk 上限で分割された token 数。環境値はこの実際の `ct` を割り切る必要がある（`engine/src/kernels/cuda/fused_gr.cu:1490-1507,1821-1845`）。
- 明示的な非負値は GPU 世代別既定値より優先する。`0` や範囲外値も「自動判定へ戻す」のではなく分割なしを選ぶ。CLI 引数による上書きは確認できず、コード上の判定は環境値・device default・launch 条件で決まる。

## 実行時の詳細

`fused_gr_read_multi()` は Q8 / RDNA / v3 の早期経路に該当しなければ `launch_multi()` を呼ぶ。そこで staged read の各 chunk について `down_tg(ct)` を評価し、`exact_t && 0 < tg < ct` の場合に grid y=`ct/tg`、shared memory=`tg * per_tok` の `gr_down_staged_kernel<tg, true>` を起動する。`tg` は範囲検査後 1、2、3 のみなので、それぞれ対応する template specialization に進む。条件を満たさない場合は token 数に応じた通常の staged kernel、または `STRATA_NO_MULTI_GR` 下の generic kernel を使う（`engine/src/kernels/cuda/fused_gr.cu:1815-1854,4424-4429`）。

環境値はプロセス内で初めて `down_tg()` が呼ばれた時の値に固定され、起動後に環境を変更しても再読込されない。unset の場合の GPU 判定も 64 device 分の static 配列に保存される（`engine/src/kernels/cuda/fused_gr.cu:1587,1592-1607`）。

## ログと測定値

この変数の値を表示する専用ログや、無効値に対する警告・終了処理はない。分割 launch の CUDA エラーは後続の `cudaGetLastError()` により `fused_gr_read_multi: <CUDA error string>` として stderr に出力され、`exit(1)` する経路がある（`engine/src/kernels/cuda/fused_gr.cu:4424-4429`）。

ソースコメントには、RTX 2080 Ti の cold `fused_gr_bench` で down（stamp 含む）が T=4 で 29.1→27.3 µs、T=6 で 38.5→32.2 µs（pairs）と記録される。RTX PRO 5000（80+ SM）のコメントには、`tg=1` で token 数 2/3/4/5 がそれぞれ -2.1/-2.3/-0.2/-2.5%、4 token で pairs を使わない場合との比較が -2.4% とある。GB10（48 SM）については、IQ3_S と DFlash2 drafter を使った rented Spark での 3 paired rounds の decode 値が chat/code/JSON/agent の順に -0.1/+0.7/+1.1/+0.9% と記録される。これらは資料にある個別の測定値で、別の構成での効果を示すものではない（`engine/src/kernels/cuda/fused_gr.cu:1590-1607`; `engine/include/strata/core/sm120_series.hpp:83-90`; `docs/DGX_SPARK_LINUX.md:119-126`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:1580-1608` — 値の読み取り、判定、既定値。
- `engine/src/kernels/cuda/fused_gr.cu:1808-1854` — staged 経路、chunk、分割 launch と `STRATA_NO_MULTI_GR`。
- `engine/src/kernels/cuda/fused_gr.cu:4286-4431` — Q8 / RDNA / v3 の先行経路、`launch_multi()` 呼出しとエラー経路。
- `engine/include/strata/core/sm75_series.hpp:24-37`, `engine/include/strata/core/sm120_series.hpp:32-38,66-81,83-100` — Turing / 12.0 / GB10 既定条件。
- `docs/SETTINGS.md:91` — 一覧には NVIDIA と AMD とあるが、実装は HIP build で環境変数を読まず `0` を返す。実際に本変数の分割 launch を行う根拠は CUDA 側コード。
