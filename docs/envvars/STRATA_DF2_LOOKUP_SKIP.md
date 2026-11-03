# `STRATA_DF2_LOOKUP_SKIP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 が次の draft を作る直前に、suffix lookup の一致が十分長い場合、その draft 計算をその場では行わず次の decode round まで遅らせます。次の round では既存の `DraftPolicy` が lookup window を選べば lookup の context を処理し、選ばなければ遅らせていた DFlash2 draft を計算します。したがって、この変数は lookup を強制したり、lookup の採否ポリシーを変更したりする設定ではなく、長い一致時に DFlash2 draft の時点をずらすための最小一致長です（`include/strata/spec/window_rule.hpp:39-53`, `src/program/generate.cpp:18139-18144,20132-20145`）。

## 値と判定

| ビルド／呼び出し経路 | 未設定または空文字 | 設定値の読み方 | 遅延が可能になる値 |
|---|---|---|---|
| CUDA / HIP（通常の `src/program/generate.cpp` 経路） | 既定値 `0` | `std::atoi` | 正の整数。suffix の一致長がその値以上のとき |
| Metal（通常の `src/program/generate.cpp` 経路） | 既定値 `8` | `std::atoi` | 正の整数。一致長がその値以上のとき |
| SYCL (`sycl/src/program/generate.cpp`) | 既定値 `0` | `std::atoi` | 正の整数。一致長がその値以上のとき。ただしこの経路の `defer_df2` は `use_df2` が true の場合に限る |

実装は未設定と空文字を同じく呼び出し側の既定値にします。空でない値は文字列全体の検証なしに `std::atoi` へ渡されます。そのため、先頭の空白と符号を伴う十進数は変換対象になり、数字の後ろに文字があっても数字部分が変換されます。数値に変換できない文字列は `atoi` の結果が 0 になり、遅延しきい値としては無効です。負数も値自体は保持されますが、実行側が `df2_skip_min <= 0` を除外するため遅延を無効にします。正数にコード上の上限・clamp はありません（`include/strata/spec/window_rule.hpp:47-53`, `src/program/generate.cpp:18139-18144,20072-20088`, `sycl/src/program/generate.cpp:12005-12013`）。

## 有効になる条件

- DFlash2 がビルドに含まれ、現在の CLI 実行または serve request で実際に選択されている必要があります。通常の CUDA/HIP GPU runtime は `STRATA_HAVE_DFLASH2` を定義し、Metal host も定義します。一方、macro がないビルドでは `use_df2` は常に false です（`CMakeLists.txt:431-436`, `metal/CMakeLists.txt:117`, `src/program/generate.cpp:6684-6692`）。
- `--suffix-draft` が正で suffix lookup が有効である必要があります。CLI 引数は `std::atoi` 後に 0 未満を 0 にします（`src/program/generate.cpp:3549`）。serve 経路では同じ `o.suffix_draft > 0` が条件です（`src/program/generate.cpp:20083-20091`）。
- 呼び出し時に lookup 候補 `lookup_k` が正で、suffix matcher の `match` がこのしきい値以上である必要があります（`include/strata/spec/window_rule.hpp:43-45`）。serve loop は初回 window では遅延判定をしません（`src/program/generate.cpp:20083-20091`）。
- serve では request ごとの drafter 選択が DFlash2 のときだけ遅延します。`--draft auto` 等で request が MTP を選ぶ場合は `req_df2` が false となり、遅延しません（`src/program/generate.cpp:15190-15232,18139-18144`）。
- しきい値が満たされても、次 round の `DraftPolicy::choose` が lookup を選ばない場合は DFlash2 draft をその round で計算します。選ばれた場合だけ `df2.context(...)` を呼びます（`src/program/generate.cpp:20132-20145`）。CLI 経路でも、遅延後の候補について同じ方針で lookup または DFlash2 draft に進みます（`src/program/generate.cpp:18182-18196`）。

## 実行時の詳細

環境値は `df2_lookup_skip_min()` 内の関数ローカル `static const int` に初回呼び出し時に保存されます。以後、同じプロセス内で環境を書き換えても再読込されません。呼び出し側は各生成ループの開始時にこの値をローカル変数へ受け取ります。CUDA/HIP の既定は 0、Metal の既定は 8、SYCL の呼び出し側既定は 0 です（`include/strata/spec/window_rule.hpp:47-53`, `src/program/generate.cpp:18128-18133,20072-20077`, `sycl/src/program/generate.cpp:12003-12006`）。

遅延条件成立時は、次回 draft に必要な行数・位置・anchor token を保存し、現在の DFlash2 draft を省略します（`src/program/generate.cpp:18139-18144,20083-20091`; SYCL: `sycl/src/program/generate.cpp:12010-12015`）。次 round で suffix 候補を取り直し、policy が lookup を選ぶ場合は DFlash2 の context を更新して lookup window にし、そうでなければ保存した位置から draft を実行します（`src/program/generate.cpp:20132-20145`; CLI: `src/program/generate.cpp:18182-18196`; SYCL: `sycl/src/program/generate.cpp:12028-12040`）。

この変数専用の有効・無効ログや警告はありません。遅延後の context 更新または draft が失敗した場合、通常の生成エラー経路へ進み、CLI は `ERR ...` を stdout に出して終了コード 1 を返し（`src/program/generate.cpp:18190-18195`）、serve loop は `strata generate: ...` を stderr に出してエラー終了します（`src/program/generate.cpp:20140-20145`）。

## 根拠

- 値の読込、空文字の扱い、キャッシュ、呼び出し側既定値: `include/strata/spec/window_rule.hpp:47-53`, `src/program/generate.cpp:18128-18133,20072-20077`, `sycl/src/program/generate.cpp:12003-12006`。
- lookup 一致長による条件: `include/strata/spec/window_rule.hpp:39-45`。
- CLI の判定・遅延と次 round の処理: `src/program/generate.cpp:18139-18144,18182-18196,18585-18588`。
- serve の遅延、request の DFlash2 選択、次 round の policy 判断: `src/program/generate.cpp:15190-15232,20083-20091,20132-20145`。
- SYCL の遅延経路: `sycl/src/program/generate.cpp:12010-12015,12028-12040`。
- DFlash2 を含む build 条件: `CMakeLists.txt:431-436`, `metal/CMakeLists.txt:117`, `src/program/generate.cpp:6684-6692`。
