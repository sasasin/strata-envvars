# `I8_ESIMD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`I8_ESIMD` は `engine/sycl/tools/build.sh` が読む**ビルド時の環境変数**で、SYCL エンジンに fused int8 ESIMD expert kernels を含めるかを CMake の `STRATA_SYCL_I8_ESIMD` に渡す。実行中の Strata が `I8_ESIMD` を読む箇所はなく、ランタイム設定ではない。OFF でビルドすると該当実装は stub になり、対応する prompt expert が利用可能な場合の int8 経路は無効になる（`engine/sycl/tools/build.sh:38-43`, `engine/sycl/CMakeLists.txt:78-96`, `engine/sycl/src/prefill/esimd_moe.dp.cpp:41-58`）。

## 値と判定

シェルスクリプトは数値変換をせず、初回 CMake 設定では `${I8_ESIMD:-AUTO}` を渡す。未設定または空文字なら `AUTO`。CMake は文字列全体を大文字小文字を区別して `AUTO` / `ON` / `OFF` のいずれかと照合する（`engine/sycl/tools/build.sh:25,40-43`, `engine/sycl/CMakeLists.txt:83-93`）。

| ビルド条件 | unset / 空文字 | 受理値 | 無効値・結果 |
|---|---|---|---|
| 新規 configure、JIT（`AOT` 空） | `AUTO`。カーネルを含める | `AUTO` または `ON`: 含める。`OFF`: stub にする | 例: `off`, `AUTO `, `0`, `true` は CMake の `FATAL_ERROR` |
| 新規 configure、AOT が `bmg` / `lnl` で始まる | `AUTO`。カーネルを含める | 上記と同じ | 同上 |
| 新規 configure、その他の非空 AOT | `AUTO`。stub にする | `ON`: 含める。`OFF`: stub にする | `AUTO` は stub。その他は同上 |
| 既存 build directory | 空文字なら既存 CMake cache を維持 | 非空なら当該値で cache を更新してから build を試みる | 不正値での更新エラーはスクリプトが隠すため、既存 cache の値のまま続く場合がある |

CMake の `AUTO` は JIT と `bmg` / `lnl` AOT で有効、それ以外の非空 AOT で無効になる。`ON` はこの AOT 条件を適用せず有効、`OFF` は全 build で無効。新規 build で不正値を渡すと configure は `STRATA_SYCL_I8_ESIMD must be AUTO, ON or OFF (got '...')` で失敗する。既存 build では `build.sh` の2回目の configure が標準出力・標準エラーを捨て、その終了状態も検査しないため、失敗後に以前の cache が使われ得る（`engine/sycl/tools/build.sh:40-44`, `engine/sycl/CMakeLists.txt:83-96`）。

## 有効になる条件

- 対象は `engine/sycl` の SYCL build。CUDA / HIP / 他の build にこの環境変数を適用する処理は見つからない（`engine/sycl/tools/build.sh:1-6`）。
- CMake の `AUTO` でカーネルを含めるのは JIT build、または AOT device 名が `bmg` / `lnl` で始まる build。その他の AOT は stub になる。`ON` は CMake 判定上この制限を外す（`engine/sycl/CMakeLists.txt:73-76,83-96`）。
- 実行時に int8 prompt expert 経路を使うには、カーネルが build に含まれ、対象 device が ESIMD と s8 matrix combination（`nsize=16`, `ksize=32`）を持つ必要がある。利用可否は device ごとに cache され、`STRATA_I8_FORCE` の先頭文字が `0` なら利用不可になる（`engine/sycl/src/prefill/esimd_moe.dp.cpp:840-858`）。
- モデル側では native expert layout、対応する gate/up と down の型、`n_ff=640`, `n_embd=2560` などの形状条件を満たし、MMQ / XMX mode による除外や Hadamard 条件に該当せず、`available()` が true である必要がある。満たさない層・形式は int8 経路を使わない（`engine/sycl/src/prefill/prefill.cpp:4772-4787`）。
- ランタイム選択には別変数 `STRATA_PREFILL_MMQ`（空または未設定時は `STRATA_PF_I8`）も関与する。明示的に int8 を選んでも build stub または非対応 device では `available()` が false のため実カーネルを使えない。`I8_ESIMD` 自体はランタイム選択を上書きしない（`engine/sycl/src/prefill/prefill.cpp:333-350`, `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`）。
- AOT が `bmg` / `lnl` で始まり、`I8_ESIMD` が `OFF` でなく、`ALLOW_BAD_OCLOC` が厳密に `1` でない場合、build script は既知の不具合版 `ocloc` を検査する。これは build 前の保護条件であり、カーネルの選択条件とは別（`engine/sycl/tools/build.sh:15-35`）。

## 実行時の詳細

環境変数は `build.sh` 起動時のシェル展開で参照され、CMake cache 値とコンパイル時定義 `STRATA_I8_NO_ESIMD=1`（無効時）に変換される。実行中のプロセスが `I8_ESIMD` を読み直すことはなく、プロセス起動後の環境変更は効果がない。既存 build directory では空の `I8_ESIMD` は cache の値を変えず、非空値だけを更新しようとする（`engine/sycl/tools/build.sh:38-44`, `engine/sycl/CMakeLists.txt:88-96`）。

stub build の `available()` は常に false を返す。ランタイムの `STRATA_PREFILL_MMQ` などが int8 経路を選ぶ設定でも、該当経路の適用条件を満たせず、通常の FP16 / XMX 側の処理に残る。なお `I8_ESIMD` の直接読み取りは build script だけで、別のランタイム挙動は確認できない（`engine/sycl/src/prefill/esimd_moe.dp.cpp:41-58`, `engine/sycl/src/prefill/prefill.cpp:4772-4787`）。

## ログと測定値

機能を stub にする設定では CMake が `Strata SYCL: the fused int8 ESIMD expert kernels are off (STRATA_SYCL_I8_ESIMD=<値>): stubs, the XMX path serves the prompt's experts` を status 出力する（`engine/sycl/CMakeLists.txt:94-96`）。既知の不具合 `ocloc` に該当すると `build.sh` は stderr に version と回避策を表示し、終了コード 2 で停止する（`engine/sycl/tools/build.sh:25-35`）。ビルド後に I8 の runtime mode が選択されたときのログは `STRATA_PREFILL_MMQ` によるもので、この変数自身のログではない（`engine/sycl/src/prefill/prefill.cpp:1416-1419,4880-4886`）。

`docs/INTEL.md:85-90` と `docs/release-notes-0.2.1.md:67` も OFF 時の build stub と XMX 経路を説明しており、現行 CMake の分岐と整合する。これらの資料にある性能・正確性の表現は本調査で新たに測定していないため、測定値は記載しない。

## 根拠

- `engine/sycl/tools/build.sh:25-50` — build guard、CMake への値の引き渡し、既存 cache 更新、build の観測出力。
- `engine/sycl/CMakeLists.txt:73-96,303-309` — AOT 条件、値の検証、stub 用 compile definition とカーネルソース。
- `engine/sycl/src/prefill/esimd_moe.dp.cpp:41-58,840-858` — stub の挙動と runtime device availability。
- `engine/sycl/src/prefill/prefill.cpp:333-350,4772-4787` — runtime mode とモデル・経路条件。
- `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50` — runtime mode 値の判定。
