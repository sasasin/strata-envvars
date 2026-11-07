# `STRATA_IQ4XS512_MIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CPU の native expert 経路で、VNNI 対応 CPU が IQ4_XS の gate/up 行に AVX-512 参照カーネルを使い始める最小 token 数を指定します。既定値は `1` です。IQ4_XS gate/up は通常の AVX-512 対応形式一覧に含まれません。

この変数は GPU カーネルやサーバー設定を直接制御しません。CPU expert pool が native gate/up 行を実行し、対象 expert の形式が IQ4_XS のときだけ関係します。pool は `native_gu_rows` / `native_gu_rows_invariant` を呼び、両方とも同じ dispatch 実装を使います（`src/kernels/cpu/pool.cpp:1231-1237`、`src/kernels/cpu/native_expert.cpp:707-720`）。

## 値と判定

値は `std::atoi` で整数に変換され、未設定の場合だけ `1` になります。空文字や整数として読めない文字列は `atoi` の結果 `0` となり、負数もそのまま閾値になります。変換は整数の先頭部分を読むため、先頭空白や符号は受け付け、数字の後ろに続く文字列は判定に使われません。

| 環境変数の値 | 閾値 | 条件への影響 |
|---|---:|---|
| 未設定 | 1 | `nt >= 1` のとき閾値条件を満たす |
| `3` | 3 | `nt` が 3 以上で満たす |
| `0`、空文字、`abc` | 0 | 非負の `nt` なら満たす |
| `-2` | -2 | 通常の非負 `nt` なら満たす |
| `3tail` | 3 | 数字の先頭部分 `3` に変換される |

この閾値を満たすだけではカーネル選択は確定しません。別の有効条件も必要です（下記）。閾値値の上限 clamp や無効値警告はありません。`atoi` で `int` の範囲外となる入力の結果は保証できません（`src/kernels/cpu/native_expert.cpp:519-520`）。

## 有効になる条件

次の条件をすべて満たすと専用カーネルに進みます。

- CPU が `cpu_vnni_ok()` を満たし、`STRATA_NO_IQ512` が未設定である。
- `STRATA_NO_IQ4XS512` が未設定である。これら2変数は `getenv(...) == nullptr` で判定されるため、空文字を含め何か設定されていれば無効化します。
- gate/up の型 ID が `23`（IQ4_XS）、token 数 `nt` が閾値以上、`NativeFmt::tail_off` が `0` である。
- linked ggml-cpu との初回照合 `iq512_reference_ok(23)` が成功する。

`cpu_vnni_ok()` は x86 の AVX-512F/DQ/BW/VL と VNNI、OS の AVX-512 状態保存を確認します。VNNI はあるが `cpu_avx512_ok()` が false となる下位 tier では、`STRATA_VNNI_TIER` の先頭文字が `1` の場合に限って許可されます。非 x86 では CPU feature helper が false を返します（`src/kernels/cpu/expert_layout.cpp:42-51,160-203`）。このため、`STRATA_IQ4XS512_MIN` の値だけで非対応 CPU 上のカーネルは有効になりません。

VNNI 対応 CPU で専用分岐の条件を満たさない場合は、IQ4_XS が通常の AVX-512/AVX2 分岐の対象外となるため ggml-cpu の gate/up `vec_dot` にフォールバックします。VNNI 非対応で AVX2 が使える CPU では、別途 `STRATA_IQ_MT_MIN` の閾値（未設定時 `2`）を満たせば IQ4_XS 用 AVX2 kernel を使い、それ以外は ggml-cpu に進みます（`src/kernels/cpu/native_expert.cpp:435-452,247-253,567-591,620-630`）。

## 実行時の詳細

閾値は `native_gu_rows_impl` 内の `static const int` で初回評価時に読み、以後その関数 specialization 内に保持します。通常経路と `WindowInvariant` 経路はテンプレートの別 specialization なので、それぞれが最初に呼ばれた時点で独立に cache します。読み取り後に環境を変更しても、その specialization の値は変わりません（`src/kernels/cpu/native_expert.cpp:455-456,519,707-720`）。

有効時は `iq512_reference_gu_rows` が IQ4_XS の gate 行と up 行を計算します。実装は gate の SiLU 値と up 値を掛けて `ff[t][r]` に格納します（`src/kernels/cpu/native_expert.cpp:520-521`、`src/kernels/cpu/iq_avx512.cpp:630-638`）。この helper の初回検査では linked ggml-cpu に IQ4_XS の dot と Q8_K 活性量子化があることを確認し、合成データで 24 行の結果を比較します。差があれば stderr に `strata: the window-invariant 512-bit rows of type 23 differ from this ggml-cpu's dot: its dot runs per token instead` と出し、その結果を cache して専用カーネルを使わず ggml-cpu に進みます。型情報不足の場合は false となりますが、この検査関数内からは警告を出しません。これは処理継続する fallback であり、この環境変数による終了やエラー経路はありません（`src/kernels/cpu/native_expert.cpp:79-114,620-630`）。

## 根拠

- 候補名の実読み取りと閾値判定: `src/kernels/cpu/native_expert.cpp:517-521`。
- CPU feature gate、`STRATA_NO_IQ512` / `STRATA_NO_IQ4XS512` の設定有無判定: `src/kernels/cpu/native_expert.cpp:463,518-520`。
- ggml-cpu 整合性の照合・警告・結果 cache: `src/kernels/cpu/native_expert.cpp:79-114`。
- IQ4_XS が一般 AVX-512/AVX2 dispatch から外れる条件と ggml dot fallback: `src/kernels/cpu/native_expert.cpp:247-253,567-591,620-630`。
- VNNI 非対応 CPU での `STRATA_IQ_MT_MIN` を使う AVX2 dispatch: `src/kernels/cpu/native_expert.cpp:435-452,567-591`。
- CPU pool から native gate/up dispatch への呼び出し: `src/kernels/cpu/pool.cpp:1231-1237`。
- AVX-512 kernel のビルド対象とコンパイル条件: `CMakeLists.txt:2182-2214`。

`docs/DETAILS.md` にはこの変数の説明や測定値が見つかりませんでした。この文書ではソースの分岐と fallback のみを記載しています。
