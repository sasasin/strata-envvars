# `STRATA_NO_AVXVNNI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

x86 CPU の AVX2 expert row dispatch で、AVX-VNNI 形式を選ばないための抑止スイッチです。Strata の `cpu_avxvnni_ok()` が環境変数を数値変換し、非 0 なら `false` を返します。その結果、Q2_0 と i-quant 系の一部 AVX2 row 処理は VNNI 実装でなく AVX2 の通常実装を通ります。環境変数自体が生成 token やモデル設定を変更する処理はありません。`expert_layout.cpp` の関数内 `static` 判定を通じ、Q2_0 と i-quant の dispatch がこの可否を使います（`engine/src/kernels/cpu/expert_layout.cpp:361-374`、`engine/src/kernels/cpu/q2_avx2.cpp:155-164`、`engine/src/kernels/cpu/iq_avx2.cpp:384,491-498`）。

## 値と判定

読み取りは x86 用 `cpu_avxvnni_ok()` の初回評価時に `std::getenv` で行い、設定されていて `std::atoi(v) != 0` の場合に AVX-VNNI を無効にします。文字列全体の妥当性検査はありません。`atoi` が先頭の空白と符号付き 10 進数を変換し、数字の後ろの文字を無視するため、`1`、`-1`、`1junk`、` 1` は抑止し、`0`、`0junk`、`true`、`false`、空文字、未設定はこの条件では抑止しません。数値として変換できない文字列は 0 として扱われます。範囲外の数値文字列については `atoi` の規則に委ねられます（Strata 側に追加の検証や clamp はありません）。

| 条件 | unset | 抑止する値の例 | 抑止しない値の例 |
| --- | --- | --- | --- |
| x86/x64 の通常 build で、AVX-VNNI kernel が build に含まれ、CPU 条件も満たす場合 | 抑止しない | `1`, `-1`, `1junk`, ` 1` | 空文字, `0`, `0junk`, `true`, `false`, `junk` |
| 非 x86 build | 関数の stub が常に `false` を返すため変数を読み取らない | 該当なし | 該当なし |
| AVX-VNNI kernel が build に含まれない場合 | VNNI kernel は選択されない | 実効上の差なし | 実効上の差なし |

根拠: `engine/src/kernels/cpu/expert_layout.cpp:42-51,361-374`。`std::atoi` の結果が 0 かどうかだけを使い、空文字専用の扱いや文字列比較はありません。

## 有効になる条件

- 値が `atoi` で非 0 になり、x86/x64 の probe 実装が使われること。
- 変数が 0 または未設定で AVX-VNNI を使うには、`STRATA_ISA_FLOOR` build が空（通常 build）、`cpu_isa_cap() >= 3`、AVX2 と OS の YMM 状態対応、および CPUID leaf 7 subleaf 1 の AVX-VNNI bit が必要です（`engine/src/kernels/cpu/expert_layout.cpp:361-371,206-238,286-294`）。
- AVX-VNNI row kernel がコンパイラで利用可能として build されている必要があります。CPU backend と SYCL の CMake は intrinsic の compile check 結果から `STRATA_AVXVNNI=1` または `0` を設定し、Q2_0 と i-quant の各ソースへ渡します。非対応コンパイラの build では VNNI row のコピー自体がありません（`engine/cmake/backends/cpu.cmake:271-298,350-358`、`engine/sycl/CMakeLists.txt:180-200,228-248`、`engine/src/kernels/cpu/iq_avx2.cpp:37-45`、`engine/src/kernels/cpu/q2_avx2.cpp:18-25`）。
- `STRATA_FORCE_ISA=avx2`, `avx`, `sse`, `sse4.2`, `none` は ISA cap を 3 未満にし、AVX-VNNI 判定を通さないため、この変数を unset/0 にしても VNNI は選ばれません。`STRATA_FORCE_ISA` に他の非空文字列を指定した場合は warning を出して cap 3 として扱います。`STRATA_FORCE_AVX2` は AVX-512 側などで使う probe 制限ですが、`cpu_avxvnni_ok()` はその判定を呼ばないため、この AVX-VNNI probe を直接は抑止しません（`engine/src/kernels/cpu/expert_layout.cpp:26-39,75-78,361-374`）。
- これらの row dispatch 以外、GPU backend のカーネルや AVX-512 probe を本変数が制御する読み取り箇所は見つかりません。モデル形式や server/CLI モードによる別の判定も、この変数の読み取り箇所にはありません。

## 実行時の詳細

`cpu_avxvnni_ok()` は関数ローカル `static const bool` を初回呼び出し時に初期化します。その初期化で環境変数を読み、結果をプロセス内で cache するため、初回評価後にプロセス環境を変更しても再評価されません（`engine/src/kernels/cpu/expert_layout.cpp:361-374`）。

Q2_0 の AVX2 row dispatcher は `STRATA_AVXVNNI && cpu_avxvnni_ok()` を渡し、true なら VNNI rows、false なら通常 AVX2 rows を呼びます（`engine/src/kernels/cpu/q2_avx2.cpp:155-164,167-178`）。i-quant dispatcher は `vnni_on()` から同じ判定を使って VNNI variant を含めるか決め、含まれない場合に通常 rows を選びます（`engine/src/kernels/cpu/iq_avx2.cpp:370-384,491-498,500-525,540-552`）。したがってこの変数は AVX-VNNI がある CPU の一部 CPU row 計算経路を AVX2 実装へ戻すもので、AVX-VNNI 対応条件を満たさない場合や VNNI kernel が build されていない場合には追加の効果はありません。

## ログと測定値

本番の読み取り・dispatch 判定から、この変数の値や切替理由を出力するログ、警告、終了経路は確認できません。別の診断実行ファイル `iq_avx2_parity` は環境値を文字列のまま標準出力に表示します（未設定は `-`）。その表示は値の診断であり、そこでは値を数値判定していません（`engine/src/kernels/cpu/iq_avx2_parity.cpp:562-566`）。

`docs/DETAILS.md` は `STRATA_NO_AVXVNNI=1` を AVX-VNNI row forms を止める診断用設定と記載しています。速度や一致性の数値は本調査では測定しておらず、同資料の数値を現行環境で再確認した結果としては扱いません（`docs/DETAILS.md:1273`）。

## 根拠

- `engine/src/kernels/cpu/expert_layout.cpp:361-374` — 環境値の読み取り、数値判定、cache、および AVX2/CPUID 条件。
- `engine/src/kernels/cpu/expert_layout.cpp:42-51` — 非 x86 stub。
- `engine/src/kernels/cpu/q2_avx2.cpp:155-178` — Q2_0 row dispatch。
- `engine/src/kernels/cpu/iq_avx2.cpp:370-384,491-525,540-552` — i-quant の VNNI variant と row dispatch。
- `engine/cmake/backends/cpu.cmake:271-298,350-358`、`engine/sycl/CMakeLists.txt:180-200,228-248` — build 時の AVX-VNNI intrinsic 判定と各 kernel への macro 設定。
- `engine/src/kernels/cpu/iq_avx2_parity.cpp:562-566` — 診断プログラムによる値の表示。
- `docs/DETAILS.md:1273`、`docs/SETTINGS.md:188` — Strata 資料上の位置づけと CPU 設定一覧。
