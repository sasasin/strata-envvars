# `STRATA_CPU_IQ_ALL_EXACT1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 経路で、対象 i-quant の gate/up 行が一つの token を処理するとき、ggml-cpu の AVX2 単一 token dot と同じ float 演算順になる Strata の AVX2 カーネルを選ぶスイッチです。出力値を変える近似スイッチではなく、条件を満たす場合に `iq256_gu_rows_exact_one` へ分岐します。対象型は `NativeFmt::gu_type` が `16, 17, 18, 21, 22` の場合です。ソースは型 ID と同じ結果になることを示していますが、この文書では型名の対応や他の経路での出力同一性までは断定しません。`engine/src/kernels/cpu/native_expert.cpp:585-599`。

これは GPU backend のカーネル切替ではありません。GPU backend の CUDA 初期化が条件を満たすと、この環境変数を Strata プロセス内に既定設定することはありますが、実際の分岐は CPU の native gate/up 行計算で評価されます。通常の GPU 利用時でも CPU が native expert を処理する場面がなければ、この分岐は実行されません。`engine/src/program/generate.cpp:4421-4449`、`engine/src/kernels/cpu/pool.cpp:1288-1296,1421-1429`。

## 値と判定

直接読み取りは `std::getenv` と文字列の完全一致相当の判定です。`atoi` などの変換はありません。関数テンプレート内の `static const bool` として各特殊化で初回評価時に保存します。`engine/src/kernels/cpu/native_expert.cpp:588-591`。

| 条件 | unset | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| native CPU gate/up 行の直接判定 | `exact_one=false` | 文字列が厳密に `1` のみ | 空文字、`0`、`10`、`1anything`、`true`、` 1`、`1 `、その他すべて |
| CUDA sm_86 の既定設定対象 | `STRATA_SM86_PERF` が先頭文字 `0` でなく、全可視 CUDA GPU が sm_86 なら、未設定時に Strata が `1` を設定 | 既定設定の結果は直接判定でも有効 | 変数があらかじめ存在すれば、その値を問わず保持。空文字や `0` も既定値を抑止し、直接判定では無効 |
| CUDA sm_70 の既定設定対象 | `STRATA_SM70_PERF` が先頭文字 `0` でなく、`STRATA_DEFAULTS=026` が無効で、全可視 CUDA GPU が sm_70 なら、未設定時に Strata が `1` を設定 | 既定設定の結果は直接判定でも有効 | 変数があらかじめ存在すれば保持。`STRATA_SM70_PERF` の先頭文字が `0`、または `STRATA_DEFAULTS=026` なら既定表を適用しない |

GPU 既定値の「変数が存在するか」は `getenv(...) != nullptr` で調べられ、空文字もユーザー設定として優先されます。表を無効化する `off()` は値の先頭文字が `0` かだけを見るため、たとえば `STRATA_SM86_PERF=0anything` も sm_86 表を無効化します。`engine/src/core/nv_defaults.cpp:15-18,41-43,136-140,222-233`。

`STRATA_DEFAULTS` は `026`、`0.2.6`、`v0.2.6` のいずれかに完全一致した場合だけ有効で、`qwen_defaults_026()` が初回に読み取って cache します。これは sm_70 の表を止めますが、現在の sm_86 の表は止めません。`engine/include/strata/core/defaults_026.hpp:21-30`、`engine/src/core/nv_defaults.cpp:41-43,136-140`。

## 有効になる条件

- `exact_one` が真で、処理 token 数が `nt == 1` であること。
- `nt < native_gu_mt_min(f.gu_type)` であること。通常の閾値は `STRATA_IQ_MT_MIN` 未設定時の `2` です。同変数が設定されていれば `atoi` の結果が閾値です。文字列全体の検証はなく、先頭に数値がない文字列は `0`、`2tail` は `2`、`-1` は `-1` になります。したがって一 token は閾値が `2` ならこの条件を満たし、`1` 以下なら満たしません。`STRATA_IQ_MT_MIN` 未設定時に限り、IQ3_S 型 (`gu_type == 21`) では、`STRATA_IQ3S_MT1` が値を問わず設定済み、AVX2 対応かつ `STRATA_NO_IQ256` 未設定、AVX-512 非対応、`iq256_gather_setting() != 0`、`cpu_gather_fast()` のすべてを満たすと閾値が `1` になり、この分岐を通りません。`engine/src/kernels/cpu/native_expert.cpp:540-556,592-595`。
- CPU が AVX2 対応で、`STRATA_NO_IQ256` が未設定であること。CPU 機能チェックに失敗する場合や `STRATA_NO_IQ256` が空文字を含め設定済みの場合は無効です。`engine/src/kernels/cpu/native_expert.cpp:569-576,594-595`。
- 実行時 CPU が AVX-512 ではないこと。ビルドされた ggml-cpu の演算 flavour が AVX2 で、AVX-512 flavour ではないこと。`STRATA_ISA_FLOOR` 相当の AVX1/SSE flavour や AVX-512 flavour では `exact_one` が成立しません。`engine/src/kernels/cpu/native_expert.cpp:585-590,594-595`、`engine/include/strata/kernels/cpu/pool_quant.hpp:69-73,96-98`。
- `f.gu_type` が `16, 17, 18, 21, 22` のいずれかであること。それ以外の型は通常の後続 dispatch に進みます。`engine/src/kernels/cpu/native_expert.cpp:594-599`。
- 適用先が CUDA の自動既定値である場合、CUDA 初期化でデバイスが 1 台以上見つかり、全可視デバイスの compute capability が同じ必要があります。混在世代なら `apply_nv_defaults` は呼ばれず、自動設定されません。sm_86 では `STRATA_SM86_PERF` の先頭文字 `0`、sm_70 では `STRATA_SM70_PERF` の先頭文字 `0` または `STRATA_DEFAULTS=026` が既定表を抑止します。明示的に環境変数を設定する CPU native 経路には、この CUDA 既定値条件は不要です。`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:41-43,136-140,222-233`。

## 実行時の詳細

CUDA engine の初期化は、CUDA の可視デバイスを調べたあと同一 compute capability の場合に `apply_nv_defaults` を呼びます。sm_86 表は `STRATA_CPU_IQ_ALL_EXACT1=1` を含みます。sm_70 表も同じ値を含み、さらに `STRATA_DEFAULTS=026` で表全体を止めます。`apply_nv_defaults` は候補変数が未設定の場合だけ `_putenv_s` または `setenv(..., 0)` でプロセス環境に追加します。したがって、環境変数の明示値は空文字も含め常に自動設定より優先されます。ここに CLI 引数による上書きはありません。`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:37-55,136-163,222-233`。

CPU native 経路では `native_gu_rows` または `native_gu_rows_invariant` が `native_gu_rows_impl` を呼び、該当 specialization の初回実行時に環境値を cache します。そこから後に環境を変更しても、その specialization の判定は変わりません。分岐に入ると `iq256_gu_rows_exact_one` を実行して戻り、通常の後続 kernel 選択へ進みません。`engine/src/kernels/cpu/native_expert.cpp:588-599,898-910`、`engine/src/kernels/cpu/iq_avx2.cpp:457-489`。

## ログと測定値

CUDA の既定表から何か一つ以上の値を新規設定した場合、stderr に `strata: sm_86 (Ampere): ...` または `strata: sm_70 (Volta): ...` で始まる既定値一覧が出ます。その行の値リストには `CPU_IQ_ALL_EXACT1` のように `STRATA_` を除いた名前が含まれます。対象変数をユーザーが既に設定していた場合、その変数は新規設定一覧には含まれません。`engine/src/core/nv_defaults.cpp:222-255`。

実際に対象 kernel 分岐へ入ると stderr に `strata ab: GATE=STRATA_CPU_IQ_ALL_EXACT1 active=1` が出ます。`std::call_once` により同じ関数テンプレート特殊化では一度だけですが、通常経路以外を含め特殊化ごとに別の `once_flag` です。値が有効でも追加の CPU・token・型条件を満たさなければこのログは出ません。分岐自体にこの変数由来の終了・エラー経路はありません。`engine/src/kernels/cpu/native_expert.cpp:594-599`。

`docs/DETAILS.md:1271` は「sm_86 で既定、他では既定オフ」と読める記載ですが、現行 `engine/src/core/nv_defaults.cpp:136-155` は sm_70 表にもこの変数を追加します。同資料の既定値表 `docs/DETAILS.md:1486-1487` は sm_70 も列挙しており、1271 行の説明と不一致です。同資料 `docs/DETAILS.md:1271,1629` には end-to-end `+0.4〜+2.5%` 等の測定記録がありますが、この調査では測定を再実施していません。コード上の計算結果の説明と資料上の速度値は区別してください。

## 根拠

- 直接判定、条件、ログ、kernel 呼び出し: `engine/src/kernels/cpu/native_expert.cpp:585-599`。
- 1 token 閾値と他環境変数の相互作用: `engine/src/kernels/cpu/native_expert.cpp:540-556,592-595`。
- exact kernel の型別 dispatch: `engine/src/kernels/cpu/iq_avx2.cpp:457-489`。
- CUDA の既定値表とユーザー設定優先、stderr 出力: `engine/src/core/nv_defaults.cpp:15-18,37-55,136-163,222-255`。
- CUDA 初期化時の適用と同一世代条件: `engine/src/program/generate.cpp:4421-4449`。
- `STRATA_DEFAULTS=026` の値判定と cache: `engine/include/strata/core/defaults_026.hpp:21-30`。
- ggml-cpu flavour の判定: `engine/include/strata/kernels/cpu/pool_quant.hpp:69-73,96-98`。
- Strata 資料との照合: `docs/DETAILS.md:1271,1486-1487,1629`。
