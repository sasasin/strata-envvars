# `STRATA_PREFILL_STREAM_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill の各 chunk について、GPU が保持しない expert を全 layer 分ストリームする long-prompt 経路へ切り替える token 数の下限を指定する。閾値以上では ring に expert を読み込み、閾値未満では router が選んだ expert だけを staged walk で読む。CUDA/HIP 実装では値が 0 以上なら既定の閾値や CPU share の閾値を置き換える。SYCL 実装でも閾値を置き換えるが、負値の扱いが CUDA/HIP と異なる。いずれも変数単独で経路を強制するものではなく、ring と `ExpertSource` など別の条件も必要である（`engine/src/prefill/prefill.cpp:648-658,4625-4629`; `engine/sycl/src/prefill/prefill.cpp:215-218,3086-3091`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoll` に渡し、文字列全体の妥当性検査や警告はしない。`atoll` は先頭の空白と符号を許し、数字列を変換する。数字の後ろに続く文字は値として使われず、数字を変換できない文字列と空文字列は 0 になる。したがって `128xyz` は 128、`true` は 0 と判定される。大文字小文字は関係しない。境界値・負値の扱いは実装ごとに異なる。

| 実装 | unset | 設定値の扱い | 例 |
|---|---|---|---|
| CUDA/HIP (`engine/src/prefill/prefill.cpp`) | `-1` の番兵値となり、自動 floor に進む。通常は 1,024。条件により CPU share、Windows gfx1151 の fused-only、plain pack、trellis、CUDA switch-point の floor が選ばれる | 変換結果が 0 以上ならその数値を採用し、既定 floor と CPU share の floor より優先。負値なら自動 floor に進む | `1024` は 1,024、`0`・空文字・`true`・`0abc` は 0、`128xyz` は 128。`-1` や `-20` は自動 floor |
| SYCL (`engine/sycl/src/prefill/prefill.cpp`) | 1,024 | 変換結果をそのまま採用。負値も拒否・fallback されない | 未設定は 1,024、`128xyz` は 128、空文字・`true` は 0、`-1` は -1 |

CUDA/HIP の未設定時は、CPU share が有効なら通常その share limit が floor になる。build やモデル状態によって default floor も変わる。例として Windows gfx1151 の測定対象クラスで全 layer が fused-only かつ staged fused entry が無効なら 64、CUDA build without MMQ の trellis 条件では 64、plain pack 条件では default 64 に discrete CUDA floor 1,536 が適用される。CUDA switch-point が有効でカード情報が揃えば計算 floor になる。これらの自動規則の判定と適用は `engine/src/prefill/prefill.cpp:392-405,407-425,592-617`; 64/1,024 の規則は `engine/include/strata/prefill/stream_floor_rule.hpp:20-49`; plain pack と share の組み合わせは `engine/include/strata/prefill/plain_floor_rule.hpp:26-43` にある。設定値が非負ならこの自動判定結果を使わない（`engine/src/prefill/prefill.cpp:648-658`）。

無効値の専用処理はなく、変換結果がそのまま使われるか、CUDA/HIP では負値だけが unset 相当として扱われる。数値の桁あふれについて Strata 独自の検査や扱いはない。

## 有効になる条件

- CUDA/HIP の `engine/src/prefill/prefill.cpp` または SYCL の `engine/sycl/src/prefill/prefill.cpp` が組み込まれた engine 経路で有効。これら二つの本番読み取り箇所を確認した。CUDA/HIP と SYCL では unset と負値の挙動が異なる（上表）。
- 実際に全 expert の streamed walk を行うには chunk が floor 以上で、`m.ring > STAGE` かつ `m.src != nullptr` である必要がある（CUDA/HIP: `engine/src/prefill/prefill.cpp:4625-4629`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3086-3091`）。短い chunk は routed-only staging のまま。
- CUDA/HIP では `STRATA_PREFILL_CPU_SHARE` などが自動 share floor を決めるが、対象変数を 0 以上で指定した場合は share limit よりも対象変数が優先する。未設定または負値のときは share floor が適用され得る（`engine/src/prefill/prefill.cpp:648-658,672-678`）。
- `STRATA_PREFILL_RING`、内部 ring override、ring budget の結果が `STAGE` 以下なら閾値を超えても full streamed walk は使われない。HIP の WMMA ring 分岐も chunk とこの floor を使う（`engine/src/prefill/prefill.cpp:843-879`）。
- SYCL では `STRATA_PREFILL_STREAM_ALL=0` により full streamed walk が禁止される。未設定時は非 resident expert の割合が 10% 未満の場合に許可され、`STRATA_PREFILL_STREAM_ALL=1` は許可側にする（`engine/sycl/src/prefill/prefill.cpp:311-323`）。
- CLI の prefill chunk や serve の短い読み取りは各 chunk の長さを決め、この floor と比較される。調査したコードにこの閾値を CLI 引数で直接上書きする処理はない（`engine/include/strata/prefill/prefill.hpp:103-110`; `engine/src/program/generate.cpp:6821-6829,11167-11194`）。

## 実行時の詳細

`stream_all_min()` 内の関数ローカル `static` が初回呼び出し時に環境を読み、プロセス内で値を保持する。起動後に環境を変更しても再読込されない（CUDA/HIP: `engine/src/prefill/prefill.cpp:648-658`; SYCL: `engine/sycl/src/prefill/prefill.cpp:215-218`）。CUDA/HIP で対象変数が未設定相当の場合、default floor は expert layout や CPU share、カード情報を待って後から決めるキャッシュを持つ。layout 未確定などで早く呼ばれた場合は default を返し、その default floor 自体は cache しない経路がある（`engine/src/prefill/prefill.cpp:592-617`）。

比較は `T >= floor` であり、ちょうど閾値の chunk から対象になる。実際の streamed walk は GPU 非常駐 expert を layer 順に ring 経由で読み込む。下回る chunk は router が使う expert のみ staged walk で処理する（`engine/src/prefill/prefill.cpp:4625-4629`; `engine/sycl/src/prefill/prefill.cpp:3086-3091`）。SYCL で負の floor を指定するとすべての非負 token chunk が比較を通る一方、値を修正する処理はこの読み取り関数にはない。

## ログと測定値

この変数の明示値を読み取ったことを示す専用ログはない。CUDA/HIP で対象変数が未設定相当の場合に自動 default floor が 1,024 以外なら、通常の MMQ build は stderr に `prefill: prompt pieces of N tokens or more read on the fused kernels, as long prompts do. STRATA_PREFILL_STREAM_MIN=1024 keeps the old rule.` を出す（`engine/src/prefill/prefill.cpp:617-629`）。MMQ なしの build では floor を含む prompt-kernel の起動行が出る場合があり、その文言は `engine/include/strata/prefill/own_only_line.hpp:56-68,71-82` に定義される。明示値のときは `stream_all_min()` が自動 floor 分岐より先に返るため、これらの default-floor ログはこの変数の指定を表示しない。

測定値は記載しない。ソースコメント中の測定結果は、この環境変数の一般的な性能効果を示す根拠として扱わない。

## 根拠

- 全読み取り箇所と値の処理: `engine/src/prefill/prefill.cpp:648-658`; `engine/sycl/src/prefill/prefill.cpp:215-218`。
- CUDA/HIP の自動 floor と cache: `engine/src/prefill/prefill.cpp:592-617`; `engine/include/strata/prefill/stream_floor_rule.hpp:20-49`; `engine/include/strata/prefill/plain_floor_rule.hpp:26-43`。
- full streamed walk の条件と効果: `engine/src/prefill/prefill.cpp:4625-4629`; `engine/sycl/src/prefill/prefill.cpp:3086-3091`。
- ring・SYCL の追加条件: `engine/src/prefill/prefill.cpp:843-879`; `engine/sycl/src/prefill/prefill.cpp:311-323`。
- API と CLI の利用関係: `engine/include/strata/prefill/prefill.hpp:103-110`; `engine/src/program/generate.cpp:6821-6829,11167-11194`。
- 観測ログ: `engine/src/prefill/prefill.cpp:617-629`; `engine/include/strata/prefill/own_only_line.hpp:56-82`。
