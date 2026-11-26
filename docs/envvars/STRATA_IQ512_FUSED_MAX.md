# `STRATA_IQ512_FUSED_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 経路で、IQ 系 expert の gate/up 行を fused 512-bit kernel で処理する最大 token 数を指定する。値が `M >= 2` なら、適用条件を満たす expert を 2 から `M` token まで `iq512_fused_gu_rows` に渡す。それ以外は後続の通常の IQ row kernel または ggml-cpu の dot 経路へ進む。gate/up の出力を使う SwiGLU を含め、初回の検証で当該ビルドの ggml-cpu dot と bit 単位で一致しない形式は fused 経路から除外される（`engine/src/kernels/cpu/native_expert.cpp:160-202,629-652`）。

この変数は `native_gu_rows_impl` でのみ読み取られる。CPU expert pool の gate/up 行処理から `native_gu_rows` または `native_gu_rows_invariant` を通じて呼ばれる（`engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`、`engine/src/kernels/cpu/native_expert.cpp:559-560,898-910`）。CUDA 等の GPU kernel がこの設定を読む実装は見つからなかった。

## 値と判定

`std::getenv` の結果が null なら `0`、null でなければ文字列を `std::atoi` に渡す。空文字、数値に変換できない文字列は `0` となる。`atoi` は先頭の空白と符号を許し、整数の後ろに続く文字を検証しないため、例として `" 2x"` は `2`、`"0anything"`、`"true"` は `0` として扱われる。小数点以下も整数変換後に無視される（例: `"2.9"` は `2`）。コードに値の clamp や無効値の警告はない。`atoi` で `int` に表現できない値の結果は移植可能な値として定義されていない。

| 条件 | unset | fused 上限として有効になる値 | fused 経路に入らない値の例 |
|---|---:|---|---|
| CPU gate/up dispatcher | `0` | 変換結果が `2` 以上。2 なら 2 token、3 なら 2–3 token、一般に `nt <= M` | 空文字、`0`、`1`、負数、`true`、`0anything`。`2.9` は上限 2 として扱う |

判定式は `fused_max >= 2 && nt >= 2 && nt <= fused_max`。そのため、整数として有効な値でも、上限未満または上限超過の token group ではこの fused kernel を使わない（`engine/src/kernels/cpu/native_expert.cpp:633-634`）。

## 有効になる条件

- Strata の CPU native expert gate/up row 経路に入ること。CPU backend 以外の GPU dispatch からこの `getenv` 読み取りへの経路はない（`engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`）。
- `cpu_vnni_ok()` が true であること。通常は AVX-512F/DQ/BW/VL と VNNI が必要であり、AVX-512 CPU と認識されない VNNI tier は `STRATA_VNNI_TIER` の先頭文字が `1` の場合に限り許可される（`engine/src/kernels/cpu/native_expert.cpp:567-568`、`engine/src/kernels/cpu/expert_layout.cpp:188-202`）。
- `STRATA_NO_IQ512` が未設定であること。空文字を含め何らかの値が設定されていると `avx512` が false になり、この fused 分岐は使われない（`engine/src/kernels/cpu/native_expert.cpp:568,634`）。
- この判定は `STRATA_IQ_MT_MIN` を読む後続の通常 multi-token 分岐より前にある。そのため `STRATA_IQ_MT_MIN` の設定値は fused 経路の 2..M token 判定を止めず、fused 条件を満たさない場合の後続 dispatch に適用される。CLI 引数による上書きはこの関数にない（`engine/src/kernels/cpu/native_expert.cpp:629-654`）。
- group の token 数が 2 以上かつ設定上限以下で、native format の `tail_off == 0`、`gu_type` が 1–31 であること（`engine/src/kernels/cpu/native_expert.cpp:634`）。
- `STRATA_IQ512_FUSED_TYPES` の形式 bitset に `gu_type` が含まれ、`iq512f_supported(gu_type)` と `iq512f_ok(gu_type)` が true であること。型リストの既定値は `18,21,22`（IQ3_XXS、IQ3_S、IQ2_S）。この別変数が未設定または空文字なら既定値を使う。非空ならカンマ区切り各要素を `atoi` し、1–31 の値だけを bitset に追加する。値の全体検証や警告はなく、`iq512f_ok` の初回検証に失敗した型は使われない（`engine/src/kernels/cpu/native_expert.cpp:635-652`）。
- x86 以外の build では portable stub が `iq512f_supported` を false にするため、この fused kernel は適用されない（`engine/src/kernels/cpu/portable.cpp:127-133`）。x86 build では AVX-512 kernel source が CPU native expert build に加わる（`engine/cmake/backends/cpu.cmake:303-317`）。

## 実行時の詳細

`fused_max` は `native_gu_rows_impl` 内の関数ローカル `static const int` で、各 `NativeArithmetic` template instance が最初にこのコードを通ったときに一度だけ読み込まれる。従って設定値は起動時ではなく初回使用時に確定し、その instance の実行中に環境を変えても反映されない（`engine/src/kernels/cpu/native_expert.cpp:559-560,629-634,898-910`）。

条件を満たすと `iq512_fused_gu_rows` が gate/up の両方の行を token group で処理し、gate に sigmoid を適用して up と乗算した結果を `ff` に書く（`engine/src/kernels/cpu/native_expert.cpp:649-651`、kernel 本体 `engine/src/kernels/cpu/iq_avx512.cpp:761-780`）。その型の初回検証では合成入力 3 token・24 行について fused 結果と ggml-cpu の個別 dot + SwiGLU を比較する。bit 単位で不一致の場合は stderr に理由を出し、その型を cache して以後 fused kernel を使わない（`engine/src/kernels/cpu/native_expert.cpp:161-201`）。

設定上限や適用条件を満たさない場合は後続の dispatch が判定し、条件に応じて通常の IQ512 multi-token rows、IQ256 rows、または ggml-cpu dot などへ進む。上限未満・超過だけを理由に終了やエラーにはならない（`engine/src/kernels/cpu/native_expert.cpp:654-710,769-789`）。

## ログと測定値

この変数の値が設定されたこと、fused 経路が有効になったことを知らせるログはない。`iq512f_ok` の比較に失敗した場合のみ、実装は stderr に `strata: the fused 512-bit gate/up rows of type %d differ from this ggml-cpu's dot: not used` を出す（`engine/src/kernels/cpu/native_expert.cpp:197-199`）。

実装コメントには、既定の row kernel に対して Zen 4 で 2–3 token 時に 1.27–1.34 倍、1 token 時は遅くなる測定と記されている。ただし、この文書から条件を特定できるのは Zen 4、2–3 token と比較対象が既定 row kernel であることまでで、測定の詳細条件はコメントに記録されていないため、他条件へ一般化しない（`engine/src/kernels/cpu/native_expert.cpp:629-632`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:629-652` — 値の読み取り、上限判定、型設定、fused kernel 呼び出し。
- `engine/src/kernels/cpu/native_expert.cpp:160-202` — fused kernel の当該 ggml-cpu build に対する初回検証と不一致ログ。
- `engine/src/kernels/cpu/expert_layout.cpp:188-202` — VNNI tier の CPU 判定条件。
- `engine/src/kernels/cpu/portable.cpp:127-133` — portable build の fused kernel 非対応 stub。
- `engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429` — CPU expert pool からの gate/up 行呼び出し。
- `engine/src/kernels/cpu/iq_avx512.cpp:761-780` — fused gate/up 行 kernel の演算。
- `engine/cmake/backends/cpu.cmake:303-317` — CPU native expert と x86 kernel source の build 登録。
