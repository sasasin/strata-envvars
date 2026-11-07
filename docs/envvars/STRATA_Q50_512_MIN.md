# `STRATA_Q50_512_MIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Q5_0 形式の native expert down projection を CPU で計算するとき、複数 token をまとめて処理する 512-bit VNNI カーネルを使い始める最小 token 数を指定します。既定値は 2 です。閾値を下げると 1 token の処理にもこのカーネルを選べます。

対象は native expert の CPU row 計算です。`ExpertPool` は native expert の down phase で `native_down_rows()` または `native_down_rows_invariant()` を呼び、どちらも同じ閾値判定を持つ実装へ進みます。通常の GPU expert kernel や、GGUF の一般的な Q5_0 dot 全体を切り替える設定ではありません。

## 値と判定

値は `std::atoi()` で整数に変換します。文字列全体の検証、範囲制限、無効値の警告はありません。

| 環境変数の状態 | `q50_min` | 判定への影響 |
|---|---:|---|
| 未設定 | 2 | token 数が 2 以上のとき閾値を満たす |
| 空文字 | 0 | 正の token 数なら閾値を満たす |
| 数値文字列 | `atoi` の結果 | `nt >= q50_min` で判定 |
| 数字で始まらない文字列 | 0 | 変換失敗のエラーにはならず、正の token 数なら閾値を満たす |

`atoi` は先頭の空白と符号を許し、数字の後ろに続く文字列を検査しません。たとえば `" 3tail"` は 3、`"-1"` は -1 です。したがって 0 や負値は正の token 数に対する実質的な下限をなくし、大きい正値は `nt` がそこに達するまでカーネルを選びません。値の clamp や変換エラーのログはありません。

## 有効になる条件

閾値を満たすだけでは十分ではありません。次の条件がすべて必要です。

- 呼び出しが native expert の CPU down-row 経路である。
- down projection の type が `6`（ggml の `GGML_TYPE_Q5_0`）である。
- `cpu_vnni_ok()` が true を返す。
- `STRATA_NO_Q50_512` が未設定である。空文字を含め、設定されていれば値に関係なく無効化する。
- native format に tail data がなく（`f.tail_off == 0`）、初回の一致性確認が成功する。
- token 数 `nt` が `q50_min` 以上である。

`cpu_vnni_ok()` は CPU と OS の ISA 対応を確認し、ISA cap が有効で `STRATA_FORCE_AVX2=1` によって抑止されていないことを要求します。VNNI 対応でも通常の AVX-512 条件を満たさない tier では、別変数 `STRATA_VNNI_TIER` の先頭文字が `1` の場合に限り許可されます。`STRATA_Q50_512_MIN` 自体は CPU の機能を有効化しません。

## 実行時の詳細

閾値は `native_down_rows_impl` 内の function-local `static const int` として `std::getenv()` から一度読み取られます。値はそのテンプレート特殊化内で cache されるため、読み取り後にプロセス環境を変更しても再評価されません。`STRATA_NO_Q50_512` の判定も static cache です。

条件を満たす場合、Strata は `q50_512_down_rows()` に down weights、Q8_0 activation、token 数、row 範囲を渡して CPU VNNI kernel を実行し、その呼び出しから戻ります。条件を満たさない場合は後続の通常 down-row 処理に進み、ggml-cpu の `vec_dot` を token ごとに呼びます。

カーネルを初めて選択するとき `q50_512_ok()` が一度だけ合成データで ggml-cpu の結果と比較します。96 と 640 の幅、3 token で結果が一致しない場合、stderr に `strata: the 512-bit Q5_0 down rows differ from this ggml-cpu's dot: not used` を出し、呼び出し側は通常の dot 処理へ進みます。一致した場合、この確認によるログはありません。閾値の値自体を記録するログや、閾値の parse 失敗による終了・警告経路はありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:655-661` — Q5_0 (`d_type == 6`) の判定、`STRATA_NO_Q50_512`、閾値の既定値と `atoi`、tail 条件、カーネル呼び出し。
- `src/kernels/cpu/native_expert.cpp:196-231` — 初回の VNNI / ggml type trait 確認、合成データでの比較と不一致時ログ。
- `src/kernels/cpu/native_expert.cpp:712-724` — 通常・window-invariant down-row wrapper の双方が同じ実装へ委譲。
- `src/kernels/cpu/native_expert.cpp:694-701` — 専用カーネルを選ばない場合の ggml `vec_dot` fallback。
- `src/kernels/cpu/pool.cpp:1238-1250,1365-1382` — native expert pool の down phase からの呼び出し。
- `src/kernels/cpu/iq_avx512.cpp:795-832,854-856` — Q5_0 block と Q8_0 activation を使う 512-bit multi-token down kernel。
- `src/kernels/cpu/expert_layout.cpp:188-203` — VNNI 判定と `STRATA_VNNI_TIER` による例外。
- `src/kernels/cpu/expert_layout.cpp:75-77,80-110` — ISA cap / `STRATA_FORCE_AVX2` と CPU/OS の AVX-512 条件。
