# `STRATA_KQ256`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native-expert 経路で、複数 token をまとめて計算する AVX2 K-quant row kernel を opt-in する。gate/up の Q4_K と down の Q5_1 / Q8_0 が対象で、各行の重み依存の decode を token ごとに繰り返さずに計算する。KQ256 の kernel は ggml-cpu の AVX2 dot と bit-exact とソースに記されている。1 token の場合は従来の dot に残る（`engine/src/kernels/cpu/native_expert.cpp:656-673, 815-818`、kernel の説明は `engine/src/kernels/cpu/kq_avx2.cpp:1-13`）。

これは CPU native-expert row dispatch の設定であり、GPU kernel を選ぶ設定ではない。native expert support を有効にした build で `native_expert.cpp` が CPU kernel library に加わり、CPU pool が gate/up と down の行処理からその関数を呼ぶ（`engine/cmake/backends/cpu.cmake:304-317, 370-374`、`engine/src/kernels/cpu/pool.cpp:1274-1309`）。

## 値と判定

どちらの読み取りも `std::getenv` の結果を `std::atoi` に渡し、その整数が 0 でないかで判定する。文字列全体の厳密な検査、真偽語の解釈、範囲制限はない。`atoi` は先頭空白と符号の後の数字列を読むため、例では `1`, `-1`, `1tail`, ` 1` が有効、`0`, `0tail`, 空文字, `true`, `tail1` は無効になる。数値に変換できない文字列は 0 扱い。int の範囲外入力はコードで検査されない。gate/up と down の読み取り箇所は別々の関数 template 内にある（`engine/src/kernels/cpu/native_expert.cpp:659, 799`）。

| 読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| gate/up | 無効 | `atoi(value) != 0` かつ初回評価時に AVX2 が利用可能 | `atoi(value) == 0`、または初回評価時に AVX2 が利用不可 |
| down | 無効 | `atoi(value) != 0`。実際の dispatch でも AVX2 が利用可能であること | `atoi(value) == 0`、または dispatch 時に AVX2 が利用不可 |

CLI 引数、設定ファイル、他の設定値による `STRATA_KQ256` の上書きはこの実装にない。AVX-512 KQ512 には独立した先行 dispatch があり、`STRATA_NO_KQ512` と `STRATA_KQ512_MIN` の条件で KQ512 が選ばれた row は、KQ256 判定まで来ない（同ファイル `:660-673, 807-817`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` を有効にした build の CPU native-expert pool 経路であること。CPU backend の native-expert macro は native source と x86 kernel source を追加する。native experts 無効の build では別実装に置き換わる（`engine/cmake/backends/cpu.cmake:304-317, 370-374`、`engine/src/kernels/cpu/expert_layout.cpp:490-496`）。
- gate/up は `f.gu_type == 12`（Q4_K）、down は `f.d_type == 7`（Q5_1）または `8`（Q8_0）で、row group の token 数 `nt >= 2` であること（`engine/src/kernels/cpu/native_expert.cpp:670-673, 815-818`）。
- CPU が AVX2 kernel を実行可能であること。判定は CPU ISA cap、FMA / OSXSAVE / AVX / F16C、OS が AVX state を保存する XCR0、CPUID AVX2 bit を確認する（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。AVX2 が使えなければ通常の dot 経路へ進む。
- AVX-512 KQ512 が先に dispatch された row では KQ256 は使われない。gate/up の Q4_K、down の Q5_1 / Q8_0 は KQ512 の対象で、AVX-512 条件・自己検査・`STRATA_KQ512_MIN` を満たす場合に先に return する。`STRATA_NO_KQ512` が設定されている場合は KQ512 の有効化を止める（同ファイル `:660-673, 807-817`）。
- `Arithmetic::WindowInvariant` 呼び出しでは `flavour_avx2()` も必要条件となる。通常の `Default` arithmetic ではこの追加条件はない（同ファイル `:669-672, 815-818`; wrapper と pool dispatch は `:896-915`, `engine/src/kernels/cpu/pool.cpp:1290-1309`）。
- モード別の別設定はない。pool の通常 row phase と dependency task の両方が native row 関数へ dispatch する（`engine/src/kernels/cpu/pool.cpp:1274-1309, 1414-1453`）。

## 実行時の詳細

`native_gu_rows_impl` と `native_down_rows_impl` の関数内 `static` 初期化で環境を読む。各 template specialization について最初に対応する関数が呼ばれた時点で値が確定し、そのプロセス内の後続呼び出しでは再読込されない。gate/up では同じ cache 初期化時に `cpu_avx2_ok()` も評価する。down では環境値を cache し、kernel 分岐で `cpu_avx2_ok()` を確認する（`engine/src/kernels/cpu/native_expert.cpp:659, 799, 815`）。従って、初回評価後にプロセス環境を変更してもこの設定の判定は変わらない。

設定が有効でも、gate/up の Q4_K または down の Q5_1 / Q8_0 以外、あるいは `nt < 2` では KQ256 kernel に入らず、後続の通常 dispatch が計算する。条件を満たす場合、gate/up は `kq256_gu_rows`、down は `kq256_rows` を呼ぶ。1 token の結果は従来の dot に委ねる（`engine/src/kernels/cpu/native_expert.cpp:669-673, 815-818`）。KQ256 固有の警告・ログ・終了・timeout 経路は読み取り箇所と dispatch にない。

## ログと測定値

KQ256 の有効・無効を知らせる実行時ログはない。ソースコメントには「engine では速くならなかった」とあり、decode window の expert group は約 1.4 token で、従来の ggml per-token call 間でも重みが L1 に残る条件、および `native_expert_parity` で 1.01–1.13x と記されている（`engine/src/kernels/cpu/native_expert.cpp:656-659`）。そのコメントには CPU 機種、OS、量子化 pack、測定回数などの詳細がないため、この値は一般的な速度差として扱えない。

関連資料の記述は測定範囲が異なる。`docs/QUANTS.md:124-126` は「3–4 tokens で Q4_K が 11–20% off」としている一方、`docs/UNSLOTH_Q4.md:228-234` は KQ256 を「measured no faster」としている。さらに特定の UD-Q4_K_XL 実機比較は RTX PRO 4500 の試験環境で short / codegen 各 3 run、明確な差なしと記録されている（`docs/bench-results/2026-10-01-community-rtx-pro-4500/README.md:346-363, 430-436`）。これはソースの動作説明を置き換える結果ではなく、測定条件の異なる資料間の比較である。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:656-673` — gate/up Q4_K の環境読み取り、値判定、KQ512 との順序、token 数と arithmetic 条件、KQ256 kernel 呼び出し。
- `engine/src/kernels/cpu/native_expert.cpp:792-818` — down の環境読み取り、値判定、KQ512 との順序、AVX2・型・token 数条件、KQ256 kernel 呼び出し。
- `engine/src/kernels/cpu/kq_avx2.cpp:1-13` — KQ256 kernel の対象形式、AVX2 arithmetic と bit-exact 性についての実装コメント。
- `engine/src/kernels/cpu/expert_layout.cpp:206-238` — CPU AVX2 capability 判定。
- `engine/cmake/backends/cpu.cmake:304-317, 370-374` — native experts build 時の source 組み込みと x86 kernel build 条件。
- `engine/src/kernels/cpu/pool.cpp:1274-1309, 1414-1453` — CPU pool の native row dispatch。
