# `STRATA_PF_DQ_FUSED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の prompt prefill において、native expert weight の gate/up と down の FP16 dequantize を `iq_dequant_expert_f16` の一呼び出しで行うか、gate/up と down を別々の呼び出しで行うかを切り替える。既定は一呼び出しで、環境変数の先頭文字が `0` のときは分割する。分岐は expert の dequantize 方法を選び、その後の gate/up・SwiGLU・down の計算自体は同じ `compute` 経路で続く（`engine/sycl/src/prefill/prefill.cpp:5076-5083`, `5163-5180`, `5225-5229`）。

この名前を環境から読む実装は SYCL の `engine/sycl/src/prefill/prefill.cpp` だけにある。同じ名前のコメントと terminal の設定レジストリ項目はあるが、それらは追加の読み取り箇所ではない。

## 値と判定

`std::getenv` の戻り値を文字列として parse せず、先頭文字だけを調べる。値が未設定なら `dq_one` は `true`。設定されていて先頭文字が `0` なら `false`、それ以外なら `true` となる。従って空文字も `true` であり、数字・真偽値としての妥当性、大文字小文字、後続文字、空白は検査されない（`engine/sycl/src/prefill/prefill.cpp:5167-5169`）。

| 条件 | unset | fused 側 (`dq_one=true`) | 分割側 (`dq_one=false`) |
|---|---|---|---|
| SYCL の対象 dequantize 分岐 | fused 側 | `1`, `true`, `false`, 空文字, ` 0`, `-0`, `00x` など、先頭文字が `0` 以外 | `0`, `0anything`, `00` など、先頭文字が `0` |

ここでの「有効」は fused 側を選ぶ値という意味であり、対象分岐に入るための実行条件は次節のとおり。

## 有効になる条件

- SYCL backend のビルドであること。このファイルは `engine/sycl/CMakeLists.txt:303-308` で `strata_prefill` に含まれる。
- prompt の routed expert を処理する `Prefill::run_impl` の expert `compute` 経路に入り、`use_mmq` と `xmx2 || fp16_group` の早期分岐を通らないこと（`engine/sycl/src/prefill/prefill.cpp:2693`, `5076-5083`, `5083-5136`）。
- 上記の後、layer が native layout (`lay.native`) であること。非-native layout は `blob_dequant_f16` に進むため、この環境変数を読まない（`engine/sycl/src/prefill/prefill.cpp:5163-5180`）。
- `f16_pairs` が偽であること。これは `STRATA_SYCL_F16_EXPERT_PAIR` の先頭文字が `1` で、かつ native layout、`!use_mmq`、XMX mode が `0` のとき真となり、その場合は `dq_one` の値にかかわらず分割 dequantize 側を選ぶ（`engine/sycl/src/prefill/prefill.cpp:4627-4629`, `5168-5177`）。
- CLI 引数、別設定ファイル、別環境変数による `dq_one` の上書きは、この読み取り箇所にはない。上記の `STRATA_SYCL_F16_EXPERT_PAIR` は別の経路条件として作用する。

## 実行時の詳細

判定は expert `compute` lambda 内の関数ローカル `static const bool` で、当該分岐に初めて到達した時に一度だけ評価される。最初の評価後に環境値を変更しても、このプロセス内の `dq_one` には反映されない。対象分岐では native layer の format と blob の offset、tail scale を使って、真なら `iq_dequant_expert_f16` に gate/up と down の両データを渡す。偽、または `f16_pairs` が真なら `iq_dequant_gu_f16` の後に down 用 `iq_dequant_f16` を呼ぶ（`f16_pairs && d_type == 42 && tail == nullptr` のときだけ `iq_dequant_f16_plain_launch`）。その後に gate/up projection、SwiGLU、down projection を行う（`engine/sycl/src/prefill/prefill.cpp:5163-5180`, `5225-5229`）。

この変数専用のログや無効値エラーはない。`compute` 中に捕捉される SYCL exception は `exc.what()` と `Exception caught at file:...`、`, line:...` を標準エラーへ出して `exit(1)` する一般処理があるが、当該例外をこの変数に固有の失敗として示す分岐はない（`engine/sycl/src/prefill/prefill.cpp:5232-5237`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:5167-5178` — 環境値の読み取り、先頭文字判定、native と非-native の dequantize 呼び分け。
- `engine/sycl/src/prefill/prefill.cpp:4627-4629` — `STRATA_SYCL_F16_EXPERT_PAIR` と native/MMQ/XMX mode による別経路条件。
- `engine/sycl/src/prefill/prefill.cpp:5076-5136`, `5225-5237` — expert `compute` の呼び出し位置、分岐、後続計算と例外処理。
- `engine/sycl/CMakeLists.txt:303-308` — SYCL prefill ソースのビルド対象。
