# `FNX_PF_HCSPLIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA split engine の prompt prefill で、hyper-connection read を 2 枚のカードの担当行に分け、各カードが計算した `mixed` 行をホストメモリ経由の copy-engine swap で交換する機能を制御する。未設定の既定 mode は `2`。mode `1` は条件を満たす 4096 行 chunk だけを分割し、mode `2` とその他の非 0 値は 512 行以上の chunk を分割対象にする。mode `1` はコメント上、unsplit read と同じ結果になる校正済み経路に限定される。mode `2` は最終 bit が異なる可能性のある経路を許す。`0` は無効。処理は `engine/src/split/src/prefill.cu` の prefill buffer 初期化と `Engine::prefill_pass` にある。分割は読み取り・行交換経路を変えるもので、コードから生成 token の同一性は保証できない（mode 2 は最終 bit 差を明記）。`engine/src/split/src/prefill.cu:403-427, 1090-1106, 1434-1444`。

## 値と判定

`fnx::env_int` が `std::getenv` で読み、設定値は符号付き base-10 整数として文字列全体を `strtoll` で解析する。省略可能な符号と数字だけを許し、先頭・末尾空白、空文字、末尾の文字、数字で始まらない値、`long long` 範囲外は無効で、`<名前>: '<値>' is not a whole number` の例外になる。`+1`、`-1`、`01` は数値として受理される。`true`、`false`、`1x`、`0anything`、空文字は受理されない。`env_int` 自体は値域 clamp をしない。読み取り後 `int` にキャストされ、機能上は `0` と `1` を特別扱いし、それ以外の非 0 値は mode 2 相当の条件になる。`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/prefill.cu:1092-1093, 1444`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA split build | mode `2`。pass 数の既定値判定側では同じ変数に fallback `1` を渡すが、これは `hcs_wanted` の真偽だけに使われ、mode 自体は後段で fallback `2` として読む | `0` は機能 off。`1` は 4096 行 chunk 限定。`2` は 512 行以上。`-1` なども非 0 なので mode 2 相当 | 空文字、`true`、`0anything`、空白つき数値、`long long` 範囲外は parse error |
| HIP split build | この名前の実読み取りはない。`#if !FNX_HIP` 内の読み取りがコンパイル対象外 | 該当なし | 該当なし |

CUDA では `hcs_wanted` 用に default `1`、mode 用に default `2` で別々に読み取る。通常は未設定なら前者が pass 既定値選択の補助、後者が mode 2 の選択となる。mode 値そのものの範囲検査はない。`engine/src/split/src/prefill.cu:1063-1070, 1090-1094`; HIP 条件は `engine/src/split/src/prefill.cu:1066-1068, 1090-1093`。

## 有効になる条件

- CUDA split engine であること。HIP では対象変数を読まず、hyper-connection split のこの CUDA 実装を有効化しない。`engine/src/split/CMakeLists.txt:76-91, 120-146`; `engine/src/split/src/prefill.cu:1066-1068, 1090-1093`。
- 2 枚のカードであること、`FNX_PF_OVERLAP` が 0 でないこと、`FNX_PF_RING_SM` が 0 であること。`hcs_wanted` はこれらの条件を使い、実際の `p->hcs` も 2 枚・overlap・非 ring-sm・mode 非 0 を必要とする。`engine/src/split/src/prefill.cu:967-975, 1063-1069, 1080-1094`。
- すべてのカードで `FNX_PF_HCSPLIT_LT` が 0 でなく、起動時の校正で使える cublasLt algorithm が見つかること。校正を無効にした場合やカードのいずれかで見つからない場合、`p->hcs` は全カードで false に戻され分割しない。mode 1/2 のどちらもこの校正成功を要する。`engine/src/split/src/prefill.cu:534-535, 583-610, 1100-1102, 1149-1159`。
- 各 prefill pass に少なくとも `FNX_PF_HCSPLIT_MIN` chunk が必要（既定 3）。mode 1 はさらに各 chunk がちょうど 4096 行であること、mode 2 相当は各 chunk が 512 行以上であることが必要。条件を満たさない pass/chunk ではその pass の split read を使わない。`engine/src/split/src/prefill.cu:1340-1347, 1436-1444`。
- `FNX_PF_HCSPLIT_FULL` は split が選ばれた pass での診断用行範囲（既定 0、値 1/2 に特別な意味）を変える別変数。対象変数の有効化条件そのものではない。`engine/src/split/src/prefill.cu:1436-1447, 1541-1549`。

## 実行時の詳細

環境値は `Engine` の prefill buffer 初期化中に読み取られる。mode は各 card の `Pf` に格納され、後の prefill pass がそれを参照する。関数内 static cache はない。読み取り後にプロセス環境を書き換えても、すでに構築された Engine の `p->hcs` / `hcs_mode` は再評価されない。`FNX_PF_HCSPLIT_MIN` など別設定は prefill 時に個別に読まれる。`engine/src/split/src/prefill.cu:1063-1102, 1340-1347, 1434-1444`。

split pass では各カードが自分の行について hyper-connection read を行い、`mixed` の行を `FNX_PF_HCSPLIT_PIECES` 個（既定 4、1〜8 以外は例外）の piece に分けて peer と交換する。行交換後に heavy part が続く。mode 1 は、`down_lt` が true で chunk が 4096 行のときだけ split 判定を通す。mode 2 相当は 512 行以上を許し、校正アルゴリズムの行数依存差により unsplit と最終 bit が異なる可能性がある。校正は 4096 行出力が cublasGemmEx と bitwise 一致し、2048 行を 2 半分に分けた出力も対応する 4096 行区間と bitwise 一致する候補を探す。`engine/src/split/src/prefill.cu:531-535, 583-610, 666-698, 1442-1449, 1541-1564`。

有効値の parse error は `std::runtime_error`。`sfnx` は初期化中の例外を `ERR <理由>` と stderr の `sfnx: failed: <理由>` に出して終了 status 1 にし、`fnx_run` は stderr に `fnx_run: <理由>` を出して status 1 にする。`engine/src/split/src/env.hpp:33-39`; `engine/src/split/tools/sfnx.cpp:1097-1103, 1123-1135`; `engine/src/split/tools/fnx_run.cpp:1364-1373`。

## ログと測定値

校正を実行するとカードごとに stderr へ `fnx: prompt path card %d: hyper-connection down GEMM ...` を出し、algorithm の有無を示す。分割が有効なら `fnx: prompt path: the hyper-connection read is split between the cards (%s)`、カードのいずれかで校正に失敗して要求が fallback された場合は `fnx: prompt path: the hyper-connection read stays on both cards (no cublasLt algorithm that gives the same rows at 2048 and 4096 rows on this card)` が出る。mode 0 や条件不足ではこの fallback 警告条件 `asked && !all` を満たさない場合があり、split 状態の行も出ない。`engine/src/split/src/prefill.cu:617-620, 1149-1159`。

この commit の関連資料には対象変数について条件付き測定値の記載を確認できなかったため、性能値は記載しない。

## 根拠

- `engine/src/split/src/env.hpp:15-40` — 整数 parse と env helper。
- `engine/src/split/src/prefill.cu:1063-1106, 1149-1159` — 有効化、関連条件、校正、初期化ログ。
- `engine/src/split/src/prefill.cu:1340-1347, 1434-1449, 1541-1564` — pass/chunk 条件と split read/swap。
- `engine/src/split/src/prefill.cu:531-620, 666-698` — 起動時 calibration と行交換。
- `engine/src/split/CMakeLists.txt:76-91, 120-146` — CUDA/HIP の build 分岐。
- `engine/src/split/tools/sfnx.cpp:1097-1103, 1123-1135`; `engine/src/split/tools/fnx_run.cpp:1364-1373` — parse 例外の観測経路。
