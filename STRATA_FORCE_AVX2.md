# `STRATA_FORCE_AVX2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

CPU の AVX-512 対応判定を強制的に false にし、Strata の CPU カーネル選択で AVX-512 カーネルを避ける開発・診断用フックです。実際の対応 CPU 命令を変更したり、AVX2 を有効化したりする設定ではありません。ソース中の直接読み取りは `cpu_avx512_ok()` と `cpu_avx512bw_ok()` の2か所です。ヘッダーコメントも、この変数を「tests」向けとして説明しています。

## 値と判定

| 値 | `cpu_avx512_ok()` / `cpu_avx512bw_ok()` での扱い |
|---|---|
| 未設定 | 環境変数による抑止なし。通常の CPU / OS 機能判定へ進む |
| 先頭文字が `1` | `false` を返す。後続文字列は見ない（例: `1`, `10`, `1abc` はすべて抑止） |
| 空文字、先頭文字が `1` 以外 | 環境変数による抑止なし。通常の CPU / OS 機能判定へ進む |

数値変換や文字列全体の比較はありません。大文字小文字、空白、残りの文字列も評価しません。この変数を無効値にしても AVX-512 が自動的に使われるわけではなく、続く CPU 機能判定が成功する必要があります。また `STRATA_FORCE_ISA` の上限が `avx2` 以下なら、`cpu_avx512_ok()` はこの変数とは別に AVX-512 を不可とします。

## 有効になる条件

- この判定を使う Strata の CPU カーネル経路で効果があります。GPU backend の種別によらず、CPU expert kernel の選択時に参照されます。
- `STRATA_FORCE_AVX2` が先頭文字 `1` の場合、AVX-512 判定が通らず、Q2_0 行列・activation quantizer は AVX2、または AVX2 非対応時の AVX1 実装へ進みます（`src/kernels/cpu/expert_layout.cpp:348-365`）。
- native expert pack の gate/up 行では、AVX-512 が使えない扱いになり、対応形式・複数 token 条件なら AVX2 kernel が選ばれます。それ以外は AVX1 または ggml-cpu の `vec_dot` にフォールバックします。down 行の AVX2 kernel は `cpu_avx2_ok()` で別途 CPU 対応も確認します（`src/kernels/cpu/native_expert.cpp:134-195,199-230`）。
- canonical Q2_0 pack の起動時必須判定 `cpu_require_expert_support()` は `cpu_features()` を直接参照し、この環境変数を見ません。そのため実 CPU が必要な機能を持つ環境では、このフラグで AVX-512 dispatch を避けても起動要件判定自体は通ります（`src/program/generate.cpp:2774-2783`, `src/kernels/cpu/expert_layout.cpp:303-345`）。
- AVX2 対応の有無はこの変数で作られません。AVX2 非対応なら、AVX2 kernel ではなく利用可能な AVX1 / ggml-cpu 経路に進みます。

## 実行時の詳細

両関数はそれぞれ `static const bool` に判定をキャッシュします。各関数がプロセス内で初めて呼ばれた時に環境を読み、その後の環境変更はその関数の結果に反映されません。関数が別々に初回評価されるため、それぞれの初回評価時点が異なる場合はその時の値が使われます。

`cpu_avx512_ok()` は通常時、CPUID と OS の保存状態を確認します。OSXSAVE があり、XCR0 が AVX-512 の状態保存に必要なビットを有効にし、CPUID leaf 7 に AVX512F/BW/VL、AVX512-VNNI、AVX512-VBMI がある場合に true です。フラグで抑止されたこと自体を知らせる専用ログはありません。native pack では起動時に AVX-512 非対応扱いとなると `strata generate: this CPU has no AVX-512: ...` を出して使用 kernel tier を表示します。

`cpu_avx512bw_ok()` にも同じ先頭文字判定がありますが、この HEAD では宣言と定義以外に呼び出し箇所が見つかりませんでした。従って本番実行への独立した効果は、呼び出される経路がない限り確認できません。

## 根拠

- `include/strata/kernels/cpu/expert_layout.hpp:44-51` — CPU 機能判定 API とコメント上の用途。
- `src/kernels/cpu/expert_layout.cpp:41-72,74-104` — 変数の読み取り、先頭文字判定、キャッシュ、AVX-512 機能判定。
- `src/kernels/cpu/expert_layout.cpp:348-365` — Q2_0 CPU kernel と activation quantizer の AVX-512 / AVX2 / AVX1 dispatch。
- `src/kernels/cpu/native_expert.cpp:134-195,199-230` — native pack の gate/up と down 行の kernel 選択・fallback。
- `src/program/generate.cpp:2774-2783`, `src/kernels/cpu/expert_layout.cpp:303-345` — 起動時の AVX-512 表示と canonical pack 要件判定。
- `docs/DETAILS.md` — CPU backend と AVX-512 kernel tiers の説明はあるが、`STRATA_FORCE_AVX2` の挙動説明は見つかりませんでした。
