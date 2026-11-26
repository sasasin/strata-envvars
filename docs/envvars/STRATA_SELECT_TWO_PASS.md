# `STRATA_SELECT_TWO_PASS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の chunk-major prompt prefill における QSA block selection で、tensor-core scorer が使えるとき、全 block をまず単精度 TF32 で採点し、誤差範囲が top-k の境界にかかる候補だけを通常の 3xTF32 で再採点する経路を要求する。最後の `qsa_block_topk` は同じ selection row を読む。通常経路と同じ選択結果になるという設計・測定上の説明は `docs/DETAILS.md` にあるが、この調査では性能や結果の再測定はしていない（`engine/src/prefill/prefill.cpp:5354-5393`, `engine/src/kernels/cuda/qsa_select.cu:3259-3265`, `docs/DETAILS.md:1310-1320`）。

これは opt-in で、値が有効でも全 prompt・全 query batch が二段 scorer を通るわけではない。対象の scorer は CUDA 実装にあり、HIP 実装は要求を使わない旨を警告して `false` を返す（`engine/src/kernels/cuda/qsa_select.cu:3896-3902,4008-4021`）。

## 値と判定

`RequestStatus::requested_from` は `getenv` の結果が null でなく、かつ文字列全体がちょうど `"1"` の場合だけ `true` にする。未設定、空文字、`0`、`true`、`01`、`1x`、前後に空白のある値はすべて無効。数値変換や大文字小文字変換はしない（`engine/include/strata/kernels/qsa_two_pass_status.hpp:12-18`）。

| 実行経路 | unset | 有効になる値 | 無効になる値 | 判定後の動作 |
|---|---|---|---|---|
| CUDA の chunk-major selection | 二段 scorer を要求しない | 厳密に `1` | 空文字を含む上記以外 | 要求は GPU・selection 経路・閾値・buffer 条件を満たすときだけ使う。条件不足時は通常 scorer に戻る（`engine/src/kernels/cuda/qsa_select.cu:3896-3902`, `engine/src/prefill/prefill.cpp:5361-5392`）。 |
| HIP / Metal / SYCL | 要求しない | 厳密に `1` でも利用不可 | 空文字を含む上記以外 | `1` のとき一度 stderr に未使用の理由を出し、selection は通常経路のまま（HIP: `engine/src/kernels/cuda/qsa_select.cu:4008-4012`, Metal: `engine/src/prefill/prefill.cpp:9633-9635`, SYCL: `engine/sycl/src/prefill/prefill.cpp:5959-5962`）。 |
| CUDA layer-major prompt path | 要求しない | 厳密に `1` でもこの walk では利用不可 | 空文字を含む上記以外 | layer-major の walk ではこの変数を selection に適用せず、設定時は一度警告（`engine/src/prefill/prefill.cpp:9677-9684`）。 |

既定値として二段 scorer は無効。別環境変数 `STRATA_SELECT_TWO_PASS_MIN` の未設定時既定値は 4096 blocks だが、これは本変数の parse 値を変えず、呼び出しサイズの閾値を決める（`engine/include/strata/kernels/qsa_two_pass.hpp:60-62`, `engine/src/prefill/prefill.cpp:5363-5369`）。

この switch の読み取りは `getenv` であり、CLI 引数や設定ファイルによる優先・上書き処理はこの実装にない。QSA block selection を行う prompt prefill の経路に限られ、decode の selection や QSA selection を通らない prompt には作用しない（`engine/src/kernels/cuda/qsa_select.cu:3896-3898`, `engine/src/prefill/prefill.cpp:5354-5393`）。

## 有効になる条件

- 値が厳密に `1` であること。空文字など「設定されているだけ」では要求されない（`engine/include/strata/kernels/qsa_two_pass_status.hpp:12-18`）。
- CUDA build の chunk-major prompt selection であること。HIP / Metal / SYCL および CUDA layer-major prompt walk は対象外（`engine/src/kernels/cuda/qsa_select.cu:4008-4021`, `engine/src/prefill/prefill.cpp:9630-9635,9677-9684`, `engine/sycl/src/prefill/prefill.cpp:5959-5962`）。
- QSA block selection を行う prompt prefill の処理を通ること。decode や QSA selection を使わないモデル・実行経路には呼び出し箇所がなく、この switch の作用はない（`engine/src/prefill/prefill.cpp:5354-5393`）。
- 現在の CUDA card で通常の tensor-core scorer が使えること。compute capability major が 8 以上で、`STRATA_QSA_WARP` が `1` または `select` でなく、必要な kernel shared-memory 属性設定が成功すること。カードごとの可否は `tp_device_ok` の `ok[64]` に保存される（`engine/src/kernels/cuda/qsa_select.cu:3873-3892`）。
- `STRATA_SELECT_OLD` が未設定であること。コードは値を parse せず `getenv(...) != nullptr` を使うため、空文字を含め設定されていると旧 selection を選び、二段 scorer を呼ばない（`engine/src/prefill/prefill.cpp:5377-5392`）。
- prompt の最終 query が `STRATA_SELECT_TWO_PASS_MIN` 以上の block 数を持ち、各 batch の最終 query (`active`) も同じ閾値以上であること。閾値環境変数の未設定既定値は 4096、負数は 0 に clamp される（`engine/src/prefill/prefill.cpp:5363-5369,5371-5385`, `engine/src/kernels/cuda/qsa_select.cu:3911-3917`）。
- key scratch の作成・利用が可能であること。query cap は 1..4096、block 数が上限内、scratch が必要サイズ以上で 16-byte aligned であること、selection shape が対応する値であることが必要。関数が `false` を返す場合は通常 scorer へ fallback する（`engine/src/kernels/cuda/qsa_select.cu:3921-3942`, `engine/src/prefill/prefill.cpp:5380-5392`）。

## 実行時の詳細

CUDA では `qsa_two_pass_on()` 内の function-local `static RequestStatus` が最初の呼び出し時に値を読み、その後は要求値を cache する。Metal / SYCL / HIP もそれぞれ `static RequestStatus` を作るため、その経路での最初の `Prefill::run` 時に読み取る。CUDA layer-major 用の警告にも独立した static status がある。したがって、これらの初期化後にプロセス環境を変更しても、その static に保存された要求値は更新されない（`engine/src/kernels/cuda/qsa_select.cu:3896-3902,4008-4012`, `engine/src/prefill/prefill.cpp:9630-9635,9677-9684`, `engine/sycl/src/prefill/prefill.cpp:5959-5962`）。

chunk-major selection は prompt の QSA indexer が chunk の key data を揃えた後に閾値を判定し、キー用 scratch を作る。各 selection batch で `STRATA_SELECT_OLD` を確認してから二段 scorer を試し、成功しなければ tensor-core scorer、さらにそれが使えなければ一般 scorer を実行する。どの scorer の場合も同じ後続 `qsa_block_topk` に進む。`STRATA_SELECT_TWO_PASS_CHECK=1` が別途有効で二段経路が実行されたときだけ、通常の tensor-core scorer も計算して比較する（`engine/src/prefill/prefill.cpp:5354-5393,5394-5436`）。

GPU が要求された scorer を使えない場合、selection function は `false` を返し、呼び出し側が fallback する。カーネル起動後の CUDA エラーは `qsa two-pass keys: <CUDA error>` または `qsa two-pass scores: <CUDA error>` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:3921-3931,3970-3972`）。

## ログと測定値

要求値が `1` で scorer を使えない path に到達すると、一つの `RequestStatus` につき最初の該当時に次の形式を stderr に出す。サポートされる CUDA prompt path では、この未使用警告は消費されない（`engine/include/strata/kernels/qsa_two_pass_status.hpp:21-39`）。

~~~text
strata: STRATA_SELECT_TWO_PASS=1 is not used on <path>: the two-pass scorer runs only in the CUDA prompt path's tensor-core selection (sm_80+); the selection is unchanged
~~~

CUDA の二段 scorer が実際に最初に呼ばれたときは一度、`qsa select: two-pass scores on ...` を stderr に出し、各 prompt 終了時にはカウンタが 1 call 以上なら `strata prefill: two-pass QSA select: ...` を出す。CHECK が有効で比較 query があった場合には別行 `strata prefill: two-pass check: ...` も出る（`engine/src/kernels/cuda/qsa_select.cu:3950-3956`, `engine/src/prefill/prefill.cpp:7943-7965`）。

`docs/DETAILS.md` は RTX 3090（sm_86、PCIe 3.0、250 W、v0.2.6 release defaults、2 組の各 2 runs）で 256K prompt が 5.2%（1,887 から 1,984 tokens/s）、128K が 2.2%速く、32K は 1%以内で同等、decode と回答は変わらなかったと報告する。この数値は同資料に記載された条件付きの報告であり、今回の調査で再測定・独立検証した値ではない（`docs/DETAILS.md:1310-1316`）。

## 根拠

- parse と未対応 path の警告: `engine/include/strata/kernels/qsa_two_pass_status.hpp:12-39`
- CUDA card / scorer 利用可否、未使用時の扱い: `engine/src/kernels/cuda/qsa_select.cu:3873-3902,4008-4021`
- chunk-major prompt における閾値、fallback、CHECK: `engine/src/prefill/prefill.cpp:5354-5436`
- block 閾値の既定値: `engine/include/strata/kernels/qsa_two_pass.hpp:60-62`
- 閾値 parse、scratch / kernel エラー: `engine/src/kernels/cuda/qsa_select.cu:3911-3931,3950-3972`
- Metal / layer-major / SYCL の扱い: `engine/src/prefill/prefill.cpp:9630-9635,9677-9684`; `engine/sycl/src/prefill/prefill.cpp:5959-5962`
- prompt 終了時の統計ログ: `engine/src/prefill/prefill.cpp:7943-7965`
- 条件付き性能記載: `docs/DETAILS.md:1310-1320`
