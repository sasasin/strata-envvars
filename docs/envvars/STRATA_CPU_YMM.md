# `STRATA_CPU_YMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

x86 CPU の native Q2_0 expert row 計算で、512-bit row kernel を選べるかを設定する。`expert.cpp` は `STRATA_CPU_YMM` が未設定なら `kZmm` を true にし、`q2_rows_512_ok()` は `kZmm` と AVX-512 VNNI 判定の両方が true の場合だけ 512-bit kernel を許可する。変数が設定されていれば、値の内容にかかわらずこの 512-bit 経路を止め、通常は AVX2 kernel に切り替える。対象は `q2_rows_any()` を通る native Q2_0 expert rows であり、CPU 計算全般の ISA 選択を変更するものではない（`engine/src/kernels/cpu/expert.cpp:152,378-380`、`engine/src/kernels/cpu/expert_layout.cpp:465-471`、`engine/src/kernels/cpu/pool.cpp:1274-1302`）。

## 値と判定

コードは `getenv()` の戻り値が null かどうかだけを調べ、値を parse しない。未設定なら `kZmm=true`、設定ありなら `false`。したがって空文字、`0`、`1`、`true`、`false`、`0anything` はすべて同じく 512-bit kernel を止める。大文字小文字、空白、数値としての妥当性、値の境界は判定されず、無効値の警告や fallback もない（`engine/src/kernels/cpu/expert.cpp:152`）。

| 条件 | unset | 設定時に 512-bit 経路を許可する値 | 512-bit 経路を止める値 |
|---|---|---|---|
| `expert.cpp` を含む x86 CPU kernel build | `kZmm=true`。ただし CPU/OS の ISA 判定も必要 | なし | 空文字、`0`、`1`、`true`、その他すべての文字列 |
| この実装を含まない build | 本変数の読み取りなし | 該当なし | 実行時の効果なし |

## 有効になる条件

- `engine/src/kernels/cpu/expert.cpp` がビルドされる x86 CPU kernel build が対象。通常の CPU backend CMake は `STRATA_CPU_X86` の場合に同ファイルを含め、非 x86 側は `portable.cpp` を使う（`engine/cmake/backends/cpu.cmake:241-247`）。SYCL build も CPU kernel に `expert.cpp` を含む（`engine/sycl/CMakeLists.txt:174-179`）。Metal build の CPU library は `expert.cpp` を含まず、`STRATA_CPU_YMM` の読み取り箇所はない（`engine/metal/CMakeLists.txt:145`）。
- 実際の切替先は native Q2_0 expert rows の `q2_rows_any()`。native expert pool の gate/up と down の Q2 行処理から呼ばれる。別形式の native experts や通常の ggml CPU dot 全体をこの変数が切り替えるわけではない（`engine/src/kernels/cpu/pool.cpp:1278-1302`）。
- 512-bit kernel が使われるには、変数が未設定であることに加え `cpu_vnni_ok()` が true である必要がある。これは OSXSAVE と OS の AVX-512 state 保存、AVX-512F/DQ/BW/VL/VNNI を確認する。VBMI がない CPU では既定で VNNI tier を無効にし、`STRATA_VNNI_TIER` の先頭文字が `1` の場合に限って許可する。VBMI がある CPU ではこの追加 opt-in は不要（`engine/src/kernels/cpu/expert_layout.cpp:75-78,148-174,188-203`）。
- `STRATA_FORCE_AVX2=1` または `STRATA_FORCE_ISA` による ISA cap は VNNI 判定を無効化し、512-bit row kernel を止める。`STRATA_CPU_YMM` が設定された場合も同様に512-bitを止めるが、`q2_rows_any()` は AVX2 が使えるなら AVX2 rows、使えなければ AVX1 rows に進む（`engine/src/kernels/cpu/expert_layout.cpp:26-39,75-78,465-471`）。
- AVX-512 VNNI はあるが VBMI がない CPU でも、`STRATA_VNNI_TIER=1` により 512-bit rows が選ばれた場合は、Q2 unpack に VBMI 版ではなくソフトウェア置換版を使う。これは `STRATA_CPU_YMM` の値判定とは別の処理である（`engine/src/kernels/cpu/expert.cpp:193-200`）。
- CLI 引数による上書きはない。ソース全体の名前検索で、実読み取りは `expert.cpp:152` のみで、他の参照は宣言コメント・説明コメント・設定レジストリの記載だった。

## 実行時の詳細

`kZmm` は関数内 static ではなく `expert.cpp` のファイルスコープ `static const bool` で、環境変数の有無を静的初期化時に一度だけ取得する。リクエストごとや row ごとには読み直さず、プロセス実行中に環境を変更しても判定は変わらない（`engine/src/kernels/cpu/expert.cpp:152`）。

Q2_0 native expert pool は gate/up の各 row と down row で `q2_rows_any()` を呼ぶ。同関数は `q2_rows_512_ok()` が true なら 512-bit `q2_0_gguf_rows_multi()`、それ以外で AVX2 が使えるなら AVX2 実装、さらに AVX2 が使えなければ AVX1 実装を呼ぶ（`engine/src/kernels/cpu/pool.cpp:1278-1302`、`engine/src/kernels/cpu/expert_layout.cpp:465-471`）。512-bit 実装は 64 個の Q2 code を一度に unpack して VNNI dot を行い、AVX2 実装とは和の順序が異なるとソースコメントにある（`engine/src/kernels/cpu/expert.cpp:143-152,213-230`）。

`STRATA_CPU_YMM` を読む箇所からログ出力や終了処理へ進む経路はない。値の妥当性による失敗もないため、観測可能な変化は対象 row の kernel 選択である（`engine/src/kernels/cpu/expert.cpp:152,378-380`、`engine/src/kernels/cpu/expert_layout.cpp:465-471`）。

## 根拠

- `engine/src/kernels/cpu/expert.cpp:152` — 環境変数の唯一の実読み取り。設定有無のみを使う。
- `engine/src/kernels/cpu/expert.cpp:193-200,378-380` — 512-bit unpack の選択肢と `kZmm && cpu_vnni_ok()` 条件。
- `engine/src/kernels/cpu/expert_layout.cpp:75-78,148-174,188-203,465-471` — ISA cap、CPU/OS feature probe、VNNI tier opt-in、AVX-512/AVX2/AVX1 の分岐。
- `engine/src/kernels/cpu/pool.cpp:1274-1302` — native Q2_0 gate/up/down rows からの呼び出し。
- `engine/cmake/backends/cpu.cmake:241-269`、`engine/sycl/CMakeLists.txt:174-179`、`engine/metal/CMakeLists.txt:145` — backend ごとのソース構成。
