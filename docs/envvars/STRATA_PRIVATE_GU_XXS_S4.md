# `STRATA_PRIVATE_GU_XXS_S4`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数名は、SYCL 実装の `xxs_s4_enabled()` に設定有無の判定コードとして現れます。ただし、調査対象 checkout ではこの関数の呼び出し箇所がなく、現在の grouped expert dispatch も関数を呼ばずに IQ2_XXS S4 kernel を選びます。そのため、この checkout の実行経路では環境変数を読まず、kernel の選択や計算に影響しません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5479-5481,7388-7392`）。

## 値と判定

唯一の読み取り式は `xxs_s4_enabled()` 内にあります。仮に同関数が呼ばれた場合、`std::getenv()` が非 null で、値の先頭文字が `'1'` のときだけ true です。文字列全体の比較や数値変換はしません。したがって `1`、`10`、`1anything` は true、未設定、空文字、`0`、`01`、`true`、先頭に空白がある ` 1` は false です。ただし、この関数に呼び出し元がないため、これらは helper のコード上の判定規則であり、現行経路で実際に評価される規則ではありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5479-5481`）。

| 条件 | unset | helper が呼ばれた場合に true | helper が呼ばれた場合に false |
|---|---|---|---|
| SYCL ソースの `xxs_s4_enabled()` | false | 先頭文字が `1`。例: `1`, `10`, `1anything` | 空文字、`0`, `01`, `true`, ` 1` など |
| 調査対象 checkout の実行経路 | 評価されない | 該当なし | 該当なし |

## 有効になる条件

- この環境変数による有効化条件は、現行コードにはありません。`xxs_s4_enabled()` は定義されていますが、候補名と関数名の全参照検索で呼び出し箇所は見つかりませんでした（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5479-5481`）。
- 現行 dispatch が `launch_gu_xxs_s4()` を選ぶ条件は別にあります。gate/up type が `16`（IQ2_XXS）、`n_embd=2560`、`n_ff=640`、`v1`・旧 kernel・split multi が無効、lane 数が 8、`grid_groups=0`、`cap_groups=cap_entries`、`p16_enabled()` と `b60_next_iq_pool()` が true であることに加え、`cap_entries` と actor/device の組み合わせが guard に合う必要があります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7392`）。
- `p16_enabled()` は `STRATA_PRIVATE_GU_XXS_PACKED` の先頭文字が `1` であること、main actor、packed weights、および Battlemage device を要求します。`b60_next_iq_pool()` は `STRATA_PRIVATE_B60_NEXT_POOL` の先頭文字が `1` の場合に true です。これらの helper の判定はそれぞれ関数内 `static` に保存されます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4625,5191`）。
- `STRATA_PRIVATE_GU_XXS_S4` が未設定でも、上記の dispatch 条件を満たせば S4 kernel は選択されます。逆に、この変数だけを設定しても dispatch 条件を満たさなければ選択されません。

## 実行時の詳細

`xxs_s4_enabled()` の本体は `static const bool` を初期化するラムダで `getenv` を呼ぶため、呼び出される設計なら初回評価結果を保持します。しかし、調査対象の全参照を確認した範囲では関数を呼ぶ箇所がなく、現在の実行では初期化・読み取り自体が起きません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5479-5481`）。

実際の dispatch は `native_expert_grouped()` 内で helper を介さず `launch_gu_xxs_s4()` を呼びます。kernel は grouped IQ2_XXS gate/up の計算結果を gate/up の出力領域へ書き込みますが、その選択判定に `STRATA_PRIVATE_GU_XXS_S4` は使われていません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5568-5591,7308-7319,7388-7392`）。この SYCL source は SYCL build の kernel source 一覧に含まれます（`sycl/CMakeLists.txt:240-253`）。

## ログと測定値

この変数または `xxs_s4_enabled()` によるログ出力はありません。`docs/DETAILS.md` を含む Strata の資料に、この変数の実行時効果や測定値の記載は見当たりません。helper が現行経路で呼ばれないため、この変数による選択ログ・警告・終了経路も確認できません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5479-5481` — 環境変数を読む唯一の helper 定義。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5568-5591` — IQ2_XXS S4 kernel の起動処理。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4625,5191` — 現行 dispatch が使う別環境変数と device / weight 条件。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7308-7319,7388-7392` — grouped expert 処理と、対象 S4 kernel の実際の選択条件。
- `sycl/CMakeLists.txt:240-253` — `iq_kernels.dp.cpp` を含む SYCL kernel source の構成。
