# `STRATA_GR_DOWN_TG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の fused hyper-connection read にある staged down kernel で、1ブロック行が処理する token 数（`tg`）を指定します。通常の staged kernel を置き換える設定ではなく、値が許可され、token 数を割り切り、該当する staged 経路が選ばれたときだけ、token 群を `tg` ごとのブロック行に分ける特別な launch を使います。HIP ビルドではこの環境変数を読みません。

## 値と判定

値は `std::atoi` で変換されます。空白や数値の後続文字を含む文字列も `atoi` の変換規則で扱われ、文字列全体の妥当性は検査されません。変換結果に対する動作は次の通りです。

| 状態・変換値 | `down_tg(ct)` の結果 |
|---|---|
| unset（内部値 `-1`） | 自動選択へ進む。対応する Turing GPU では `ct` が4または6のとき `2`、それ以外は `0`。 |
| 0（空文字、非数値文字列を含む） | `0`。環境変数による分割 launch を使わない。 |
| 1、2、3 | `ct >= 2` かつ `ct % 値 == 0` の場合にその値を返す。それ以外は `0`。 |
| 4以上 | `0`。許可範囲外。 |
| 負数 | 自動選択へ進む（unset と同じ分岐）。 |

`ct < 2` は環境変数の値にかかわらず `0` です。したがって `STRATA_GR_DOWN_TG=0` は「staged down kernel を無効化」する指定ではなく、特別な `tg` 分割だけを無効にします。`atoi` のため、例えば `2junk` は2、`junk` は0、`-2` は自動選択扱いです。

## 有効になる条件

- CUDA の `fused_gr.cu` でのみ環境値を読みます。HIP コンパイル時の `down_tg()` は常に0を返します。
- `fused_gr_read_multi()` の標準経路を通る必要があります。Q8 down/up 重みの経路と、利用可能な場合の `STRATA_GR_V3` 経路は `launch_multi()` より前に分岐するため、この設定はその経路には適用されません。
- `launch_multi()` で staged variant が選ばれ、かつ `s_down == nullptr` である必要があります。staged variant は `STRATA_HC_SPLIT` と per-device の fused GR 検査により決まり、対応 variant が検査で通らなければ plain または split へ fallback します。
- `STRATA_NO_MULTI_GR` が空でなく、先頭文字が `0` でない場合、`exact_t` が false になり、この特殊分割と token 数別の staged kernel 選択は使われません。
- 自動選択は `sm75_default()` を満たすデバイスでのみ行います。これは compute capability 7.5（または `STRATA_EMULATE_CC=75` による同等判定）かつ `STRATA_SM75_PERF` が `atoi` で非0の場合です。環境変数を明示した正の値1〜3による指定には、この自動選択の Turing 条件は掛かりませんが、上記の CUDA/staged 経路条件は残ります。

実行ファイルで fused GR が設定されるのは native MMVF が有効で、`--no-fused-gr`、GPU stages、layer/half dump、stage timing によって無効化されない場合です。

## 実行時の詳細

CUDA の `down_tg()` 内で環境値を関数ローカル `static const int` にキャッシュします。したがって最初の評価後にプロセス環境を書き換えても、この設定値は再読込されません。デバイス別の自動選択可否も `per_dev[64]` にキャッシュされます。

`tg` が1〜3で `tg < ct` の場合、launch grid のY次元を `ct / tg` とし、各ブロック行が `tg` token を処理する staged kernel を選びます（`tg` 1、2、3の明示的な template instantiation）。返り値が0、または `tg >= ct` の場合は通常の staged kernel dispatch に進みます。そこで `exact_t` が有効なら `ct` 1〜6の専用 instantiation、それ以外は一般 kernel を使います。

ソースコメントには、RTX 2080 Ti の cold `fused_gr_bench` で down と stamp を含む時間が token 4で29.1→27.3 µs、token 6で38.5→32.2 µs（pairs）と記載されています。これはソースコメントに記されたベンチ結果であり、通常の decode 性能を保証する測定ではありません。`docs/DETAILS.md` はこの変数を Turing kernel series の個別スイッチとして列挙しています。

## 根拠

- `src/kernels/cuda/fused_gr.cu:1208-1230` — 値の読み取り、`atoi`、明示値の範囲・割り切り判定、および Turing 自動選択。
- `src/kernels/cuda/fused_gr.cu:1252-1259,1271-1294` — staged 条件、`STRATA_NO_MULTI_GR` 条件、特殊 launch と通常 staged dispatch。
- `src/kernels/cuda/fused_gr.cu:2217-2324` — Q8/V3 分岐と標準 `launch_multi()` 経路。
- `src/kernels/cuda/fused_gr.cu:1360-1370,2530-2571` — `STRATA_HC_SPLIT` による variant 選択と per-device 検査・fallback。
- `include/strata/core/sm75_series.hpp:24-43` — `STRATA_SM75_PERF` の読み取りと compute capability 7.5 判定。
- `src/program/generate.cpp:3670-3679` — generate 実行経路で fused GR を有効にする条件。
- `docs/DETAILS.md:2244-2257` — Turing kernel series と同変数の位置付け。
