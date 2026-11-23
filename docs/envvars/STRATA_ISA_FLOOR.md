# `STRATA_ISA_FLOOR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この環境変数は Terminal の Python setup がローカル engine をビルドするときに、x86 CPU の最低 ISA floor を選ぶための入力です。認識する値は `avx` と `none` です。`avx` は AVX1、`none` は SSE4.2 + POPCNT の build を要求します。unset・空文字・その他の値ではこの指定を採用せず、setup が CPU 機能から floor を自動判定します。環境変数そのものを engine の実行中に読む処理は確認できません。setup が値を CMake の `-DSTRATA_ISA_FLOOR=...` に変換し、compile-time の定義と build 設定に反映します（`terminal/setup.py:1779-1799, 6755-6760`; `engine/CMakeLists.txt:46-56`）。

通常の NVIDIA 経路では、変数を設定しただけで ready-made engine の代わりにビルドすることはありません。CLI の `--build`、または AVX2 のない CPU で setup が自動的に選ぶローカル build が、値を engine に反映する主な経路です。Linux の HIP engine は setup がローカルビルドを行います（`terminal/setup.py:11727-11738, 9513-9542`）。

## 値と判定

setup は `os.environ.get(..., "")` の結果に `strip().lower()` を適用し、全体が `avx` または `none` と一致するかを判定します。数値 parse はせず、前後空白を除去し、大文字小文字を区別しません。未設定と空文字は同じ扱いです。無効値もエラーにはせず、自動判定へ進みます（`terminal/setup.py:1779-1799`）。

| setup が読む値 | 判定結果 |
|---|---|
| unset、空文字、空白だけ | ARM64 なら通常 floor（空文字）。それ以外は CPU を自動判定し、AVX2 があれば通常 floor、なければ AVX があれば `avx`、SSE4.2 と POPCNT があれば `none`、どれもなければ `unsupported` |
| `avx`（例: `avx`, ` AVX `） | 強制的に `avx` を選択 |
| `none`（例: `none`, ` NONE `） | 強制的に `none` を選択 |
| その他（例: `0`, `1`, `true`, `false`, `bogus`, `avx_f16c`） | 無効値として捨て、自動判定 |

この環境変数の有効値を選んでも、setup が必ずビルドするわけではありません。CPU に AVX2 がない場合、`--check` でなければ setup は警告後にローカル build を選びます。一方、AVX2 がある PC では `--build` を指定しない限り、通常の NVIDIA 経路は ready-made engine を使い得ます。`--check` は floor 判定後に PC 情報を表示して終了し、engine をビルドしません（`terminal/setup.py:11718-11738, 11739-11758, 9513-9542`）。

## 有効になる条件

- 値が効くのは setup がローカル engine build を実行するときです。NVIDIA の通常経路で既製 engine を使う場合、値が `avx` / `none` でもその engine の build 設定は変わりません。`--build` は既製 engine を選ばずビルドします（`terminal/setup.py:11317, 9531-9542`）。
- AVX2 非対応 CPU では、setup が環境変数の指定（認識可能な場合）または CPU 自動判定から floor を選び、`--check` 以外では build に切り替えます。`unsupported` のときは「this CPU has neither AVX2 nor SSE4.2; Strata needs at least SSE4.2 (Intel Nehalem, 2008, or newer)」で setup を停止します（`terminal/setup.py:11718-11738`）。
- AVX2 対応 CPU で `avx` / `none` を強制しても `--build` の代わりにはなりません。ローカル build が選ばれたときにその floor が使われます。Linux の HIP 経路は engine がない場合にローカル build へ進み、Windows の HIP 経路は ready-made engine がなければ停止します（`terminal/setup.py:9513-9542`）。
- engine の CMake 設定では `STRATA_PORTABLE=ON` と非空の floor は併用できず、configure が「STRATA_ISA_FLOOR (an older-CPU build) and STRATA_PORTABLE (the AVX2 release build) exclude each other」で停止します。非 x86 build では警告後に floor を空へ戻します（`engine/CMakeLists.txt:50-56, 73-82`）。setup の認識値はこの親 CMake の `avx` / `none` に限られます。
- floor は build 時に記録されるため、CLI 引数や別の環境変数で実行時に上書きする経路は見つかりません。CPU の実機能が選んだ floor に足りない場合は engine 起動時に拒否されます（`engine/src/program/generate.cpp:5309-5339`）。

## 実行時の詳細

setup の `cpu_floor()` は呼ばれるたびに環境変数を読みます。関数内 static cache はありません。環境値の確認後、ARM64 は通常 floor（空文字）を返します。その他の CPU では Windows は CPUID、Windows 以外は `/proc/cpuinfo` の `flags` を使い、ファイル読み取りに失敗すると機能フラグなしとして扱います。setup は初回の PC 検査で floor を決め、非 AVX2 CPU なら engine build を選びます。CUDA / HIP の build 関数でも floor を再取得し、既存のローカル engine の記録と異なれば再利用対象にせず、build 引数に floor を含めます。build directory の `CMakeCache.txt` に別 floor が記録されている場合は削除してから configure します（`terminal/setup.py:1768-1799, 5584-5589, 5611-5617, 6755-6760, 6840-6863`）。

CMake では `avx` / `none` 以外の非空値を直接渡すと configure が fatal error になります。setup 経由では未知の環境値を自動判定に置き換えるため、このエラーにはなりません（`engine/CMakeLists.txt:50-56`; `terminal/setup.py:1783-1799`）。floor build は ggml-cpu の ISA 設定をその floor に制限し、Strata の CPU kernels には floor 用 compile definition を付けます。AVX2 / AVX-512 kernels は binary 内に残りますが、実 CPU 機能の gate を通らない限り実行されません（`engine/cmake/strata_ggml.cmake:40-58`; `engine/cmake/backends/cpu.cmake:343-358`）。

engine 起動時に compile-time floor を `isa_floor_build()` が返し、AVX2 がない CPU では floor が空ならエラー終了（return 2）、floor がある場合は必要な AVX1 または SSE4.2 + POPCNT が CPU にあるか確認します。不足時もエラーを stderr に出して return 2 します。対応 CPU で AVX2 がない場合、CPU experts は ggml-cpu の kernels を使う旨を stderr に出します。これは build に記録された floor の検査であり、実行時に `STRATA_ISA_FLOOR` を再読込するものではありません（`engine/src/kernels/cpu/expert_layout.cpp:286-294`; `engine/src/program/generate.cpp:5303-5339`）。

## ログと測定値

AVX2 のない CPU で setup がローカル build を選ぶ場合、次の警告を表示します（floor を強制したときも選択値が含まれます）:

> this CPU has no AVX2: Strata support for it is EXPERIMENTAL and slow. Setup compiles the engine on this PC for AVX (STRATA_ISA_FLOOR=avx; 10-20 minutes, once), and the CPU's share of the experts runs on ggml-cpu's kernels, a few times slower than on an AVX2 CPU. See "Older CPUs" in docs/INSTALL.md

実際には `AVX` の部分と括弧内の値は選択された floor に応じて変わります（`terminal/setup.py:11727-11738`）。

engine は floor build で必要な ISA が CPU にない場合、例えば次の形式を stderr に出し return 2 します。

- `strata generate: this engine is the older-CPU build for AVX, which this CPU (<CPU名>) does not have; compile it with STRATA_ISA_FLOOR=none`
- `strata generate: this engine is the older-CPU build for SSE4.2 with POPCNT, which this CPU (<CPU名>) does not have`

floor build で AVX2 がない場合は `strata generate: EXPERIMENTAL older-CPU build (ggml-cpu for <floor>): this CPU has no AVX2, so the CPU's experts run on ggml-cpu's kernels - expect it to be slow` を stderr に出します。AVX2 対応 CPU 上で floor build を動かす場合は通常 build の方が速い旨を表示します（`engine/src/program/generate.cpp:5325-5339`）。

## 根拠

- `terminal/setup.py:1779-1799` — setup の値取得・正規化・CPU 自動判定。
- `terminal/setup.py:11718-11738` — unsupported CPU の停止、旧 CPU の警告と自動 build 選択。
- `terminal/setup.py:5584-5589, 5611-5617, 6840-6863, 6755-6760` — HIP / CUDA build の floor 判定、CMake 引数化、cache 切替。
- `terminal/setup.py:11317, 9513-9542` — `--build` と既製 engine 選択の関係。
- `engine/CMakeLists.txt:46-56, 73-82` — CMake 側の許容値、portable との排他、非 x86 の扱い。
- `engine/cmake/strata_ggml.cmake:40-58`; `engine/cmake/backends/cpu.cmake:343-358` — floor 別の CPU build 設定。
- `engine/src/kernels/cpu/expert_layout.cpp:286-294`; `engine/src/program/generate.cpp:5303-5339` — build floor の埋め込み、実 CPU 機能の検査と観測可能な終了・ログ。
