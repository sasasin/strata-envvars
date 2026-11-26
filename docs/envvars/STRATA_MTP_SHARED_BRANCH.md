# `STRATA_MTP_SHARED_BRANCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

MTP draft layer の MoE decode で、shared expert を router と routed experts と並行して別 stream/queue で計算するかを切り替える。非 HIP の CUDA と SYCL では未設定時に分岐を使い、`0` 相当の値を設定すると主 stream/queue 上で routed experts の後に shared expert を実行する。HIP はこの分岐をコンパイル時に無効にしており、変数を読み取らない。これは計算スケジュールの切替で、router の選択値や combine の入力形式を直接変更するコードではない。実装は CUDA/HIP 共通の `MtpDrafter::record_rest` / `record_rest_slots` と SYCL 版 `record_rest` にある（`engine/src/core/mtp.cpp:1309-1312,1391-1455,2445-2448,2537-2590`; `engine/sycl/src/core/mtp.cpp:1102-1147`）。

## 値と判定

各 decode 関数内の関数ローカル `static const bool` を初期化するとき `std::getenv` で読み、`std::atoi(v) != 0` で判定する。未設定は `true`。設定値は先頭の整数部分を `atoi` が変換し、変換結果が 0 以外なら有効とする。文字列全体の検証、大文字小文字判定、真偽語の解釈、範囲制限はない。

| 経路 | unset | 分岐を有効にする値の例 | 分岐を無効にする値の例 |
| --- | --- | --- | --- |
| CUDA (`STRATA_USE_HIP` 未定義) / SYCL | 有効 | `1`, `-1`, `2`, `1tail` | `0`, 空文字, `true`, `false`, `0tail`, `nonnumeric` |
| HIP (`STRATA_USE_HIP` 定義) | 無効（変数を読まない） | 該当なし | 常に無効 |

`atoi` は先頭の空白や符号を許容する整数変換で、数値の後ろは判定に使わない（例: `  +1tail` は有効、`  0tail` は無効）。整数に変換できない先頭なら 0 となる。CUDA/SYCL の単発 decode と batch decode にそれぞれ別の `static` があるため、各関数が初めて評価された後に環境を変更しても、その関数の値は変わらない。設定ファイルや CLI 引数との優先順位を決める処理はこれらの実装にはなく、engine はこの環境変数を直接読む（`engine/src/core/mtp.cpp:1392-1398,2537-2544`; `engine/sycl/src/core/mtp.cpp:1104-1111`）。

## 有効になる条件

- MTP drafter の decode が実行され、単発経路の `record_rest` または batch 経路の `record_rest_slots` に到達する必要がある。CUDA/HIP の両経路は `decode_ready` が偽なら先に失敗する（`engine/src/core/mtp.cpp:1309-1312,2445-2448`）。SYCL 版の単発 `record_rest` は `engine/sycl/src/core/mtp.cpp:1013-1022` にある。
- CUDA では `STRATA_USE_HIP` が未定義であること。HIP build では `#if defined(STRATA_USE_HIP)` が `false` を返し、環境変数の読み取り自体を除外する（`engine/src/core/mtp.cpp:1392-1398,2537-2544`）。
- batch 経路では、値が有効でも `side_`, `sh_fork_`, `sh_join_` がすべて非 null の場合に限り `use_branch` が真になる。null なら shared expert は主 queue 上で routed experts の後に実行される（`engine/src/core/mtp.cpp:2545-2545,2584-2590`）。
- SYCL では同ファイルの `record_rest` がこの分岐を使う。SYCL 対応 build と MTP decode が必要（`engine/sycl/src/core/mtp.cpp:1104-1113`）。
- Metal build は対象の CUDA/HIP 共通・SYCL の実装ではない。batch の `draft_slots` は Metal で `mtp batch: unsupported on Metal` を返す（`engine/src/core/mtp.cpp:2735-2744`）。

## 実行時の詳細

単発 decode では有効時に CUDA event を主 stream に記録し、side stream を待たせてから shared expert の計算を side stream に投入する。router と routed experts は主 stream で進み、主 stream は shared expert の join event を待ってから combine に進む。無効時は同じ `shared_rows` 計算を routed experts の後に主 stream で実行する（`engine/src/core/mtp.cpp:1400-1418,1437-1455`）。

Batch decode も同様に fork/join するが、補助 stream/event が揃わない場合は分岐せず直列実行する。単発と batch の各 `static` はそのコード経路で初回評価された時点の値を保持する。プロセス起動後に環境値を変えた場合の再読み込みはない（`engine/src/core/mtp.cpp:2537-2566,2584-2590`）。

SYCL では queue の barrier で fork/join し、`side_` に shared expert を投入する。無効時は主 queue 上で routed experts の後に実行する（`engine/sycl/src/core/mtp.cpp:1112-1147,1165-1173`）。CUDA/SYCL の各実装は MTP drafter の初期化時に補助 stream/queue と event を作り、作成に失敗すると初期化を失敗させる（CUDA: `engine/src/core/mtp.cpp:646-653`; SYCL: `engine/sycl/src/core/mtp.cpp:578-590`）。

## ログと測定値

この変数の値や分岐選択を報告する専用ログは、該当する実装経路にはない。fork/join の CUDA API が失敗すると `record_rest` は `mtp: the shared expert's branch` または `mtp: the shared expert's join` をエラー文字列に設定して `false` を返す（`engine/src/core/mtp.cpp:1402-1405,1416-1419,1452-1454`）。batch は `mtp batch: shared expert fork failed`, `mtp batch: shared expert join record failed`, `mtp batch: shared expert join wait failed` を設定して `false` を返す（`engine/src/core/mtp.cpp:2547-2551,2560-2565,2584-2587`）。SYCL は `mtp: the shared expert's branch` / `mtp: the shared expert's join` を設定して `false` を返す（`engine/sycl/src/core/mtp.cpp:1120-1125,1139-1145,1165-1169`）。この調査では性能測定を行っていない。

## 根拠

- CUDA/HIP 単発 decode の値判定、分岐、合流: `engine/src/core/mtp.cpp:1391-1418,1452-1455`。
- CUDA/HIP batch decode の値判定、補助リソース条件、分岐、合流: `engine/src/core/mtp.cpp:2537-2566,2584-2590`。
- CUDA/HIP 補助 stream/event の生成と HIP の除外: `engine/src/core/mtp.cpp:646-672`。
- SYCL の判定、queue barrier、合流: `engine/sycl/src/core/mtp.cpp:1102-1147,1165-1173`。
- SYCL 補助 queue/event の生成: `engine/sycl/src/core/mtp.cpp:578-590`。
- Metal batch の非対応経路: `engine/src/core/mtp.cpp:2735-2744`。
