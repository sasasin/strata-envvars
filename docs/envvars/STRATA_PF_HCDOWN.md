# `STRATA_PF_HCDOWN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill の hyper-connection read で、down projection と inject projection を別々に計算する代わりに、対応する BF16 WMMA kernel でまとめて計算する経路を選ぶ opt-in フラグです。対応経路が完了すると down 結果 `lo` と inject 結果 `inj` が別々の出力バッファに書かれ、その後の処理は既存の SiLU・up projection・mix に続きます。ソースコメントは hipBLASLt と異なる K の積算順序による丸め差を記していますが、出力同一性や性能はこの調査では測定していません（`engine/src/prefill/prefill.cpp:1001-1006, 5108-5125`、`engine/src/prefill/wmma_gemm.cu:502-507, 580-592`）。

CUDA/HIP 共通の prefill 実装と SYCL prefill 実装にそれぞれ読み取りがあります。設定だけでは必ず kernel が起動するとは限らず、chunk・activation・weight・build・GPU 条件を満たしたときに限って選択されます（`engine/src/prefill/prefill.cpp:1004-1007, 5101-5124`、`engine/sycl/src/prefill/prefill.cpp:387-390, 3438-3459`）。

## 値と判定

両実装とも `std::getenv("STRATA_PF_HCDOWN")` の結果について、値が存在し、かつ `e[0] == '1'` かだけを関数内 `static const bool` に保存します。文字列全体の parse や数値検査はありません（`engine/src/prefill/prefill.cpp:1004-1007`、`engine/sycl/src/prefill/prefill.cpp:387-390`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA/HIP 共通 prefill / SYCL prefill | 無効 | `1`、`1anything`、`10` | 空文字、`0`、`true`、` 1`、`01` |

先頭 1 byte が ASCII `1` なら後続文字列は判定に影響しません。大文字小文字・空白・数値としての妥当性を検査せず、先頭が `1` でない値は無効です。環境変数自体に CLI 引数や別設定からの上書き処理はありません。

## 有効になる条件

- HC read を実行する prefill chunk である必要があります。`T` が `max(STRATA_PF_SWITCH_MIN_T, 64)` 以上であることが必要です。`STRATA_PF_SWITCH_MIN_T` は別の関数内 `static` で `atoll` 読み取りされ、未設定なら `0` です。そのためこの経路の下限は常に 64 token で、同変数を 64 より大きくすると閾値も上がります（`engine/src/prefill/prefill.cpp:975-978, 1016, 5101-5104`、`engine/sycl/src/prefill/prefill.cpp:372-375, 399, 3438-3440`）。
- stride を padded にする条件として `!gr_unfused()` かつ `!m.xn16_lo` も必要です。満たすと `ldx = D + 64`（この hyper-connection の `D` は 10240）になります。`STRATA_GR_UNFUSED=1` または低位 BF16 activation (`m.xn16_lo`) があると `ldx == D` になり、この fused 分岐を通らず通常の down / inject projection に進みます（`engine/src/prefill/prefill.cpp:1008, 1016, 5101-5104, 5124-5125`、`engine/sycl/src/prefill/prefill.cpp:391, 399, 3438-3440, 3459-3460`）。
- padded stride になった場合でも、CUDA/HIP 実装では `wd->q8_scale == nullptr` が必要です。BF16-in-F32 の down / inject weight と data、期待する次元（down: `D × LR`、inject: `D × HC`）を満たし、kernel 呼び出しが成功する必要があります。`q8_scale` がある場合はこの fused 呼び出しを選ばず、通常の各 projection に進みます（`engine/src/prefill/prefill.cpp:5091-5099, 5111-5124`）。
- 実 kernel は HIP の WMMA build/device 対応が必要です。`strata_pf_hcdown_bf16` は入力ポインタ、`T >= 64`、正の `nd`、`K % 64 == 0`、`ldx >= K`、`ldx % 8 == 0`、上限値、対応 device を検査し、未対応なら `false` を返します。kernel は `STRATA_WMMA_GFX11` build でコンパイルされる経路で、device 判定は gfx1100/1101/1102/1103/1150/1151 を対象にしています（`engine/src/prefill/wmma_gemm.cu:34-40, 44-57, 514-520, 675-684`）。
- 対応 kernel が build にない場合も注意が必要です。非 `STRATA_USE_HIP` build のヘッダー実装は常に `false` を返します（`engine/src/prefill/wmma_gemm.h:29-35`）。この場合、上記の padded stride と weight 条件まで進んだ `STRATA_PF_HCDOWN` 有効経路はエラーになります。SYCL prefill にも同じ環境判定と失敗分岐があります（`engine/sycl/src/prefill/prefill.cpp:387-390, 3446-3459`）。
- `STRATA_HCD_EXACT` も `hc_pad()` を通じて padded stride を要求しますが、両方が有効で条件を満たす場合、分岐は `!pf_hcdown()` を満たさないため exact-only kernel ではなく本変数の fused down+inject 経路を選びます（`engine/src/prefill/prefill.cpp:1009-1016, 5111-5122`、`engine/sycl/src/prefill/prefill.cpp:392-399, 3446-3457`）。
- ソースにこの変数を読む箇所は CUDA/HIP 共通 prefill と SYCL prefill だけです。CLI とサーバーモード独自の設定分岐はなく、両モードが同じ prefill 実装を呼ぶ範囲で適用されます。

## 実行時の詳細

各 backend の `pf_hcdown()` は関数内 static を初回呼び出し時に初期化します。CUDA/HIP 共通実装では `hc_pad()` が呼ばれる stride 判定と projection 選択で参照され、SYCL でも同様です。したがってプロセス起動後に環境値を変えても、既に初期化された backend の判定値は変わりません（`engine/src/prefill/prefill.cpp:1004-1007, 1016, 5101-5114`、`engine/sycl/src/prefill/prefill.cpp:387-390, 399, 3438-3449`）。

有効条件を満たすと、kernel は `xn16` を入力として down (`lo`) と inject (`inj`) の両方を計算します。呼び出しが失敗した場合、または weight の形式・次元条件に合わない場合、コードは `prefill: STRATA_PF_HCDOWN could not run the hyper-connection projections` を `err` に設定して `false` を返します。ここでは標準 projection への fallback は行いません。成功時は `hcd` が立ち、別個の down と inject projection 呼び出しをスキップします（`engine/src/prefill/prefill.cpp:5114-5125`、`engine/sycl/src/prefill/prefill.cpp:3449-3460`）。

## ログと測定値

有効化や通常の成功を知らせる専用ログはありません。失敗時の `err` は上記のとおりです。通常 CLI の prompt forward は `forward: %s` として stderr に出して終了コード `1` を返します。サーバー側は `forward_chunk` の失敗後に `ERR forward: %s` を protocol 出力へ送り、終了コード `1` でその処理を終えます（`engine/src/hy4flash/run/hy4_main.hip.cpp:791-796`、`engine/src/hy4flash/run/hy4_serve.hip.h:502-507, 527-529`）。

kernel ソースコメントには別の probe での時間と hipBLASLt 時間が記載されていますが、対象環境変数の効果を示す条件付きの製品測定値とは確認できないため、本書では性能値として引用しません（`engine/src/prefill/wmma_gemm.cu:502-507`）。

## 根拠

- 全直接参照（読み取り・分岐・エラー）: `engine/src/prefill/prefill.cpp:1001-1007, 5101-5124`、`engine/sycl/src/prefill/prefill.cpp:384-390, 3438-3459`
- 値の stride への反映と相互作用: `engine/src/prefill/prefill.cpp:975-978, 1008-1016, 5091-5104`、`engine/sycl/src/prefill/prefill.cpp:372-375, 391-399`
- WMMA kernel と build/device 条件: `engine/src/prefill/wmma_gemm.h:26-35`、`engine/src/prefill/wmma_gemm.cu:34-57, 502-507, 675-684`
- 観測できる CLI 側の失敗: `engine/src/hy4flash/run/hy4_main.hip.cpp:791-796`
