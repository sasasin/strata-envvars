# `FNX_PF_HCSPLIT_MIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

ハイパーコネクション読み取りをカード間で分割する prompt 処理で、1 pass に必要な chunk 数のしきい値と、短い末尾 chunk を別 pass に分ける位置を指定する。既定値は 3。前者を満たさない pass では split read を使わず、後者では末尾を先行する全 chunk と同じ pass に残す。値は生成内容や CLI の選択を直接指定するものではなく、該当する prompt の chunk 分割と hyper-connection read の実行経路に作用する（`engine/src/split/src/prefill.cu:1340-1348,1436-1444`）。

## 値と判定

`fnx::env_int` は `std::getenv` で値を取得し、符号任意の 10 進整数として文字列全体を `strtoll` で変換する。未設定なら呼び出し側の既定値 3。空文字、符号だけ、数字以外、末尾に文字がある値、`long long` の範囲外は受け付けず、`FNX_PF_HCSPLIT_MIN: '<値>' is not a whole number` という `std::runtime_error` を投げる。先頭・末尾の空白も受け付けない。`+3`、`03`、`0`、負の整数は構文上受理される。parse 後に `int` へ cast し、正の下限・上限や clamp は設けていない（`engine/src/split/src/env.hpp:15-21,33-40`; 読み取り箇所は `engine/src/split/src/prefill.cu:1341,1441`）。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| 全 build の `Engine::prefill` | 3 | 整数構文の値。短い末尾 chunk の分割位置に使うのは HCS split が有効な場合 | 空文字、`3x`、空白を含む値などは例外 |
| 全 build の `Engine::prefill_pass` | 3（初回の値を static cache） | 整数構文の値。pass 内 chunk 数がこの値以上なら HCS split の候補になる | 空文字、`3x`、空白を含む値などは例外 |

値 3 の場合、HCS split が有効なら短い末尾 chunk の直前に全 chunk が 3 個以上あれば末尾を次の pass に回す。また pass 内 chunk 数が 3 未満ならその pass の split read を無効にする。値 0 や負数も parse され、pass 数の比較では実質的に split の chunk 数しきい値をなくす。値を大きくすると split に必要な pass の chunk 数が増える。短い末尾 chunk の振り分けにも同じ値が使われる（`engine/src/split/src/prefill.cu:1340-1348,1440-1444`）。

## 有効になる条件

- split engine の prompt path で読む。`FNX_PF_HCSPLIT_MIN` の値自体には OS や CLI 引数による別の優先順位はない。対象名の直接参照は `prefill.cu` の 2 箇所で、動的な名前渡しは確認されなかった（`engine/src/split/src/prefill.cu:1341,1441`）。
- threshold によって HCS split の実動作が変わるのは、非 HIP build、カード数が 2、`FNX_PF_RING_SM` が 0、`FNX_PF_OVERLAP` と `FNX_PF_HCSPLIT` が非 0 で、さらに各カードで HCS 用の校正済み GEMM algorithm が見つかり split が有効になった場合。初期化時に全カードで条件を満たす必要があり、満たさなければ HCS split は無効になる（`engine/src/split/src/prefill.cu:1063-1069,1080-1093,1100-1102,1149-1159`）。
- split が有効でも、pass の chunk 数がしきい値未満、chunk のいずれかが 512 行未満、または HCS mode 1 で calibration / 4096 行 chunk 条件を満たさない場合は、その pass の split read を行わない（`engine/src/split/src/prefill.cu:1436-1444`）。
- HIP build では HCS split の設定と有効化が `#if !FNX_HIP` の内側にあるため、この変数で split 動作は有効にならない。ただし `Engine::prefill` と `prefill_pass` の読み取りは共通コードにあり、無効な文字列なら HIP でも例外になる（`engine/src/split/src/prefill.cu:1066-1068,1090-1094,1340-1342,1436-1442`）。

## 実行時の詳細

1. `Engine::prefill` は毎回 `FNX_PF_HCSPLIT_MIN` を読み、`pf_[0]->hcs` が true のとき、短い末尾 chunk の直前にすでに積んだ chunk 数が値以上なら、その末尾を現在の pass に追加せず次の pass に回す。したがってこの読み取りは process 起動後に環境値が変われば次の `prefill` 呼び出しで反映される（`engine/src/split/src/prefill.cu:1300,1338-1348`）。
2. `prefill_pass` は関数内 `static const int hcs_min` として同じ名前を一度読み、最初の初期化時の値を後続の全 pass で使う。後から環境値を変えてもこのしきい値には反映されない。pass の chunk 数が値未満なら `hs` を false にし、HCS read を通常経路にする（`engine/src/split/src/prefill.cu:1436-1444`）。
3. 値の指定は CLI 引数や別の環境変数で上書きされない。ただし HCS split の前提が満たされなければ `lone_min` による末尾 chunk の分割は適用されず、`hcs_min` の判定で `hs` は元から false のままになる。

## ログと測定値

この変数専用のログはない。HCS split の初期化時、split が利用可能なら `fnx: prompt path: the hyper-connection read is split between the cards (%s)`、利用を求めたがカード上で同じ結果になる cublasLt algorithm がなければ `fnx: prompt path: the hyper-connection read stays on both cards (no cublasLt algorithm that gives the same rows at 2048 and 4096 rows on this card)` が stderr に出る（`engine/src/split/src/prefill.cu:1149-1159`）。

不正値は helper が例外を投げる。`fnx_run` では `fnx_run: <例外文>` を stderr に出して終了コード 1、`sfnx` の致命的エラー経路では `ERR <例外文>` と `sfnx: failed: <例外文>` を出して終了コード 1 となる（`engine/src/split/src/env.hpp:34-39`; `engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102`）。この変数に結び付いた測定値は記載されていない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数 parse、未設定時既定値、不正値例外。
- `engine/src/split/src/prefill.cu:1340-1348` — 毎回読む値による末尾 chunk の pass 分割。
- `engine/src/split/src/prefill.cu:1063-1102,1149-1159` — build / backend / card / overlap / ring 条件、HCS split 初期化と calibration、観測ログ。
- `engine/src/split/src/prefill.cu:1436-1444` — 初回値を cache する split chunk 数判定と pass 内の追加条件。
- `engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102` — 不正値例外の出力と終了経路。
