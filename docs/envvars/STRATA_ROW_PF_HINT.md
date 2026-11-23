# `STRATA_ROW_PF_HINT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の native expert 行カーネルがソフトウェア・プリフェッチを要求するときに渡すヒントを選ぶ。x86 では `0` が T0、`2` が NTA、それ以外が T1 となる。GNU 系の非 x86 では対応する `__builtin_prefetch` の locality 値に変換される。読み取りや書き込みのデータ、計算結果を変える処理ではなく、プリフェッチ命令のヒントを選ぶだけである（`engine/src/kernels/cpu/native_expert.cpp:264-271`, `engine/include/strata/kernels/cpu/row_prefetch.hpp:31-43`）。

この変数単独ではプリフェッチを開始しない。行カーネルが一般的な dot 経路に進み、かつ `STRATA_ROW_PF` で正の距離が設定された場合に、行ループがこのヒントを使う（`engine/src/kernels/cpu/native_expert.cpp:741-747`, `engine/src/kernels/cpu/native_expert.cpp:771-773`, `engine/src/kernels/cpu/native_expert.cpp:866-870`, `engine/src/kernels/cpu/native_expert.cpp:884-886`）。

## 値と判定

`row_pf_hint()` は `std::getenv` で取得し、未設定または空文字なら `1`、それ以外は `std::atoi` で整数化する。関数内 `static const int` に保存されるため、最初の呼び出し時に一度だけ評価される（`engine/src/kernels/cpu/native_expert.cpp:265-271`）。

| 条件 | unset | 有効になる値（例） | 無効・その他の値（例） |
|---|---|---|---|
| 全ビルド共通の整数化 | `1` | `0`、`1`、`2` | 不正値を拒否する処理はない。`true`、`false`、`abc` は `atoi` が `0` を返す。`2x` は `2`、`0anything` は `0` として扱う。空文字だけは既定値 `1`。 |
| x86 (`STRATA_ROW_PF_X86`) | `1` | `0` → T0、`2` → NTA、`1` → T1 | その他すべて（例: `-1`、`3`、文字列からの `0`）は T1 分岐。 |
| 非 x86、`__GNUC__` 定義あり | `1` | `0` → locality 3、`2` → locality 0、`1` → locality 2 | その他すべては locality 2 分岐。 |
| 非 x86、`__GNUC__` 定義なし | `1` | 値は整数化される | `row_prefetch_line` はポインターと hint を使わず何もしない。 |

全体文字列の厳密な数値検証はない。`atoi` は先頭の空白と符号を許し、先頭の整数部分を読み、後続文字を無視する。数値に変換できない文字列は `0` になる。したがって `true` や `abc` は x86 では T0 分岐になる。大文字小文字を区別する真偽値判定や範囲チェック、無効値の警告はない（`engine/src/kernels/cpu/native_expert.cpp:267-269`, `engine/include/strata/kernels/cpu/row_prefetch.hpp:31-43`）。

## 有効になる条件

- `native_gu_rows_impl` または `native_down_rows_impl` が、先行する専用型・ISA カーネルの分岐から戻らず一般 dot 経路に到達すること。これらの関数では、プリフェッチ設定の参照より前に trellis、AVX、NVFP4 などの経路を選んで return する分岐がある（`engine/src/kernels/cpu/native_expert.cpp:559-560`, `engine/src/kernels/cpu/native_expert.cpp:700-740`, `engine/src/kernels/cpu/native_expert.cpp:792-867`）。
- `STRATA_ROW_PF` が正の整数に変換され、`pf_rows > 0` になること。未設定・空文字の `STRATA_ROW_PF` は `0` で、hint 値を読み取ってもプリフェッチ要求は行わない（`engine/src/kernels/cpu/native_expert.cpp:246-252`, `engine/src/kernels/cpu/native_expert.cpp:741-743`, `engine/src/kernels/cpu/native_expert.cpp:866-867`）。
- `STRATA_ROW_PF_PRO` は行ループの前に先行行を要求する prologue だけを制御する。未設定または空文字では `1`。値を `atoi` した結果が `0` のとき prologue は省かれるが、正の距離があれば各行ループ内の先読み要求は残る（`engine/src/kernels/cpu/native_expert.cpp:254-260`, `engine/src/kernels/cpu/native_expert.cpp:744-747`, `engine/src/kernels/cpu/native_expert.cpp:868-870`）。
- x86 では `STRATA_ROW_PF_X86` が定義され、x86 intrinsic の `_mm_prefetch` が選ばれる。非 x86 では `__GNUC__` が定義される場合に builtin、それ以外は no-op の実装になる（`engine/include/strata/kernels/cpu/row_prefetch.hpp:15-22`, `engine/include/strata/kernels/cpu/row_prefetch.hpp:31-43`）。
- CLI 引数、サーバーモード、モデル状態によるこの値の上書きは、候補名の全参照からは確認できない。別プロセスへの明示的な転送も確認できない。

## 実行時の詳細

`row_pf_hint()` の関数内 static は最初の呼び出し時に初期化され、その後プロセス内で再読込されない。実行中に環境を変更してもキャッシュ済みの hint は変わらない。native gate/up と down の一般 dot 経路はそれぞれこの関数を呼ぶ（`engine/src/kernels/cpu/native_expert.cpp:897-914`）。

`row_prefetch_range` は指定範囲を 64 byte ごとに `row_prefetch_line` へ渡す。x86 では hint `0` が `_MM_HINT_T0`、`2` が `_MM_HINT_NTA`、その他が `_MM_HINT_T1`。非 x86 で `__GNUC__` が定義されている場合、同じ分岐が locality `3`、`0`、`2` に対応する。非 x86 かつ `__GNUC__` が未定義なら要求は no-op となる（`engine/include/strata/kernels/cpu/row_prefetch.hpp:31-49`）。

hint の読取り自体にログ、警告、終了、失敗経路はない。負値や通常外の整数も拒否されず、「その他」のヒント分岐に入る。`docs/DETAILS.md` にこの環境変数固有の挙動や測定値の記載は見当たらず、この調査では性能値を追加していない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:264-271` — hint の取得、空文字時の既定値、`atoi`、static cache。
- `engine/src/kernels/cpu/native_expert.cpp:741-747`, `engine/src/kernels/cpu/native_expert.cpp:771-773`, `engine/src/kernels/cpu/native_expert.cpp:866-870`, `engine/src/kernels/cpu/native_expert.cpp:884-886` — 対象行経路とプリフェッチ要求。
- `engine/include/strata/kernels/cpu/row_prefetch.hpp:15-22`, `engine/include/strata/kernels/cpu/row_prefetch.hpp:31-49` — OS/コンパイラ分岐、hint 対応、no-op 条件、64 byte ごとの要求。
