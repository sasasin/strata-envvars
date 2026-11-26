# `FNX_PF_PASS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

split engine の prompt prefill で、1 pass にまとめて処理する prompt chunk 数を指定する。値は `Pf::pass` に保存され、prefill の chunk 分割上限と、pass 数分の GPU / pinned-host バッファ確保に使われる。生成 token の選択を直接指定する変数ではない（`engine/src/split/src/prefill.cu:1069-1079,1307-1318,1342-1364`）。

## 値と判定

`env_int("FNX_PF_PASS", fallback)` が `getenv` で設定有無を調べ、設定されていれば `parse_whole` で符号付き base-10 整数として文字列全体を parse する。未設定なら fallback を使う。空文字は設定済みとして parse されるが整数ではないため例外になる。先頭・末尾の空白、小数、接尾辞、16進数、`true` / `false` は受理されず、`strtoll` の範囲外も不正値になる。`+1`、`01` など整数全体として有効な表記は parse される。その後 `1` 以上 `PF_PASS`（定数 `8`）以下でなければ例外になり、clamp や fallback はしない（`engine/src/split/src/env.hpp:15-22,33-40`; `engine/src/split/src/engine.hpp:393-398`; `engine/src/split/src/prefill.cu:1069-1071`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA build、`FNX_PF_ROWS` と `FNX_PF_PASS` の両方が unset で自動選択が走る | 空き VRAM 等から `{4, 2}` の候補を選ぶ。最小候補も収まらない場合は `2` | `1`、`4`、`8` | `0`、`9`、`-1` は範囲外 |
| それ以外（`FNX_PF_ROWS` または `FNX_PF_PASS` が設定済み、または HIP build） | ExpertCache slots がある、または CUDA の 2-card HCSplit を要求できる場合は `4`、それ以外は `2` | `1`〜`8` の整数全体 | `0`、`9`、`-1` は範囲外 |

設定例: `0`、空文字、`0anything`、` 2`、`2 `、`2.0` はいずれも失敗するが、前二者の `0` は整数 parse 後の範囲エラー、空文字や後続文字・空白は整数 parse エラーとなる。整数 parse エラーは `FNX_PF_PASS: '<値>' is not a whole number`、範囲エラーは `FNX_PF_PASS: 1 to 8, got <値>`（`PF_PASS` は 8）となる（`engine/src/split/src/env.hpp:15-21,33-39`; `engine/src/split/src/prefill.cu:1069-1070`）。

CUDA constructor は、`FNX_PF_ROWS` と `FNX_PF_PASS` の両方が未設定の場合にだけ空き VRAM 等から rows/pass を選ぶ。どちらか一方でも設定されていればこの自動選択は行わない。これは `getenv(...) == nullptr` による存在判定なので、`FNX_PF_PASS` を空文字や不正値に設定した場合も自動選択を抑止した後、後段の整数 parse / 範囲検査で失敗する。自動選択を抑止した場合、未設定 `FNX_PF_PASS` の fallback は `pf_pass_pick_` が未選択なら後述の `2` または `4` になる（`engine/src/split/src/engine.cu:81-115`; `engine/src/split/src/prefill.cu:1065-1071`）。

## 有効になる条件

- 対象は `engine/src/split` の CUDA / HIP split engine の prompt path。別 backend の同名設定は見つからなかった（`engine/src/split/src/engine.cu:34-35,84-116`; `engine/src/split/src/prefill.cu:1063-1071`）。
- 未設定時の fallback は、constructor が設定した `pf_pass_pick_` が正ならその値、そうでなければ `(w.ec.n_slots || hcs_wanted) ? 4 : 2`。ExpertCache の slot（`w.ec.n_slots`）があれば `4`。`hcs_wanted` は CUDA のみで、2 カード、`FNX_PF_RING_SM` が未設定または `0`、`FNX_PF_OVERLAP` が整数として非 0、`FNX_PF_HCSPLIT` が整数として非 0 の全条件を満たすと true。後二変数の未設定 fallback は各 `1`。HIP では `hcs_wanted` の設定コードが compile guard で除外される（`engine/src/split/src/prefill.cu:967,1063-1071`）。
- CUDA の自動 VRAM 選択が行われるのは、`FNX_PF_ROWS` も `FNX_PF_PASS` も未設定の場合だけ。空き VRAM・K/V pool・arena の slot をもとに `(8192,4)`, `(8192,2)`, `(4096,4)`, `(4096,2)` の組から選び、選んだ pass 数が未設定値の fallback として使われる（`engine/src/split/src/pf_pick.hpp:21-29`; `engine/src/split/src/engine.cu:81-110`; `engine/src/split/src/prefill.cu:1069-1071`）。
- sfnx server で別 request が decode 中なら、`set_pass_rows(8192)` が指定され、prefill は `K = min(Pf::pass, pass_rows_ / pf_c_)` に制限される。ただし下限は 1 chunk。したがって `FNX_PF_PASS` の値が大きくても、この状態では pass に使う chunk 数が行数上限で小さくなる。decode が無いときは上限を解除する（`engine/src/split/tools/sfnx.cpp:828-829,915-916`; `engine/src/split/src/engine.hpp:72-74`; `engine/src/split/src/prefill.cu:1307-1312`）。
- CLI 引数や他の設定ファイルによる上書き箇所は確認できなかった。`FNX_PF_ROWS` は CUDA の VRAM 自動選択を抑止する相互作用があるが、`FNX_PF_PASS` の明示値を上書きしない（`engine/src/split/src/engine.cu:89-115`; `engine/src/split/src/prefill.cu:1069-1071`）。

## 実行時の詳細

`Engine` constructor が `prefill_alloc()` を呼び、その中でカードごとの `Pf` 構造体を作る際に環境値を読む。`env_int` に static cache はなく、prefill request ごとの読み直しでもない。値は `Pf::pass` に保存され、その pass 数に応じて chunk ごとの作業領域を確保する。`prefill()` は全カードの最小 pass 数を初期上限 `K` とし、必要なら server の `pass_rows_` 制限を適用して chunk 群を作り、各群を `prefill_pass` に渡す。通常はプロセス初期化時に一度設定される値で、実行中の環境変更を次の request で再読込する実装はない（`engine/src/split/src/engine.cu:318`; `engine/src/split/src/prefill.cu:854-857,1069-1079,1300-1318,1342-1364`）。

設定値が増えると pass あたりの chunk 上限とそれに必要なバッファ数が増える。`FNX_PF_TIMING` が有効なら初期化時に `prefill on card %d: passes of %d chunks, stages of %zu MiB` が stderr に出る。これは pass 数の表示で、設定が最終的に使われる実 chunk 数は prompt 長や server の行数上限で小さくなることがある（`engine/src/split/src/prefill.cu:1071-1079,1257-1258,1307-1312,1342-1364`）。

## ログと測定値

設定値の受理・範囲エラーは前節の例外文言になる。`fnx_run` は `fnx_run: <例外>` を stderr に出して終了コード `1` を返す。sfnx の engine 初期化失敗では `ERR <例外>` を stdout、`sfnx: failed: <例外>` を stderr に出して flush 後 `_Exit(1)` する（`engine/src/split/tools/fnx_run.cpp:1365-1373`; `engine/src/split/tools/sfnx.cpp:1094-1103,1123-1136`）。

測定値は記載しない。現行コードから、この設定値による性能差を示す測定条件は確認できない。

## 根拠

- 整数環境値の読取・parse: `engine/src/split/src/env.hpp:15-40`
- CUDA の自動 pass 選択と `FNX_PF_ROWS` との相互作用: `engine/src/split/src/engine.cu:81-115`; 候補: `engine/src/split/src/pf_pick.hpp:21-29`
- fallback、範囲検証、pass 用バッファ確保、timing log: `engine/src/split/src/prefill.cu:1063-1080,1123-1127,1257-1258`
- prefill 内の chunk 数上限と server 同時 decode 時の制限: `engine/src/split/src/prefill.cu:1300-1312,1342-1364`; `engine/src/split/tools/sfnx.cpp:828-829,915-916`
- pass 定数と constructor 選択値: `engine/src/split/src/engine.hpp:393-398`
