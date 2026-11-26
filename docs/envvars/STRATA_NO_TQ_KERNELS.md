# `STRATA_NO_TQ_KERNELS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert 経路で trellis 形式（`tq_supported` が認識する形式）の gate/up・down row を、Strata の trellis kernel から量子化レイヤーまたは ggml-cpu の dot に切り替える要求である。設定値が非ゼロでも、該当ビルドの dot がその形式を持たない場合は Strata の kernel を使う。通常の既定動作は Strata kernel で、GPU 側の trellis kernel 選択を切り替える変数ではない。判定は `engine/src/kernels/cpu/tq_cpu.cpp:140-143,177-185`、切替と両 row の呼び出しは `engine/src/kernels/cpu/native_expert.cpp:38-47,675-680,803-805`。

## 値と判定

`tq_kernels_enabled()` の初回評価時に `std::getenv` で値を取り、設定されていて `std::atoi(e) != 0` のときだけ Strata kernel を無効にする。`atoi` は先頭の空白と符号付き整数部分を読み、末尾までの妥当性を検査しない。したがって `1`、`-1`、`1tail` は非ゼロ、`0`、`0tail`、`true`、空文字列はゼロ扱いとなる。数値部分のない文字列もゼロ扱いで、空白だけもゼロ扱いとなる。`atoi` の整数範囲外の入力については文書化された動作を保証できない。

| ビルド・形式 | unset | 設定時に有効になる値（Strata kernel を無効化） | 設定時に無効になる値（Strata kernel を維持） |
|---|---|---|---|
| 既定の `STRATA_OWN_CPU_QUANT=ON` | 有効 | `atoi` が非ゼロでも trellis 形式では切替不可。量子化レイヤーの `traits(type)` は trellis ID（64 以上）に dot を返さず、`native_expert.cpp` が own row に戻す | `0`、空文字、`true` など `atoi` がゼロを返す値。非ゼロ値も実際の row 選択は変えない |
| `STRATA_OWN_CPU_QUANT=OFF`、ggml-cpu が該当 trellis type の dot を持つ | 無効 | `atoi` が非ゼロの値 | `0`、空文字、`true` など `atoi` がゼロを返す値 |
| `STRATA_OWN_CPU_QUANT=OFF`、ggml-cpu が trellis type / dot を持たない | 有効 | 非ゼロでも切替不可。Strata own row に戻る | `atoi` がゼロを返す値 |

既定の量子化レイヤーは type ID 64 以上に対して空の trait を返す実装であり、trellis type の `has_dot()` は偽となる（`engine/include/strata/kernels/cpu/pool_quant.hpp:32-65`）。`STRATA_OWN_CPU_QUANT=OFF` では ggml-cpu の `vec_dot` trait を確認する（同 `:78-92`）。OFF ビルドでも upstream ggml のように該当 type が `GGML_TYPE_COUNT` 外なら own row を維持し、型が登録されていて `vec_dot` がある場合に限って切替が成立する（`engine/src/kernels/cpu/native_expert.cpp:43-47`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` を含む CPU native expert 実装がビルドされ、その `native_gu_rows` または `native_down_rows` が trellis type に対して呼ばれる必要がある。CPU backend では `native_expert.cpp` と trellis dispatcher が追加され、x86 以外は scalar trellis source のみ追加される（`engine/cmake/backends/cpu.cmake:303-317,370-374`）。Metal host も `native_expert.cpp` と scalar trellis source を含む（`engine/metal/CMakeLists.txt:140-146`）。
- ggml-cpu dot への切替には `STRATA_OWN_CPU_QUANT=OFF` かつ、対象 ggml-cpu が該当形式の dot を提供することが必要。既定の ON ビルドでは trellis type の dot がなく、変数を設定しても Strata own row に戻る（`engine/include/strata/kernels/cpu/pool_quant.hpp:32-65,78-92`; `engine/src/kernels/cpu/native_expert.cpp:40-47`）。
- 対象は CPU native expert row の経路に限られる。GPU 用 trellis kernel は本変数を参照しない。サーバーモードや CLI 引数による別の上書きは見つからなかった（全参照の検索結果では実際の環境読み取りは `tq_cpu.cpp:179` のみ）。
- Own kernel が選ばれる場合の ISA は別の `STRATA_TQ_ISA` 判定に従う。x86 では CPU が対応する場合 AVX-512 / AVX2、非 x86 では scalar が使われる（`engine/src/kernels/cpu/tq_cpu.cpp:155-175`; `engine/include/strata/kernels/cpu/tq_cpu.hpp:53-61`）。

## 実行時の詳細

`tq_kernels_enabled()` は関数内 `static const bool` を初期化する lambda で値を一度だけ読む。実際には `tq_rows_own()` が trellis type についてこの関数を呼ぶ最初のときに評価され、そのプロセス内では cache されるため、評価後に環境を変更しても再評価されない（`engine/src/kernels/cpu/tq_cpu.cpp:177-185`; `engine/src/kernels/cpu/native_expert.cpp:40-47`）。

gate/up row は `tq_rows_own(f.gu_type)` が真なら `tq_gu_rows` を呼び、down row は `tq_rows_own(f.d_type)` が真なら `tq_rows` を呼ぶ。切替可能な build で変数に非ゼロ値があり、ggml-cpu dot が使える場合はこの分岐を通らず、後続の `traits(...).dot(...)` に進む。dot がない場合は条件式が own row を選ぶため、未知の型を ggml-cpu に問い合わせる経路には進まない（`engine/src/kernels/cpu/native_expert.cpp:40-47,675-680,734-789,803-805`）。選択されるのは row 計算実装であり、出力の bit 単位の一致まではこの切替コードから保証できない。

## ログと測定値

この変数の読み取り・fallback 自体に専用のログ、警告、終了処理はない。切替不可のときも own row へ戻るだけである（`engine/src/kernels/cpu/tq_cpu.cpp:177-185`; `engine/src/kernels/cpu/native_expert.cpp:40-47`）。`docs/GYRO.md:262-265` は AVX2 の CPU trellis kernel が ggml-cpu の expert あたり時間の約 45%であると記載し、`build/tq_cpu_parity --bench` で手元 CPU の計測ができるとしている。同箇所には機種、モデル、計測回数などの条件がないため、その比率は一般化できない。同文書は既定 build で `STRATA_NO_TQ_KERNELS=1` は変更を生じないとも記載し、既定 `STRATA_OWN_CPU_QUANT=ON` の trait 分岐と整合する。

## 根拠

- 候補名の実読み取り、`atoi` 判定、cache: `engine/src/kernels/cpu/tq_cpu.cpp:177-185`
- trellis type の認識: `engine/src/kernels/cpu/tq_cpu.cpp:140-143`
- own row と ggml-cpu dot の選択条件: `engine/src/kernels/cpu/native_expert.cpp:38-47`
- gate/up と down の dispatch / dot fallback: `engine/src/kernels/cpu/native_expert.cpp:675-680,734-789,803-805`
- build 条件、量子化 trait: `engine/cmake/backends/cpu.cmake:303-317,370-374`; `engine/include/strata/kernels/cpu/pool_quant.hpp:32-65,78-92`
- Strata 文書の説明と計測値: `docs/GYRO.md:262-265`; 候補索引: `docs/SETTINGS.md:189`
