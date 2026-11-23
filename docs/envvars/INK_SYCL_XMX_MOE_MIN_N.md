# `INK_SYCL_XMX_MOE_MIN_N`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL backend の MoE で、1 expert に割り当てられた token-expert pair 数 `n` がこの値以上なら、oneMKL XMX MoE kernel を使うための下限を指定する。下限未満の expert は SG16 MoE 経路に回る。値は `ink_sycl::xmx_moe_min_n()` が取得し、通常の MoE 経路と hybrid の大 batch 経路で参照される（`engine/src/inkling2/sycl/ink_sy_xmx.h:35-42`、`engine/src/inkling2/sycl/ink_sy_runner.h:680-721`、`engine/src/inkling2/sycl/ink_sy_hybrid.h:774-798`）。

## 値と判定

`std::getenv` で設定有無を調べ、値が存在し空でなければ `std::atoi` で整数変換し、`std::max(1, ...)` で最低値を 1 にする。未設定または空文字は既定値 12。文字列全体の妥当性検査はなく、`atoi` の数値変換結果を使うため、数値の後ろに文字がある場合も数値部分が使われる。例えば `12tail` は 12、`tail12` や空白だけの値は `atoi` が 0 を返すため 1 になる。先頭空白や符号は `atoi` の変換規則に従い、変換結果が 1 未満なら 1 になる。`atoi` の変換エラーや範囲外を検出する処理はない（`engine/src/inkling2/sycl/ink_sy_xmx.h:35-42`）。

| 条件 | unset | 有効になる値（例） | 変換後の下限 |
|---|---|---|---|
| SYCL source が `xmx_moe_min_n()` を呼ぶ場合 | 12 | `1`, `12`, `24`, `12tail` | `atoi` の結果と 1 の大きい方 |
| 同上 | 空文字 | `0`, `-4`, `tail12`, 空白のみ | 1 |

正の整数はその値が下限になる。大きい値を指定すると、その値に届かない expert は XMX 対象から外れる。負値を含む 1 未満の変換結果は 1 に丸められる。`bool`、大文字小文字、文字列全体の比較は行わない。

## 有効になる条件

- Strata の実験的 SYCL backend が選択されている必要がある。`STRATA_ENABLE_SYCL` は既定で OFF（`engine/CMakeLists.txt:23-32`）。
- XMX dispatch の実体は `INK_SYCL_USE_ONEMKL` が定義された build に限られる。CMake は oneMKL の include が見つかった場合にこの macro を定義する（`engine/src/inkling2/sycl/CMakeLists.txt:28-41`）。macro がない build では `ink_xmx_moe_single` は常に `false` を返す stub で、XMX 実行にはならない（`engine/src/inkling2/sycl/ink_sy_xmx.h:520-525`）。
- `INK_SYCL_NO_XMX` が空でない文字列で、先頭文字が `'1'` の場合は XMX が無効。例えば `1`, `10`, `1false` は無効化し、未設定、空文字、`true`, `0` はこの判定では無効化しない。判定結果も関数内 `static` に cache される（`engine/src/inkling2/sycl/ink_sy_xmx.h:23-33`）。
- 非 hybrid の通常 MoE 分岐では、expert-parallel の分岐に入らず、`M >= 32` であることが必要。各 expert の件数 `cnt` が下限以上なら XMX 対象になり、それ未満は SG16 の gate/up と down kernel にまとめて処理される（`engine/src/inkling2/sycl/ink_sy_runner.h:623-680, 689-721`）。
- hybrid 実行では `run_moe_hybrid` の `M >= 3` 側で VRAM 常駐 expert と cold expert の両方に件数下限が使われる。VRAM 常駐 expert のうち閾値以上で `INK_SYCL_NO_XMX` が無効化していないものは XMX、残りは SG16 へ進む。cold expert は XMX 関数が `false` を返すと SG16 single-expert 経路へ進む。`M <= 2` 側は pinned host doorbell と CPU worker pool を使う別経路で、この XMX 件数判定を通らない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:619-639, 743-744, 774-798, 801-841`）。
- `mod->ep2_active && mod->q_peer` の expert-parallel 分岐は通常 MoE の XMX 分岐より先に処理され、その分岐内ではこの閾値を参照しない（`engine/src/inkling2/sycl/ink_sy_runner.h:623-680`）。
- CLI 引数や設定ファイルによる上書きは、対象名の全参照と読み取り箇所の呼び出し経路では見つからない。別環境変数による下限値の上書きもない。

## 実行時の詳細

`xmx_moe_min_n()` は関数内 `static const int` の初期化ラムダで環境を読み、一度値を確定する。最初にこの関数が呼ばれた後の環境変更は反映されない。通常 MoE 経路では、device 上の top-k expert index を host にコピーして expert ごとの pair 数を数え、件数を閾値と比較して対象を分ける。XMX 対象は `ink_xmx_moe_single` で入力を FP16 に集め、expert 重みを FP16 に展開して gate/up・活性化・down を実行し、top-k weight を適用して pair 出力へ書く。小さい件数の expert は既存の SG16 kernel に回る（`engine/src/inkling2/sycl/ink_sy_xmx.h:35-42, 490-518`、`engine/src/inkling2/sycl/ink_sy_runner.h:682-721`）。

hybrid の大 batch 経路も閾値以上の件数だけ XMX に渡し、件数不足の常駐 expert は SG16 の一括処理へ回す。cold expert については `ink_xmx_moe_single` の失敗時に SG16 single-expert 処理を行う。したがって、この値が変えるのは MoE expert の backend/kernel dispatch 下限であり、router が選ぶ expert や top-k weight を変更する処理ではない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:774-798, 801-841`）。

## ログと測定値

この変数の読み取り、閾値判定、XMX/SG16 の振り分けについて専用のログ出力はない。対象 commit の `docs/DETAILS.md` にこの変数または当該下限の測定値は見つからず、速度や出力同一性はここでは主張しない。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_xmx.h:23-42, 490-525` — XMX 有効判定、環境値の変換と既定値、MoE XMX dispatch と no-oneMKL stub。
- `engine/src/inkling2/sycl/ink_sy_runner.h:623-721` — 通常 MoE での expert-parallel 優先分岐、`M >= 32` 条件、件数による dispatch。
- `engine/src/inkling2/sycl/ink_sy_hybrid.h:619-639, 743-841` — hybrid 小 batch 経路、大 batch 条件、常駐/cold expert の dispatch と fallback。
- `engine/CMakeLists.txt:23-32`、`engine/src/inkling2/sycl/CMakeLists.txt:28-45` — SYCL backend と oneMKL macro の build 条件。
