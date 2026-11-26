# `STRATA_NO_IQ4XS512`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert pool が IQ4_XS（型 23）の gate/up 行を処理するとき、AVX-512 VNNI 用の Strata 512-bit 行実装を選ばず、CPU quant trait の dot にフォールバックさせるための無効化スイッチです。既定の `STRATA_OWN_CPU_QUANT=ON` build では Strata quant layer、OFF では ggml-cpu の type trait が dot を提供します。値の内容ではなく環境変数の設定有無を見ます。IQ4_XS 以外の形式や CUDA/HIP のカーネルを切り替える参照はありません。分岐は `native_gu_rows_impl` にあります。(`engine/src/kernels/cpu/native_expert.cpp:559-560,620-627`; `engine/include/strata/kernels/cpu/pool_quant.hpp:1-5,32-43,78-89`; CPU pool からの呼び出し: `engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`)

## 値と判定

`std::getenv(...) == nullptr` のときだけスイッチが OFF と判定され、AVX-512 行実装の候補になります。空文字列を含め、環境変数が存在すれば値を読まずに候補を無効にします。したがって `0`、`1`、`false`、大文字表記、空白付き文字列、その他どの文字列も同じ扱いで、文字列比較・数値変換・大文字小文字の検査はありません。(`engine/src/kernels/cpu/native_expert.cpp:620-625`)

| 条件 | unset | 設定時に無効化される値 | 実装候補が残る値 |
|---|---|---|---|
| 全て | AVX-512 条件などを満たせば使用可能 | 空文字、`0`、`1`、`false`、その他すべて（設定あり） | 該当なし。環境変数が設定されていない場合だけ候補 |

## 有効になる条件

- 無効化スイッチが未設定であることに加え、`cpu_vnni_ok()` が true である必要があります。これは CPU と OS が AVX-512 状態を扱え、AVX-512F/DQ/BW/VL と VNNI の条件を満たすかを調べます。非 x86 ではこの判定は false です。AVX-512 VNNI 判定の追加条件に `STRATA_VNNI_TIER` が関係する CPU 経路もあります。(`engine/src/kernels/cpu/native_expert.cpp:568,623`; `engine/src/kernels/cpu/expert_layout.cpp:42-51,188-203`)
- 対象 expert の gate/up 型が `23`（IQ4_XS）、`nt >= STRATA_IQ4XS512_MIN`、`f.tail_off == 0` である必要があります。`STRATA_IQ4XS512_MIN` は未設定なら `1`、設定時は `atoi` で変換されます。空文字や数値で始まらない文字列は `0` となり、負値も範囲制限されないため、正の `nt` なら閾値条件を満たします。数値に続く文字は `atoi` の変換後に無視されます。(`engine/src/kernels/cpu/native_expert.cpp:624-625`)
- 閾値等を満たしても、起動後最初の IQ4_XS 判定で実装結果がこの build の `traits(23).dot` と一致する必要があります。一致しなければ候補は使われず、後段の `traits(23).dot` に進みます。検証は `traits(23)` の dot と Q8_K 変換が利用可能なときに実行されます。(`engine/src/kernels/cpu/native_expert.cpp:87-120,625-627`; trait の実装元: `engine/include/strata/kernels/cpu/pool_quant.hpp:32-43,78-89`)
- CPU が AVX-512 VNNI 条件を満たさない場合、この変数による 512-bit 分岐は元から候補外です。IQ4_XS の AVX2 行実装は `nt >= native_gu_mt_min(...)` かつ AVX-512 CPU ではない場合に別途選択されるため、この変数では無効になりません。AVX-512 CPU 上でこの変数が設定されるか、512-bit 分岐の他条件が満たされない場合、型23は AVX-512/AVX2 の IQ 行分岐を通らず CPU quant trait の dot に進みます。(`engine/src/kernels/cpu/native_expert.cpp:654,681-709,734-788`)
- この分岐は native CPU expert pool の gate/up 行処理に限られます。通常の dense 層や、CUDA/HIP など別 backend の処理をこの変数が変える根拠は見つかりません。(`engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`; `engine/src/kernels/cpu/native_expert.cpp:620-627`)

## 実行時の詳細

`native_gu_rows_impl` 内の `static const bool` として判定を保存します。`native_gu_rows`（Default）と `native_gu_rows_invariant`（WindowInvariant）は同じテンプレート関数の別インスタンスを呼ぶため、それぞれ初回呼び出し時に判定を初期化します。同じ実行中に環境値を変更しても、初期化済みのインスタンスには反映されません。(`engine/src/kernels/cpu/native_expert.cpp:559-560,623,896-910`; `engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429`)

スイッチが未設定で型・閾値・tail 条件を満たすと、Strata は 24 行・2560 要素の合成データで AVX-512 行計算と `traits(23).dot` の結果を比較し、その型の結果を mutex 保護された map に保存します。成功した場合は `iq512_reference_gu_rows` が gate/up 行を計算し、SwiGLU を適用して戻ります。失敗時は後続の per-token `traits(23).dot` に進みます。環境変数を設定した場合は、この 512-bit 分岐とその検証をスキップし、該当 CPU/型の後続処理が build に応じて Strata quant layer または ggml-cpu の dot を使います。(`engine/src/kernels/cpu/native_expert.cpp:87-121,620-627,734-788`; `engine/include/strata/kernels/cpu/pool_quant.hpp:1-5,32-43,78-89`; `engine/src/kernels/cpu/iq_avx512.cpp:630-639`)

## ログと測定値

比較を実行して結果が不一致の場合は stderr に次の文字列を出し、型ごとの判定を保存します。成功時と、`STRATA_NO_IQ4XS512` が設定されていて照合分岐自体を通らない場合、この照合ログは出ません。(`engine/src/kernels/cpu/native_expert.cpp:87-121,623-627`)

このログ文字列は `ggml-cpu's dot` と表現していますが、実際の比較先は build の `traits(23).dot` です。`STRATA_OWN_CPU_QUANT=ON` では Strata quant layer が比較先です。(`engine/include/strata/kernels/cpu/pool_quant.hpp:1-5,32-43,78-89`)

```text
strata: the window-invariant 512-bit rows of type %d differ from this ggml-cpu's dot: its dot runs per token instead
```

この変数の性能測定値は、参照した Strata ソース資料にはありません。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:559-560,620-627` — 変数の読み取り、型・閾値・tail 条件、選択する処理。
- `engine/src/kernels/cpu/native_expert.cpp:87-121` — quant trait との合成データ照合、結果 cache、失敗時のログ。
- `engine/src/kernels/cpu/native_expert.cpp:654-709,734-788` — 他の IQ 経路と quant trait dot へのフォールバック。
- `engine/src/kernels/cpu/native_expert.cpp:896-910`、`engine/src/kernels/cpu/pool.cpp:1290-1296,1423-1429` — Default / WindowInvariant の呼び出し経路。
- `engine/src/kernels/cpu/expert_layout.cpp:42-51,188-203` — 対応 CPU の ISA/VNNI 条件。
- `engine/src/kernels/cpu/iq_avx512.cpp:630-639` — 型23を含む参照行実装。
