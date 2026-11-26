# `STRATA_NO_IQ512`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 経路にある IQ gate/up 行の AVX-512 カーネルを選ばないための切替です。`native_gu_rows_impl` の `avx512` 判定で設定有無を確認し、設定されていれば AVX-512 カーネル群を候補から外します。対応形式・CPU 条件を満たす場合は AVX2 の IQ カーネルへ進み、そこも使えない場合は後段の dot 経路に進みます。`native_down_rows_impl` の判定や Q2_0 専用行処理にはこの変数の参照がありません（`engine/src/kernels/cpu/native_expert.cpp:559-576,684-710,792-815`; `engine/src/kernels/cpu/pool.cpp:1274-1296`）。

## 値と判定

文字列の内容は parse せず、`std::getenv(...) != nullptr` かどうかだけを `static const bool` に保存します（`engine/src/kernels/cpu/native_expert.cpp:568`）。したがって未設定なら AVX-512 候補を許可し、空文字を含む設定済み値は値にかかわらず候補を抑止します。

| 条件 | unset | AVX-512 を抑止する値 |
|---|---|---|
| `cpu_vnni_ok()` が true の CPU | AVX-512 IQ 行を候補にする | 空文字、`0`、`1`、`true`、任意の文字列すべて |
| `cpu_vnni_ok()` が false の CPU | AVX-512 IQ 行は候補にならない | 同左。変数による追加の変化なし |

大文字小文字、空白、数値としての妥当性、境界値は検査されません。CLI 引数や別変数によるこの判定値の上書きはありません。別の `STRATA_NO_IQ256` は後段の AVX2 カーネルを抑止し、`STRATA_NO_IQ128` は AVX1 カーネルを抑止します（同ファイル `:568-584,696-710`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` を有効にして native expert ソースがビルドされ、native pack の CPU expert 処理が呼ばれること。CMake の既定オプションは ON で、ON のとき native expert ソースを CPU kernel library に追加します（`engine/CMakeLists.txt:178,725-735`; `engine/cmake/backends/cpu.cmake:303-312,370`）。OFF の場合は native pack の読み込みを拒否する実装です（`engine/src/kernels/cpu/expert_layout.cpp:488-495,501-515`）。
- 対象は `native_gu_rows` / `native_gu_rows_invariant` を通る gate/up 行であること。通常の pool 処理は mode 5 でこれらを呼びます（`engine/src/kernels/cpu/pool.cpp:1274-1296,1414-1429`）。
- AVX-512 IQ 実装の候補は `cpu_vnni_ok()` が true のときに限られます。この probe は OS の AVX-512 状態保存を含む ISA 判定と F/DQ/BW/VL/VNNI の各 feature を確認します。VBMI のない tier では `STRATA_VNNI_TIER` の先頭文字が `1` であることも必要です（`engine/src/kernels/cpu/expert_layout.cpp:148-174,188-203`）。その CPU で `cpu_vnni_ok()` が false なら、この変数を設定しても AVX-512 IQ 行の選択に変化はありません。
- AVX-512 を抑止した後、AVX2 実装へ進むには `cpu_avx2_ok()` が true、`STRATA_NO_IQ256` が未設定、対象型を `iq256_supported` が扱うことが必要です。それ以外では後段の dot 経路が使われます。AVX1 経路は AVX2 がなく `cpu_avx1_ok()` が true、`STRATA_NO_IQ128` が未設定、対象型を `iq128_supported` が扱い、token 数が `native_gu_mt_min` 以上の場合に限られます（`engine/src/kernels/cpu/native_expert.cpp:576,684-710`）。
- 1 token 専用の `iq512x_rows` 経路と、IQ3_XXS / IQ3_S / IQ2_S の fused AVX-512 gate/up 経路も `avx512` を条件にするため、この変数で候補から外れます（同ファイル `:601-618,629-652`）。

## 実行時の詳細

設定は `native_gu_rows_impl` の関数内 static 初期化で評価されます。`Default` と `WindowInvariant` の template specialization は別々の static 判定を持ち、それぞれ最初に呼ばれたときの値を保存します。その後同じプロセス内で環境を変更しても、その specialization の判定には反映されません（`engine/src/kernels/cpu/native_expert.cpp:559-568,898-910`）。

`avx512` が false のとき、複数 token の IQ 行は AVX-512 を選ばず、`avx2` と型の対応条件を満たせば AVX2 行カーネルを選びます。対象形式・token 数・ISA 条件などを満たすカーネルがなければ、処理は後段の per-row `traits(...).dot` に進みます（同ファイル `:684-710,734-789`）。Q2_0 の pool 専用 gate/up 分岐は `native_gu_rows_impl` より前に処理されるため、この判定を通りません（`engine/src/kernels/cpu/pool.cpp:1274-1296`）。

## ログと測定値

この変数自体を理由とするログ、警告、終了処理はありません。AVX-512 経路を抑止した際も、この分岐からはログを出さず、選択可能な下位経路へ進みます（`engine/src/kernels/cpu/native_expert.cpp:568,684-710`）。資料 `docs/SETTINGS.md:425` は CPU の on/off 設定として一覧に載せていますが、`docs/DETAILS.md` にこの変数の測定値や追加条件は見当たりません。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:559-576` — 環境変数の唯一の実読み取り、static cache、AVX-512 / AVX2 / AVX1 判定。
- `engine/src/kernels/cpu/native_expert.cpp:601-710` — AVX-512 専用経路と下位 ISA / dot への dispatch。
- `engine/src/kernels/cpu/native_expert.cpp:734-789,792-815,898-915` — dot fallback、down 行との切り分け、関数の公開 wrapper。
- `engine/src/kernels/cpu/expert_layout.cpp:148-174,188-203,488-515` — CPU feature probe と native expert build / load 条件。
- `engine/src/kernels/cpu/pool.cpp:1274-1296,1414-1429` — pool からの gate/up 行呼び出し。
- `engine/cmake/backends/cpu.cmake:303-312,370`; `engine/CMakeLists.txt:178,725-735` — native expert ソースと build option。
