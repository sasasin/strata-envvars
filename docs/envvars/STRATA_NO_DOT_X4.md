# `STRATA_NO_DOT_X4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native-expert 行計算で使う 4 行共有活性 dot カーネルを無効にする上書きスイッチ。設定されていなければ、この変数自体は有効化せず、`STRATA_DOT_X4=1` が有効化した経路も止めない。設定されていれば値の内容にかかわらず 4 行カーネルを選ばず、通常の 1 行 dot ループに進む。対象の gate/up と down の両方で判定する（`engine/src/kernels/cpu/native_expert.cpp:734-740,751-768,859-865,873-894`）。

## 値と判定

`std::getenv("STRATA_NO_DOT_X4")` の null 判定だけを使い、返った文字列は読まない。未設定 (`nullptr`) の場合だけ無効化指定なしとなる。空文字を含む、設定済みのすべての値は無効化指定として扱われる。数値変換、空白除去、大文字小文字の比較、値の妥当性検査はない（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`）。

実際に 4 行カーネルを選ぶには、別変数 `STRATA_DOT_X4` が文字列全体でちょうど `"1"` であり、かつ本変数が未設定である必要がある。したがって本変数が設定されていれば、`STRATA_DOT_X4=1` でも無効化が優先される。`STRATA_DOT_X4` が未設定、空文字、`0`、`11` などの場合も 4 行経路は有効にならない（同:14-17）。

| ビルド・実行条件 | `STRATA_NO_DOT_X4` 未設定 | 本変数が設定済み（例） |
|---|---|---|
| `STRATA_OWN_CPU_QUANT=ON` で CPU native-expert 行処理がこの判定に到達 | `STRATA_DOT_X4` が厳密に `1` の場合に限り、利用可能な 4 行カーネルを選択 | 値が空、`0`、`1`、その他の文字列のいずれでも 4 行カーネルを選択しない |
| `STRATA_OWN_CPU_QUANT=OFF` | この環境変数を読むコードがコンパイルされず、この判定による選択変更はない | 同左 |

`STRATA_OWN_CPU_QUANT` と `STRATA_NATIVE_EXPERTS` の CMake 既定値は `ON`。前者を `OFF` にすると x4 判定を含む own-quant 実装が除かれ、後者を `OFF` にすると native-expert 実装自体が組み込まれない（`engine/CMakeLists.txt:178-184,725-735`; `engine/cmake/backends/cpu.cmake:370-374`）。

## 有効になる条件

- Strata の CPU native-expert 経路で gate/up または down の行計算が実行されること。`ExpertPool::native_rows` は通常の native 行経路から `native_gu_rows` / `native_down_rows` を呼び、`WindowInvariant` モードでは対応する invariant 関数を呼ぶ。どちらも同じ row 実装テンプレートを使う（`engine/src/kernels/cpu/pool.cpp:1274-1310`; `engine/src/kernels/cpu/native_expert.cpp:898-915`）。
- `STRATA_OWN_CPU_QUANT` が有効であること。この macro がないビルドでは `x4_on` の判定および 4 行ループ自体が `#if defined(STRATA_OWN_CPU_QUANT)` で除かれる（`engine/src/kernels/cpu/native_expert.cpp:735-768,860-894`; `engine/cmake/backends/cpu.cmake:370-374`）。
- `STRATA_NATIVE_EXPERTS` が有効で、native-expert 実装がビルドに含まれること（CMake 既定は `ON`）。無効なら対象実装は登録されない（`engine/CMakeLists.txt:178,725-735`; `engine/cmake/backends/cpu.cmake:304-317`）。
- 本変数が未設定で、同時に `STRATA_DOT_X4` が文字列 `1` であること。`STRATA_NO_DOT_X4` は設定済みなら常に優先して無効化する（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`）。
- 対象の重み型と実 CPU で利用できる x4 カーネルがあること。x86 tier がコンパイルされた場合、ディスパッチは AVX-512 / AVX2 の表を検索し、重み型・算術契約・CPU ISA に合うものを返す。該当するものがなければ `nullptr` となり、環境変数が有効化条件を満たしても 1 行経路を使う。x86 tier は CMake の `STRATA_CPU_X86` 条件下で組み込まれる（`engine/src/quant/dispatch.cpp:66-85`; `engine/include/strata/quant/dot.hpp:40-46`; `engine/cmake/backends/quant.cmake:23-28`）。
- 4 行カーネルがある場合でも、native expert の特定の行型が先行する専用形式カーネルの分岐で処理されれば、この x4 判定箇所には到達しない。判定は通常の `traits(...)` dot に進んだ後に置かれている（`engine/src/kernels/cpu/native_expert.cpp:680-740,793-865`）。

## 実行時の詳細

`native_gu_rows_impl` と `native_down_rows_impl` の各 template instantiation にある関数内 `static const bool x4_on` を初回呼び出し時に初期化する。初期化時に `STRATA_DOT_X4` と `STRATA_NO_DOT_X4` を読み、その instantiation では結果を cache するため、同じプロセス内で後から環境を変更しても再評価されない。各関数の x4 有効時には、`dot_x4_kernel` が AVX2 算術契約の利用可能な kernel を問い合わせる（`engine/src/kernels/cpu/native_expert.cpp:560-561,734-740,793-794,859-865`; `engine/src/quant/dispatch.cpp:66-85`）。

kernel が得られた gate/up 処理では 4 行ずつ、各 token の gate と up の dot を行い SwiGLU 結果を格納する。down 処理も 4 行ずつ dot の結果を格納する。4 行単位に満たない末尾の行は 1 行ずつ処理される。無効化された場合や kernel pointer が null の場合は最初から 1 行ループを通る（`engine/src/kernels/cpu/native_expert.cpp:751-789,873-893`）。この変数についてサーバーモード、CLI 引数、モデル状態による別の値解釈はない。

## ログと測定値

この変数の判定または 1 行経路への切り替え時に出すログ・警告・終了処理は、該当実装にない（`engine/include/strata/quant/dot_x4_policy.hpp:14-17`; `engine/src/kernels/cpu/native_expert.cpp:734-789,859-893`）。

## 根拠

- 値の判定と優先順位: `engine/include/strata/quant/dot_x4_policy.hpp:14-17`。
- 読み取り、4 行処理、1 行 fallback: `engine/src/kernels/cpu/native_expert.cpp:734-789,859-893`。
- CPU native-expert pool からの呼び出し: `engine/src/kernels/cpu/pool.cpp:1274-1310`。
- Native expert / own CPU quant build 条件: `engine/CMakeLists.txt:178-184,725-735`; `engine/cmake/backends/cpu.cmake:304-317,370-374`。
- CPU ISA と重み型に基づく kernel lookup: `engine/src/quant/dispatch.cpp:66-85`; `engine/include/strata/quant/dot.hpp:40-46`; `engine/cmake/backends/quant.cmake:23-28`。
