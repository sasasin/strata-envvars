# `STRATA_PF_P1A`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP の gfx1151 で、対応する native MoE expert 層の prompt 処理を `moe_p1a.cu` の FP16 行列コア kernel に切り替える要求スイッチです。対象の基本ペアは Q4_K gate/up と Q5_1 down です。`STRATA_PF_P1A_L2` も厳密に `1` の場合は、Q5_K gate/up と Q8_0 down を含む追加ペアも候補になります。対象層では gate/up の中間 `H` と down 出力を FP16 で扱います。値を有効にしても、対応層・prompt 経路・各バッファ条件を満たさない呼び出しは従来の kernel を使います（`src/prefill/moe_fused_iq.cu:3056-3074, 3131-3143`; `src/prefill/moe_p1a.cu:508-528`）。

このスイッチ自体が既定で注入されるのは Windows の統合 gfx1151 です。ほかの OS や GPU ではユーザーが明示的に設定できますが、実装は HIP と gfx1151 以外では要求を受け付けません（`src/core/arch_defaults.cpp:169-215`; `include/strata/prefill/moe_fused_iq.hpp:49-57`; `src/prefill/moe_fused_iq.cu:3065-3074`）。

## 値と判定

HIP build では `p1a_wanted()` が `std::getenv` の値を関数内 `static const bool` に一度だけ保存します。未設定でなく、かつ文字列がちょうど1文字の `1` で、`dev_info().g1151` が真の場合だけ有効です。空文字や `01`、`1 `、`1anything` は無効です。数値変換、大文字小文字変換、空白除去はしません。CUDA 等の非 HIP build では常に false です（`src/prefill/moe_fused_iq.cu:3065-3074`）。

| 条件（build / 実行環境） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP、gfx1151 | 通常は OFF。Windows の統合 gfx1151 では起動時に未設定なら `1` を注入 | `1` のみ | `0`、空文字、`true`、`01`、`1x` |
| HIP、gfx1151 以外 | OFF（Windows の gfx1151 用既定値も注入されない） | 判定上は `1` でも `dev_info().g1151` が偽なので OFF | `0`、空文字、`true`、`01`、`1x` |
| CUDA / 非 HIP build | OFF | なし | すべて（関数が常に false） |

この変数を直接設定する CLI 引数は見つかりませんでした。値の優先順位は、起動前に与えた環境値（空文字を含む）が最優先で、未設定の場合だけ対象環境の既定値が補われます。アーキテクチャ既定値の適用時は、対象の環境変数が設定済みなら値を検査せず保持します。そのため Windows gfx1151 でも `STRATA_PF_P1A=0` や空文字は自動の `1` に置き換わりません。`STRATA_GFX1151_DEFAULTS=0` は gfx1151 のアーキテクチャ既定値の表を止めますが、統合 GPU 用の別表は止めません。統合 GPU 用の表は `STRATA_IGPU_DEFAULTS=0` または `STRATA_IGPU_PROMPT_SET=0` で無効になり、その場合は自動注入されません。既定値は `setenv(..., 0)` / `_putenv_s` により未設定時だけ設定されます（`src/core/arch_defaults.cpp:63-65, 123-137, 187-213, 218-223, 302-311`）。

## 有効になる条件

`STRATA_PF_P1A=1` は要求を記録するだけで、実際に P1A kernel を使うには次の条件をすべて満たす必要があります。

- HIP でコンパイルされ、実行 GPU が gfx1151 であること。非 HIP build は要求を無効化します（`src/prefill/moe_fused_iq.cu:3065-3074`）。
- prompt の層が `fused_nat` 経路に入ること。コード上これは MMQ（または対象層の fused-only 指定）を使い、`stream_all` で、peer 経路でなく、native expert layout があり、折り畳み層なら許可された trellis pair 条件を満たし、`native_supported()` がその型ペアを受け付ける場合です。`STRATA_PF_FUSED=0` は fused kernels を無効にします（`src/prefill/moe_fused_iq.cu:2891-2918, 3015-3025`; `src/prefill/prefill.cpp:5430-5441`）。
- P1A 対応型ペアであること。基本は Q4_K / Q5_1。`STRATA_PF_P1A_L2=1` のときに限り、実装上は Q4_K または Q5_K / Q5_1 または Q8_0 の組み合わせも `takes()` に含まれます（`src/prefill/moe_p1a.cu:508-511`）。
- 層入力の FP16 行が渡されること。prompt 側は `had_gu` がない場合だけ `m.mixed_h` を `p1a_input()` に渡し、`had_gu` がある場合は null を渡すため、後者では P1A launch 条件を満たしません（`src/prefill/prefill.cpp:5492-5494`; `src/prefill/moe_fused_iq.cu:3084-3090`）。
- `want_dm_f16()` が有効であること。prompt 側では `STRATA_PF_DM16` が `1` で始まる値であり、CPU share がなく、peer でなく、`m.shared` と `m.bo` のアドレスがともに16-byte整列の場合に要求されます。`STRATA_PF_DM16` が未設定なら P1A は要求されても実行されません（`src/prefill/prefill.cpp:931-935, 5540-5542`）。
- H の FP16 行を格納できるサイズがあること。必要量を超える場合や `tiles > 65535` の場合はこの呼び出しでは P1A を使わず、従来 kernel に進みます（`src/prefill/prefill.cpp:2232-2249, 2260-2267`; `src/prefill/moe_fused_iq.cu:3134-3143`）。

Windows の統合 gfx1151 では `igpu_default_env()` が `STRATA_PF_P1A=1` と `STRATA_PF_FUSED=1`、`STRATA_PF_DM16=1` を同じ既定値セットに含めます。この統合 GPU 用の既定値は `STRATA_IGPU_DEFAULTS=0` または `STRATA_IGPU_PROMPT_SET=0` で止められます。Linux gfx1151 では P1A 自体は既定注入されません（`src/core/arch_defaults.cpp:123-137, 169-215`）。

## 実行時の詳細

起動時、`generate.cpp` が GPU 構成を調べた後 `apply_arch_defaults()` を呼びます。Windows の統合 gfx1151 では、その場で未設定の P1A を `1` にします（`src/program/generate.cpp:4085-4107`; `src/core/arch_defaults.cpp:169-215, 302-311, 358-364`）。`p1a_wanted()` は呼び出し後に値を static cache するので、プロセス中に環境値を変えても判定は更新されません（`src/prefill/moe_fused_iq.cu:3065-3074`）。

buffer 計画時、native expert layout に P1A 対応ペアが一つでもあると、fused prompt buffer の H を FP16 行の必要量まで拡張します。実際に層を処理するときは入力ポインタ、DM16 要求、GPU、型ペア、tile 数、H 容量を再確認します。条件が揃えば P1A の gate/up と down kernel を起動し、`g_dm16_used` と `g_p1a_used` を立てて通常経路を抜けます。条件が不足すればそのまま既存 fused kernel の処理を続けます（`src/prefill/prefill.cpp:2232-2249, 2260-2267, 5492-5554`; `src/prefill/moe_fused_iq.cu:3131-3143`）。

P1A kernel の down 出力は FP16 で、値は ±65504 に飽和されます。prompt 側は DM16 が実際に使われたかに基づき後段の combine 経路を選びます（`include/strata/prefill/moe_fused_iq.hpp:45-57`; `src/prefill/moe_p1a.hpp:19-26`; `src/prefill/prefill.cpp:5550-5555`）。

## ログと測定値

少なくとも一つの層で P1A kernel が実際に使われた場合、最初の fused prompt chunk の最終層の処理時に stderr へ次の形式で一度だけ出ます。ペア名と層数は実行時の pack 内容に応じます。対応層がない場合や P1A が実行されない場合、この行は出ません（`src/prefill/prefill.cpp:2195-2230, 5567-5571`）。

```text
strata: prompt experts P1A (STRATA_PF_P1A=1): gate/up + down on the P1A kernels in <N> of <total> layers (<pairs>); today's kernels in <M> (<pairs>); <U> not on the fused path in this chunk
```

Windows 統合 gfx1151 で既定スイッチ群が注入された場合は、起動時の stderr に `strata: integrated GPU (gfx1151): the matrix-core prompt set is on ...` という行が出て、設定済みスイッチ名一覧に `PF_P1A` が含まれます。明示設定で既定値が注入されなかった場合は、この既定値セットへの追加を示す行には含まれません（`src/core/arch_defaults.cpp:190-213, 358-373`）。

ソースコメントには Windows gfx1151 の UD-Q4_K_XL、5組の交互測定で prompt が 4K / 8K / 32K それぞれ x1.046 / x1.043 / x1.043、decode は不変と記録されています。同コメントは別 job の24 prompt/サイズで FP16 truth への KL を4K / 8Kで on 0.0112 / 0.0116、off 0.0179 / 0.0118 と記載しています。これはソースコメント上の限定条件つき記録で、この調査で再測定した値ではありません（`src/core/arch_defaults.cpp:208-212`）。

## 根拠

- 読み取り・厳密な値判定・HIP / gfx1151 条件・static cache: `src/prefill/moe_fused_iq.cu:3065-3074`
- Windows gfx1151 の既定値と値保持: `src/core/arch_defaults.cpp:169-215, 218-223, 302-311`
- 起動時の既定値適用位置: `src/program/generate.cpp:4085-4107`
- fused native 経路の条件: `src/prefill/prefill.cpp:5430-5441`
- 型ペア、バッファ確保、呼び出し条件、実行ログ: `src/prefill/moe_p1a.cu:508-528`; `src/prefill/prefill.cpp:2195-2230, 2232-2249, 2260-2267, 5492-5555, 5567-5571`; `src/prefill/moe_fused_iq.cu:3084-3096, 3131-3143`
