# `STRATA_BENCH_QMIXED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は通常の Strata 推論設定ではなく、GPU カーネルの `fused_gr_bench` ベンチ専用である。ベンチの `cold sets` 引数が 1 より大きいとき、合成入力で `fused_gr_read_multi` を測る呼び出しに `q8_mixed` と `q8_cnt` の出力先を渡すかを切り替える。設定してもモデルの読込、通常の推論、サーバー処理を変更しない。実装は `engine/src/kernels/fused_gr_bench.cpp` の `main` にある（同ファイル 4–6, 227–266 行）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 用 `fused_gr_bench` の cold-set 節 | `with_q == false` | 値の内容を問わず設定済み（`1`, `0`, `true`, `false`, 空文字、`0anything` を含む） | なし。環境変数が未設定の場合だけ false |

`std::getenv(...) != nullptr` だけを判定し、文字列変換・比較・空白検査・数値範囲検査はしない。したがって空文字や文字列 `0` も有効扱いである。既定値は unset のとき false。CLI 引数や他の環境変数による上書き・優先順位はない（`engine/src/kernels/fused_gr_bench.cpp:244,258`）。

## 有効になる条件

- `fused_gr_bench` が CUDA または HIP の GPU engine build に含まれ、その実行ファイルを起動していること。CMake は CUDA/HIP 共通 engine の中でこのターゲットを定義する（`engine/cmake/strata_gpu_engine.cmake:7-8,1005-1007`）。
- 第 4 CLI 引数 `cold sets` が `std::atoi` で 2 以上になること。引数省略時は 0 で、この場合 cold-set 節に入らず環境変数も読まない。1 以下も同様に節を通らない（`engine/src/kernels/fused_gr_bench.cpp:57,65-68,227-244`）。
- この変数による分岐は cold-set 測定に限られる。SYCL 版 `engine/sycl/src/kernels/fused_gr_bench.cpp` には同名の読み取りがなく、そちらではこの変数は効かない（同ファイル 27–31, 115–200 行）。

## 実行時の詳細

`main` は反復回数・トークン範囲・cold-set 数を CLI から読み、通常の比較計測を行った後、`cold_sets > 1` の場合に複数組の合成重みを用意する。この節で環境変数を一度読み、設定済みなら各 token の `FusedGrArgs` に `q8_mixed` のバッファ位置と `q8_cnt` を設定する。unset なら両フィールドは初期値の null のままである。続く `fused_gr_read_multi` 呼び出しは複数の fast/通常カーネル条件で実行される。ここで渡すバッファは `mixed` の Q8_1 イメージ用で、ヘッダーもこの引数を「読み取りが書く」出力と定義している（`engine/src/kernels/fused_gr_bench.cpp:241-266`; `engine/include/strata/kernels/fused_gr.hpp:46-49,74-76`）。

値は cold-set 節に入った時点でローカル `const bool` に一度だけ読み込まれ、その節内の呼び出しに使われる。関数内 static やプロセス横断の cache はない。読み取り後に環境を変更しても同じ実行中のこの分岐には反映されず、次回起動時に再評価される。子プロセスへの転送処理はない。

カーネル側では、すべての token に `q8_mixed` があり、counter がある場合に Q8 出力要求として扱い、要求が整わなければ null に戻す経路がある。カーネル実装はこの出力先が非 null のとき mixed の計算後に Q8 tail を書く（`engine/src/kernels/cuda/fused_gr.cu:472-475,4272-4283`）。このベンチは `fused_gr_read_multi` の戻り値を保存せず、cold-set 出力は時間計測行のみで、Q8 イメージを個別に表示・比較しない（`engine/src/kernels/fused_gr_bench.cpp:258-286`）。この変数の効果はベンチでの追加出力先設定とその測定経路に限られ、通常推論の計算結果や生成 token を変える設定ではない。

## ログと測定値

この変数専用のログや警告はない。cold-set 節に入ると、通常の時間計測と同じ `COLD(%d sets) fast %d T %d | read ... | stamps median: ...` 行を stdout に出すが、行に変数の状態や Q8 出力の値は含まれない（`engine/src/kernels/fused_gr_bench.cpp:285-290`）。カーネル呼び出しで CUDA エラーが起きた場合は `fused_gr_read_multi q8: %s` 等を stderr に出して `exit(1)` する経路がある。これは変数値を検証した結果ではなく、呼び出されたカーネルのエラー処理である（`engine/src/kernels/cuda/fused_gr.cu:4286-4293`）。

## 根拠

- `engine/src/kernels/fused_gr_bench.cpp:57-68,227-290` — CLI 引数、cold-set 条件、環境読み取り、出力先設定と測定ログ。
- `engine/cmake/strata_gpu_engine.cmake:7-8,1005-1007` — CUDA/HIP 共通 GPU engine とベンチターゲット。
- `engine/sycl/src/kernels/fused_gr_bench.cpp:27-31,115-200` — SYCL 版に対象変数の読み取りがないこと。
- `engine/include/strata/kernels/fused_gr.hpp:46-49,74-76`、`engine/src/kernels/cuda/fused_gr.cu:472-475,4272-4293` — Q8_1 出力先の用途、カーネルでの判定・書き込みとエラー経路。
