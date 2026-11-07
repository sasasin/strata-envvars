# `STRATA_NO_VBMI`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

x86 CPU の Q2_0 行カーネルで、VBMI の `VPMULTISHIFTQB` を使う 2-bit 展開を、VBMI を使わない代替展開へ切り替える診断用ノブです。Strata のソースコメントも、VBMI 対応 CPU 上で代替実装を実行するテスト用としています。VBMI がない CPU では、変数を設定しなくても代替実装が選ばれます。

## 値と判定

値の parse はなく、`std::getenv("STRATA_NO_VBMI") == nullptr` かどうかだけを判定します。

| 状態 | `cpu_vbmi_ok()` の VBMI 判定 |
|---|---|
| 未設定 | `cpu_isa_free()` が true なら CPUID の VBMI bit を調べ、その結果に従う |
| 空文字を含む何らかの値が設定済み | false（VBMI なしとして扱う） |

`0`、`1`、`false` などの値の違いは無視されます。空白、大文字小文字、数値形式の検査もありません。設定時に「変数値が 1 なら有効」とする意味ではなく、設定があれば VBMI 命令の利用を抑止します。根拠: `src/kernels/cpu/expert_layout.cpp:176-185`。

## 有効になる条件

この切替が実際に効くのは、x86 向け CPU カーネルがビルドされ、Q2_0 の 512-bit/VNNI 行経路で `unpack64_q2_0()` が呼ばれる場合です。Q2_0 の行経路選択は `kZmm` と `cpu_vnni_ok()` によります。`kZmm` は `STRATA_CPU_YMM` が未設定のとき true で、`STRATA_CPU_YMM` が設定されると false になります。VNNI 経路が選ばれない場合は AVX2/AVX1 の Q2_0 実装に進むため、この VBMI 展開切替は使われません。根拠: `src/kernels/cpu/expert.cpp:152,193-200,378-380,465-472`。

さらに `cpu_vbmi_ok()` は `cpu_isa_free()` が true のときだけ VBMI を検査します。`STRATA_FORCE_AVX2` の先頭文字が `1` なら `cpu_isa_free()` は false となり、この時点で VBMI なし側になります。`STRATA_FORCE_ISA` の CPU ISA cap が 3 未満の場合も同様です。根拠: `src/kernels/cpu/expert_layout.cpp:26-39,75-78,178-185`。

`STRATA_NO_VBMI` は Q2_0 AVX-512 パックの実行要件を免除しません。非 native pack に対する `cpu_require_expert_support()` は別途、AVX512F/VNNI/VBMI を含む `cpu_features().usable()` を確認し、満たさない場合は stderr に診断を出して終了コード 1 で終了します。この変数は `cpu_features()` のハードウェア判定を変えません。native expert pack では Q2_0 の該当行処理に 512-bit/VNNI 経路が選ばれた場合に代替展開が使われます。根拠: `src/kernels/cpu/expert_layout.cpp:424-462`, `src/kernels/cpu/expert.cpp:465-472`。

## 実行時の詳細

`cpu_vbmi_ok()` の結果は関数内の `static const bool` に保存され、`unpack64_q2_0()` も `static const bool vbmi` として初回に保持します。したがって初回評価後にプロセス環境を変更しても、このプロセスの選択には反映されません。VBMI が使えると判定した場合は `_mm512_multishift_epi64_epi8` を用いる展開を、そうでない場合はシフト・マスク・並べ替えによる代替展開を選びます。後者は `VPMULTISHIFTQB` 命令を使わず Q2_0 の packed 2-bit codes を展開します。根拠: `src/kernels/cpu/expert_layout.cpp:176-185`, `src/kernels/cpu/expert.cpp:154-195`。

ソース内にこの変数を使った警告・ログ出力、CLI 引数との優先順位、または子プロセスへの転送処理は見つかりません。変数自体による終了・失敗経路もありません。変わるのは該当 CPU 行カーネル内で選ぶ unpack 実装です。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:176-185` — 設定有無と CPUID による VBMI 判定、static cache。
- `src/kernels/cpu/expert_layout.cpp:26-39,75-78` — ISA cap / `STRATA_FORCE_AVX2` による短絡条件。
- `src/kernels/cpu/expert_layout.cpp:424-462` — ハードウェア feature 判定と非対応 CPU の終了経路。`STRATA_NO_VBMI` はこの判定に使われない。
- `src/kernels/cpu/expert.cpp:152,154-195,213-225,378-380,465-472` — ZMM/VNNI 経路と VBMI / software unpack の選択。
- `CMakeLists.txt:2059-2075` — x86 / portable CPU kernel のビルド分岐と `expert.cpp` の AVX-512 compile options。
