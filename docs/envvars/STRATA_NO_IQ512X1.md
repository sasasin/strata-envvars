# `STRATA_NO_IQ512X1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert gate/up 計算で、条件を満たす IQ3_XXS / IQ3_S の単一 token に使う AVX-512 exact-row 最適化を無効化します。値の真偽や内容ではなく、環境変数が設定されているかだけを見ます。未設定なら通常の dispatch 条件に従って最適化候補になり、設定されていればその専用分岐を通りません（`engine/src/kernels/cpu/native_expert.cpp:601-619`）。

この分岐が使われるのは `native_gu_rows_impl` の gate/up 処理です。AVX-512 exact-row の計算結果が linked ggml-cpu の単一 token dot と一致するかを初回に合成データで照合し、一致した場合だけ gate/up の行を計算します。これは down projection や GPU の kernel を無効化する設定ではありません（`engine/src/kernels/cpu/native_expert.cpp:126-155, 605-618, 898-910`）。

## 値と判定

`std::getenv("STRATA_NO_IQ512X1") == nullptr` の判定です。文字列変換・数値 parse・範囲検査はありません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全 build / platform | 専用経路を抑止しない | なし（値にかかわらず専用経路を抑止） | 空文字、`0`、`1`、`true`、`false`、任意の文字列はすべて同じく抑止 |

ここで「有効」は変数による無効化がないことを指し、専用 kernel の実行には次節の条件も必要です。設定を空文字にしても unset とは異なります（`engine/src/kernels/cpu/native_expert.cpp:605`）。

## 有効になる条件

- 呼び出しが CPU native expert の gate/up 処理であること。対象コードは x86 build では `native_expert.cpp` と AVX-512 実装を組み込みます（`engine/cmake/backends/cpu.cmake:303-317`）。
- `cpu_vnni_ok()` が true で、`STRATA_NO_IQ512` が未設定であること。これが `avx512` 条件です（`engine/src/kernels/cpu/native_expert.cpp:562-568`）。
- `iq512_gather_on()` が true であること。この設定は `STRATA_IQ_GATHER` が空でない場合 `atoi` の結果が 0 以外なら true、0 なら false です。未設定または空文字の場合は `cpu_gather_fast()` の CPU 判定に従います。この gather 設定は `iq_avx512.cpp` の namespace-scope `const` 初期化時に一度評価されます（`engine/src/kernels/cpu/iq_avx512.cpp:38-45, 668`; `engine/src/kernels/cpu/expert_layout.cpp:319-340`）。非 x86 側の stub は常に false を返します（`engine/src/kernels/cpu/portable.cpp:113-122`）。
- token 数が 1 で、`native_gu_mt_min(f.gu_type)` より小さいこと。既定の `STRATA_IQ_MT_MIN` は 2 なので単一 token が候補ですが、同変数が `1` なら単一 token は先行する multi-token kernel のルールに残り、この exact one-token 分岐は通りません。`STRATA_IQ_MT_MIN` は `atoi` で読み、未設定時は 2 です（`engine/src/kernels/cpu/native_expert.cpp:540-556, 604-607`）。
- gate/up の形式が type 18（IQ3_XXS）または 21（IQ3_S）で、`f.tail_off == 0` であること。IQ2_S は `iq512x_supported` の対象でも、この gate/up 分岐の対象ではありません（`engine/src/kernels/cpu/native_expert.cpp:606-607`; `engine/src/kernels/cpu/iq_avx512.cpp:670-672`）。
- `x512_one_ok` の初回照合で linked ggml-cpu と bitwise 一致すること。型の dot と Q8_K の float quantizer が利用可能で、AVX-512 VPOPCNTDQ を備える場合に照合します（`engine/src/kernels/cpu/native_expert.cpp:126-155`; `engine/src/kernels/cpu/iq_avx512.cpp:653-672`）。

いずれかの条件を満たさない場合、この環境変数による専用経路の抑止とは別の dispatch に進みます。通常の multi-token kernel や ggml-cpu dot など、どの経路になるかは token 数、CPU、build、型の条件で決まります（`engine/src/kernels/cpu/native_expert.cpp:654-710`）。

## 実行時の詳細

変数は `native_gu_rows_impl` 内の関数ローカル `static const bool x512_one` 初期化時に読み取られます。これは `NativeArithmetic` の template specialization ごとに初回だけ評価され、以降その specialization では値が cache されます。プロセス実行中に環境値を変更しても、その specialization の判定は変わりません（`engine/src/kernels/cpu/native_expert.cpp:559-561, 605`）。

条件を満たした場合、初回は型ごとに mutex と map で照合結果を保持します。照合は n=2560、24 行の合成ブロックで AVX-512 exact-row の出力と ggml dot の出力を `memcmp` 比較します。一致時は要求された gate と up の行を 64 行ずつ計算して SwiGLU を適用し、関数から戻ります（`engine/src/kernels/cpu/native_expert.cpp:126-155, 606-618`）。不一致または照合に必要な機能がない場合は `x512_one_ok` が false となり、この専用経路を使わず後続 dispatch に進みます。

## ログと測定値

この変数自体を読み取ったことや抑止されたことを示すログはありません。照合が失敗した場合は stderr に `strata: the 512-bit exact one-token rows of type %d differ from this ggml-cpu's dot: not used` を出し、この専用経路を使いません。照合が必要な機能を欠く場合は、このメッセージを出す比較自体が行われません（`engine/src/kernels/cpu/native_expert.cpp:132-153`）。

ソースコメントには Xeon 8468 で ggml の dot に対して 1.3x との測定記述がありますが、同ファイルの記述は機種と測定対象のみで、OS・build 設定・モデル条件・回数を示していません。そのため、この文書では一般的な速度効果として扱いません（`engine/src/kernels/cpu/native_expert.cpp:601-604`）。

## 根拠

- 全直接参照は `engine/src/kernels/cpu/native_expert.cpp:605` の環境読み取り 1 か所です。リポジトリ全体の名前検索では `terminal/data/settings-register.json:26993` にも名前がありますが、これは設定レジストリであり実行時読み取りではありません。
- `STRATA_NO_IQ512X1` の説明は `docs/DETAILS.md` および Strata の Markdown 文書では見つかりませんでした。挙動の根拠は上記ソースです。
