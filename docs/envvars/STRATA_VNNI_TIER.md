# `STRATA_VNNI_TIER`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

AVX-512 VNNI は使えるが VBMI がない x86 CPU で、Strata の一部 CPU expert kernel を VNNI tier に上げる opt-in です。対象の判定関数 `cpu_vnni_ok()` は、CPU の ISA probe が AVX-512F/DQ/BW/VL/VNNI を確認した後、VBMI を含む通常の `cpu_avx512_ok()` が false のときにこの環境変数を読みます。VBMI も使える CPU では環境変数に関係なく `cpu_vnni_ok()` は true です。非 x86 の実装は常に false を返します（`src/kernels/cpu/expert_layout.cpp:42-52,188-203`）。

この tier は native expert の一部 i-quant、Q2_0 row、Q5_0 down-row、activation quantization の AVX-512/VNNI 経路を選べるようにします。対応する経路には AVX2 側と異なる丸め結果になるものがあります。ソースコメントは VBMI なしの CPU で i-quant の 512-bit rows と Q2_0 rows の結果が異なると説明しています（`src/kernels/cpu/expert_layout.cpp:196-201`）。

## 値と判定

値を数値や真偽値として parse せず、`getenv()` の結果と先頭文字だけを判定します。

| 値 | VBMI なしで VNNI 要件を満たす CPU における判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済み pointer はあるが、先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| その他 | 無効。`0`, `true`, ` 1` など |

大文字小文字、後続文字、数値としての妥当性は調べません。無効値に対する警告や fallback 専用ログはありません。判定は `e != nullptr && e[0] == '1'` です（`src/kernels/cpu/expert_layout.cpp:200-202`）。

## 有効になる条件

- x86/x86-64 向け実装であること。非 x86 の stub は変数を読まず false を返します（`src/kernels/cpu/expert_layout.cpp:42-52`）。
- OS が AVX-512 の状態を保存でき、CPU が AVX-512F/DQ/BW/VL/VNNI を備えること。ISA probe は OSXSAVE/XCR0 を確認し、`cpu_vnni_ok()` は各 CPUID bit を検査します（`src/kernels/cpu/expert_layout.cpp:148-174,188-195`）。
- VBMI がないこと。このときに限り `STRATA_VNNI_TIER` が判定に使われます。VBMI がある CPU は通常どおり有効で、変数によって無効化されません（`src/kernels/cpu/expert_layout.cpp:176-184,196-201`）。
- `STRATA_FORCE_AVX2=1` または `STRATA_FORCE_ISA` による ISA cap がないこと。共通の `cpu_isa_free()` が先に false を返すと、VNNI probe とこの環境変数の判定へ進みません（`src/kernels/cpu/expert_layout.cpp:26-39,75-78,188-190`）。
- 実際にその kernel が使われる形式・設定であること。たとえば native expert の i-quant 512-bit 経路には `STRATA_NO_IQ512` が未設定であることが必要です。Q5_0 down-row には `STRATA_NO_Q50_512` が未設定であることも必要です（`src/kernels/cpu/native_expert.cpp:459-471,570-590,655-660`）。Q2_0 512-bit row 経路には `STRATA_CPU_YMM` が未設定であることも必要です（`src/kernels/cpu/expert.cpp:152,378-380`）。

この設定は canonical Q2_0 pack の CPU 対応要件を置き換えません。`generate` は native pack でない場合に `cpu_features().usable()` を別途確認し、満たさなければ `cpu_require_expert_support()` が診断を出して終了します。要件は AVX-512 kernel に必要な機能（VBMI を含む）です（`src/program/generate.cpp:4781-4802`, `src/kernels/cpu/expert_layout.cpp:413-420,451-462`）。

## 実行時の詳細

`cpu_vnni_ok()` の戻り値は関数内の `static const bool` に保存されます。環境変数は最初の評価時に一度だけ読み取られ、その後プロセス内で環境を変更しても再評価されません。評価前に設定されている値が使われます（`src/kernels/cpu/expert_layout.cpp:188-203`）。この関数は CPU dispatch から呼ばれます。native expert では gate/up の i-quant が VNNI tier を用いて AVX-512 rows を選択し（`src/kernels/cpu/native_expert.cpp:463,570-590`）、Q5_0 down-row も条件を満たせば VNNI tier の kernel を選びます（同:657-660）。Q2_0 rows と activation quantization は `cpu_vnni_ok()` により AVX-512 経路と AVX2/AVX1 fallback を切り替えます（`src/kernels/cpu/expert.cpp:378-380,465-485,678`）。

`generate` は native pack で VNNI tier が無効の場合、CPU expert kernel の tier を stderr に表示します。VNNI tier が有効ならこの条件付きログは出ません。ここに環境変数の不正値を示す警告はありません（`src/program/generate.cpp:4802-4808`）。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:42-52,75-78,148-174,176-203` — 非 x86 stub、ISA cap、CPU/OS 機能判定、変数の読み取りとキャッシュ。
- `src/kernels/cpu/expert.cpp:152,378-380,465-485,678` — Q2_0 row と activation quantization の dispatch。
- `src/kernels/cpu/native_expert.cpp:459-471,570-590,655-660` — native expert の i-quant と Q5_0 down-row の dispatch、および関連する別環境変数。
- `src/program/generate.cpp:4781-4808` — canonical Q2_0 pack の機能要件と native pack の起動時 tier 表示。
- `include/strata/kernels/cpu/expert_layout.hpp:44-56` — AVX-512 と VNNI tier の API 上の機能境界。
