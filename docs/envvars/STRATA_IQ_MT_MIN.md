# `STRATA_IQ_MT_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 行計算で、IQ 系の multi-token カーネルを使い始める token 数のしきい値を指定する。通常の未設定値は 2 で、`1` にすると 1 token のグループにも対象カーネルを使う。IQ 行の丸め方が変わり、コメントでは draft/verify window 内のグループ数によって greedy 出力が変わり得る点と、この設定でグループ幅に依存しない計算にする意図が説明されている。設定値は結果の token を固定する一般的な決定性スイッチではなく、対象 CPU カーネルの選択しきい値である（`engine/src/kernels/cpu/native_expert.cpp:540-556,654-708,828-839`）。

この読み取りは `STRATA_NATIVE_EXPERTS` が有効な CPU native expert 実装にある。モデル pack に `native_experts.txt` があり native experts を使う場合にその実装へ進む。native experts を含む pack は `STRATA_NATIVE_EXPERTS` 無効の engine では拒否される。非 x86 では x86 ISA 判定がすべて false になり、ここで選択される AVX 系 IQ カーネルは実行されない（`engine/src/kernels/cpu/expert_layout.cpp:42-50,501-515`; `engine/CMakeLists.txt:178,725-736`; `engine/cmake/backends/cpu.cmake:303-317`）。

## 値と判定

両方の本番読み取り箇所は `std::getenv` の値を `std::atoi` に渡し、未設定なら `2` を使う。関数内 `static` に保存される。設定値の文字列全体や真偽語を検証せず、`atoi` が読む先頭の十進数部分でしきい値を決める（`engine/src/kernels/cpu/native_expert.cpp:545-546,798`）。

`docs/SETTINGS.md` の一覧はこの変数の型を `on / off` と記すが、実装は真偽値比較ではなく整数しきい値として扱う。`docs/DETAILS.md` は CPU の native IQ 行計算と出力差について説明しており、現行コードの役割と整合する（`docs/SETTINGS.md:410`; `docs/DETAILS.md:388-396`; 実装: `engine/src/kernels/cpu/native_expert.cpp:540-556,654-708`）。

| 条件 | unset | 有効になる値（例） | その他の値の扱い |
|---|---|---|---|
| gate/up の IQ 行 | `mt_min=2` | `1`、`0`、`-1`、`1abc` はそれぞれしきい値 1、0、-1、1 | 空文字、`true`、`false`、`0anything` は `atoi` が 0 を返す。先頭空白や符号の後の数字は変換対象。数値部分の後ろは無視される。 |
| down の IQ4_NL 行 | `mt_min=2` | 同じ変換規則 | 同じ変換規則 |

各経路は `nt >= mt_min` で multi-token 行カーネルの適用可否を判定するため、値 `1` は 1 token から、`0` や負値は正の `nt` ならすべてのグループ幅から条件を満たす。値が 2 以上なら小さいグループは対象外になる。無効な文字列を拒否する処理、clamp、警告はない。down 側は IQ4_NL (`d_type == 20`) に限り、さらに AVX2 と `STRATA_NO_IQ4NL` 未設定が必要（`engine/src/kernels/cpu/native_expert.cpp:654-708,797-799,828-839`）。

## 有効になる条件

- CPU native expert 計算が使われること。pack に native experts がなければこの行計算経路を使わず、native experts 対応なしで該当 pack を読む場合は拒否される（`engine/src/kernels/cpu/expert_layout.cpp:501-515`）。
- gate/up 側では、multi-token カーネルが実装されている IQ 型であること。対象判定は IQ 型・CPU ISA によって AVX-512、AVX2、AVX1 のカーネルを選ぶ。各 ISA は CPU 機能判定を通った場合だけ呼ばれ、対象外の型や ISA では通常の dot 経路へ進む（`engine/src/kernels/cpu/native_expert.cpp:568-584,681-708`; `engine/src/kernels/cpu/expert_layout.cpp:280-290`）。
- down 側でこの変数がしきい値として使われるのは IQ4_NL (`d_type == 20`)。CPU が AVX2 対応で、`STRATA_NO_IQ4NL` が未設定（空文字を含め、設定されていない）であり、`nt >= mt_min` のときに限る（`engine/src/kernels/cpu/native_expert.cpp:795-799,828-839`）。
- `STRATA_IQ3S_MT1` はこの変数が未設定の場合だけ別の gate/up しきい値を 1 にできる。`STRATA_IQ_MT_MIN` が空文字を含め設定済みなら、この別ルールは無効になり、`atoi` の結果が使われる。別ルール自体も CPU が AVX2 対応、`STRATA_NO_IQ256` 未設定、AVX-512 非対応、IQ256 gather が有効かつ fast と判定される場合の IQ3_S gate/up に限る（`engine/src/kernels/cpu/native_expert.cpp:545-556`）。
- `STRATA_NO_IQ512`、`STRATA_NO_IQ256`、`STRATA_NO_IQ128` などの ISA 別無効化設定は、対応するカーネル経路を選べるかに影響する。しきい値設定自体はこれらを上書きしない（`engine/src/kernels/cpu/native_expert.cpp:568-584,681-708`）。
- `nt == 1` かつ `nt < mt_min` のときは、通常のしきい値判定に先立ち、条件を満たせば `STRATA_CPU_IQ_ALL_EXACT1` による AVX2 exact-one 行、または `STRATA_NO_IQ512X1` が未設定の場合の AVX-512 exact-one 行を選べる。しきい値を 1 以下にするとこの singleton 分岐条件を満たさない（`engine/src/kernels/cpu/native_expert.cpp:588-618`）。

## 実行時の詳細

gate/up のしきい値は `native_gu_mt_min()` が初めて呼ばれたときに読み、`env` と `mt_min` を static 保存する。さらに `STRATA_IQ3S_MT1` の適用条件も static 保存される。down のしきい値は native down 行実装が初めて評価されたときに static 保存される。したがって同一プロセスで環境を後から変えても、読み取り済みのしきい値には反映されない（`engine/src/kernels/cpu/native_expert.cpp:540-556,792-799`）。

gate/up は `nt >= mt_min` のとき、対応する AVX カーネルを選び得る。`NativeArithmetic::WindowInvariant` 経路は通常 `mt_min > 1` なら singleton IQ 行を維持するが、しきい値を 1 以下にするとこの singleton 条件は外れ、対応する multi-token カーネル選択に進み得る。down の IQ4_NL はしきい値を満たす場合に AVX2 カーネルを使い、`WindowInvariant` でも `mt_min <= 1` ならそのカーネルを選ぶ（`engine/src/kernels/cpu/native_expert.cpp:654-708,828-839,896-915`）。pool は通常経路と window-invariant 経路を分けてこれらの行関数へ渡す（`engine/src/kernels/cpu/pool.cpp:1274-1309,1414-1453`）。

この変数による専用ログ、エラー、終了経路は実装にない。変換できない文字列も拒否せず、`atoi` の値 0 としてしきい値比較に使う。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:540-556` — gate/up の読み取り、既定値、`STRATA_IQ3S_MT1` との条件。
- `engine/src/kernels/cpu/native_expert.cpp:654-708` — gate/up のしきい値比較、型・ISA ごとの選択、window-invariant 条件。
- `engine/src/kernels/cpu/native_expert.cpp:792-839` — down 側の読み取り、IQ4_NL に対する適用条件。
- `engine/src/kernels/cpu/expert_layout.cpp:42-50,501-515` — CPU ISA stub と native expert pack の読み込み条件。
- `engine/src/kernels/cpu/pool.cpp:1274-1309,1414-1453` — pool から通常・window-invariant 行関数への呼び出し。
- `engine/cmake/backends/cpu.cmake:303-317`; `engine/CMakeLists.txt:178,725-736` — CPU native expert 実装のビルド登録条件。
