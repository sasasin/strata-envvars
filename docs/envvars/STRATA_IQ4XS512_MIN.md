# `STRATA_IQ4XS512_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert の gate/up 行計算で、IQ4_XS（型番号 23）に使う Strata AVX-512 行カーネルを、expert グループの token 数 `nt` がこの値以上のときに選ぶ下限を設定する。これは GPU の IQ4_XS 経路や通常の単体行列積全般を設定する変数ではない。該当分岐に入らない場合は後続 dispatch に進み、VNNI 対応 CPU では通常 ggml-cpu の dot に戻る。`native_gu_rows_impl` が環境値を読む場所と選択分岐は `engine/src/kernels/cpu/native_expert.cpp:560-560,620-627`、実行時の CPU pool 呼び出しは `engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡し、未設定なら `1` を使う。空文字は設定済みとして `atoi("") == 0` になり、数値変換後の範囲検査、文字列全体の検証、clamp はない。`atoi` は先頭の空白と符号を許し、先頭の整数部分を変換して後続文字を無視する。整数に変換できない先頭なら `0` になる。`int` で表現できない値に対する `atoi` の結果は保証されない。分岐は `nt >= iq4xs512_min` なので、`nt` が正である実行では 0 や負の値も下限条件を通す。根拠: `engine/src/kernels/cpu/native_expert.cpp:624-625`。

| 条件 | unset | 有効になる値の例 | 値による下限不成立の例 |
| --- | --- | --- | --- |
| CPU native expert dispatch の各算術 specialization | `1`（1 token から条件を満たす） | `1`, `2`, `3junk`（下限 3）, `  +4tail`（下限 4）, `0`, `-2` | `2` は `nt=1` で不成立。`abc` と空文字は 0 になり、正の `nt` なら条件成立 |

無効文字列をエラーとして拒否する処理や、この変数に関する起動ログはない。別の CLI 引数や設定値による同じ下限の上書きも、この dispatch にはない。

## 有効になる条件

- CPU native expert の gate/up dispatch が呼ばれ、`f.gu_type == 23`（IQ4_XS）であること。Q2 native kernel に別 dispatch されるとこの分岐には来ない（`engine/src/kernels/cpu/pool.cpp:1277-1296`）。
- `cpu_vnni_ok()` が true であること。x86 以外の実装は false を返す。x86 では CPU の AVX-512 F/DQ/BW/VL と VNNI を確認し、VBMI 非対応 tier は `STRATA_VNNI_TIER` の先頭文字が `1` の場合に許可される。`STRATA_FORCE_AVX2=1` または `STRATA_FORCE_ISA` による ISA 制限はこの probe を無効にする（`engine/src/kernels/cpu/expert_layout.cpp:42-51,74-78,188-203`）。
- `STRATA_NO_IQ512` が未設定であること。この変数は存在有無で AVX-512 i-quant 経路を止めるため、空文字や `0` でも設定されていれば本変数の値にかかわらず分岐しない（`engine/src/kernels/cpu/native_expert.cpp:568,623`）。
- `STRATA_NO_IQ4XS512` が未設定であること。同様に存在有無だけを見るため、空文字や `0` も無効化する（`engine/src/kernels/cpu/native_expert.cpp:623`）。
- `nt >= atoi(STRATA_IQ4XS512_MIN)`（未設定時は `nt >= 1`）、`f.tail_off == 0`、および `iq512_reference_ok(23)` が true であること。`tail_off` は NVFP4 の追加 scale tail がある blob で非ゼロになる（`engine/src/kernels/cpu/native_expert.cpp:400-405,625-626`）。
- AVX-512 カーネル実装は x86 build で追加される。非 x86 build では probe が false なのでこの変数で有効化できない（`engine/cmake/backends/cpu.cmake:303-317`）。

## 実行時の詳細

`native_gu_rows_impl` の `Default` / `WindowInvariant` specialization ごとに、初めてその関数へ入った際に関数内 `static` として値を読み、保持する。プロセス起動時に必ず読むのではなく、最初の native gate/up row dispatch 時に読むため、それ以降に環境を変更してもその specialization の判定には反映されない（`engine/src/kernels/cpu/native_expert.cpp:559-560,620-625,898-910`）。

条件を満たすと `iq512_reference_ok(23)` が、合成 IQ4_XS block に対する Strata AVX-512 行計算とリンク済み quant trait の dot 結果を bitwise 比較する。この check は type ごとに mutex 保護の map に保存され、以後再実行しない。check が通れば `iq512_reference_gu_rows` が gate/up rows を計算して dispatch を終了する。通らなければこの最適化を使わず後続処理へ進み、VNNI 対応 CPU では IQ4_XS が `iq512_supported` の一覧に含まれず、AVX2 kernel も `!cpu512` 条件のため使われないので、通常の per-token dot に到達する（`engine/src/kernels/cpu/native_expert.cpp:87-121,280-286,625-627,681-704,734-740`）。

この変数は gate/up のカーネル選択だけに作用し、down rows や token 数・expert 選択・CLI/サーバーモードの選択は変えない。`nt` は pool が各 expert job について渡すグループ内 token 数（`engine/src/kernels/cpu/pool.cpp:1290-1296`）。

## ログと測定値

下限を使ったことを示すログはない。照合が不一致の場合に限り stderr に `strata: the window-invariant 512-bit rows of type 23 differ from this ggml-cpu's dot: its dot runs per token instead` と出し、最適化を選ばない（`engine/src/kernels/cpu/native_expert.cpp:117-120`）。trait に dot / Q8_K quantizer がない場合は照合自体が行われず false となるが、この理由だけのログはない（同 `:93-95`）。この調査では build・実行・性能測定をしていないため、現行 checkout にある測定値は記載しない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:559-560,620-627` — 読み取り、default、閾値、選択条件。
- `engine/src/kernels/cpu/native_expert.cpp:87-121,280-286,681-704,734-740` — 照合と fallback dispatch。
- `engine/src/kernels/cpu/pool.cpp:1274-1296,1414-1429` — native expert の実行呼び出し。
- `engine/src/kernels/cpu/expert_layout.cpp:42-51,74-78,188-203` — OS/CPU ISA 判定と tier gate。
- `engine/cmake/backends/cpu.cmake:303-317` — CPU native expert / x86 カーネルの build source。
