# `STRATA_VERIFY_QDEDUP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の MoE 処理で、shared expert の gate/up 投影が読む Q8_1 入力を、通常 expert 用に作る同じ Q8_1 バッファから共有します。これにより、適用条件を満たす経路では shared expert 用の重複した入力量子化を避けます。変数は `src/core/verify.cpp` と `sycl/src/core/verify.cpp` の両方で読み取られます。

## 値と判定

読み取りは `std::getenv()` と `std::atoi()` です。文字列全体との比較ではなく、`atoi` が解釈した先頭の10進整数が 0 かどうかで判定します。

| 設定値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、空白だけ、整数として始まらない文字列 | `atoi` が 0 を返すため無効 |
| `0`、`00`、`0abc`、`+0` | 無効 |
| `1`、`2`、`-1`、` 1tail` | 変換結果が 0 以外なので有効 |

先頭の空白と符号は整数変換で扱われ、整数部分の後ろにある文字列は判定に使われません。環境変数が未設定でないだけでは有効になりません。判定結果は `g_qdedup()` 内の `static const bool` に保存され、最初の呼び出し後にプロセス内で環境値を変更しても再評価されません。

根拠: `src/core/verify.cpp:135`, `sycl/src/core/verify.cpp:74`。

## 有効になる条件

環境変数の判定が有効でも、共有処理側では次の条件をすべて満たす必要があります。

- Verifier の `record_window()` が shared expert を処理すること。対象モデル/層に shared expert の重みが必要で、shared-expert 呼び出しが行われる経路が対象です。
- `sh_fork` が false であること。shared expert が fork された別 stream/queue で実行される場合、別バッファとの同期・所有関係が異なるためこの共有は使われません。
- `strata::kernels::cpu::expert_layout().native` が true であること。native expert layout 以外では Q8_1 ではなく別形式の経路を通るため無効です。

したがって、有効な設定値であっても forked shared-expert 経路や native expert layout 以外では、環境変数による量子化共有は行われません。CUDA/HIP 側と SYCL 側に対応する verifier 実装があります。SYCL の `sh_fork` には `!g_stepped` など backend 固有の追加条件があります。

根拠: `src/core/verify.cpp:1420-1426,1521-1526`, `sycl/src/core/verify.cpp:1289-1297,1380-1385`。

## 実行時の詳細

`record_window()` の各 group で shared expert の重みと native 形式を確認した後、実効値を `g_qdedup() && !sh_fork && expert_layout().native` で決めます。通常 expert の入力 Q8_1 がその時点でまだ作られていない場合（`q8_ffn` が false）、`quantize_q8_1_rows(xm, ...)` を先に実行して `nat_xq_` に保存します。`q8_ffn` が true の場合は、既に `nat_xq_` にある MoE 入力の Q8_1 を利用します。

その後 `shared_expert_multi()` に `nat_xq_` の該当 group のアドレスを `x_q8_1_ready` として渡します。同関数はこのポインターが非 null ならそれを shared expert の gate/up `native_mmvq` に渡し、自身で入力を再量子化しません。環境変数による共有が有効でない場合、呼び出し元は null を渡し、shared-expert 関数は `nw.x_q8_1` がなければ `native_quantize_q8_1()` で専用 scratch に量子化します。

後続の通常 expert 用量子化では `qdedup` が true の場合に再度の `quantize_q8_1_rows()` を省略します。native expert layout でない場合は従来の `quantize_q8_0_scaled()` 経路です。`q8_ffn` が true のときは既存の Q8_1 を前提に通常 expert 用の量子化も省かれます。

この変数自体によるログ出力は確認できません。`shared_expert_multi()` の失敗時には verifier が `verify shared expert: ` に例外内容を付けたエラーを返します。性能向上量や結果の同一性について、この変数を対象にした測定値は参照した `docs/DETAILS.md` と文書群では確認できません。

根拠: `src/core/verify.cpp:1416,1521-1547`, `src/kernels/cuda/shared_expert.cu:214-225`; SYCL 対応箇所 `sycl/src/core/verify.cpp:1286,1380-1406`, `sycl/src/kernels/cuda/shared_expert.dp.cpp:313-324`。

## 根拠

- 環境変数の読み取りと値判定: `src/core/verify.cpp:135`, `sycl/src/core/verify.cpp:74`。
- CUDA/HIP verifier での条件判定、事前量子化、共有ポインターの受け渡し、後段量子化の省略: `src/core/verify.cpp:1521-1547`。
- CUDA shared-expert 関数での優先順位（呼び出し元の ready pointer、descriptor の Q8_1、関数内量子化）と gate/up 投影: `src/kernels/cuda/shared_expert.cu:214-231`。
- SYCL verifier と shared-expert 実装: `sycl/src/core/verify.cpp:1380-1406`, `sycl/src/kernels/cuda/shared_expert.dp.cpp:313-330`。
- `docs/DETAILS.md` および `docs/` 内に `STRATA_VERIFY_QDEDUP` の個別説明・測定記録は見つかりませんでした。
