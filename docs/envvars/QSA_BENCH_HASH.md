# `QSA_BENCH_HASH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA 選択ベンチ `qsa_select_bench` の通常経路で、fast scorer が計算した block score のハッシュを追加表示します。Strata の推論エンジンからは参照されず、推論挙動や scorer の選択を切り替える変数ではありません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ハッシュを計算・表示しない |
| 設定あり（空文字を含む） | ハッシュを計算し、`fast scores hash %016llx` を stdout に表示する |

値の内容は parse せず、`std::getenv("QSA_BENCH_HASH")` が null かどうかだけを判定します。そのため `0`、`false`、空文字を含め、設定されていれば有効です。判定は `qsa_select_bench` の `main()` 内で通常経路がスコア計算を終えた後に行われます。

## 有効になる条件

- 対象は CUDA または HIP 向けにビルドされた `qsa_select_bench`。CMake ではそれぞれ CUDA のテストビルド、または HIP のテスト／prompt-attention parity ビルドに登録されています。
- `QSA_BENCH_DECODE` が設定されていると、ベンチは decode 用の block score を計測して早期 return します。この経路では `QSA_BENCH_HASH` の判定に到達せず、ハッシュ行は出ません。
- 設定すると、ベンチが別途参照する `STRATA_SELECT_SIMT` などの scorer 設定値は変わりません。ソースコメントはハッシュを `STRATA_SELECT_SIMT=1` と `=2` の scorer 出力比較に使う想定を示しています。
- SYCL 側の `sycl/src/kernels/qsa_select_bench.cpp` にはこの変数の参照がありません。

## 実行時の詳細

ベンチは合成入力で warp scorer と fast scorer を実行し、fast scorer の結果 `sc_new` を CPU 側の配列 `b` にコピーします。環境変数が設定されている場合、各 query について `steps` の block 数に従い `j < nbid` の score を走査します。各 `float` のビット列を `uint32_t` として読み、初期値 `1469598103934665603` から `(hash XOR bits) * 1099511628211` の順に累積します。得た値を16桁の16進数で stdout に出します。

この処理はベンチ出力への診断値追加です。スコアや選択結果を書き換えず、環境変数の設定有無でベンチの合否判定も変更しません。値は一度の `getenv` 判定で使われ、キャッシュ用 static はありません。

## 根拠

- `src/kernels/qsa_select_bench.cpp:35-42` — 引数既定値とベンチ入力の初期化。
- `src/kernels/qsa_select_bench.cpp:74-95` — `QSA_BENCH_DECODE` 経路と早期 return。
- `src/kernels/qsa_select_bench.cpp:96-119` — 通常経路の scorer 実行、CPU 配列へのコピー、環境変数判定。
- `src/kernels/qsa_select_bench.cpp:119-130` — score の対象範囲、hash 計算、stdout 出力。
- `src/kernels/qsa_select_bench.cpp:187-212` — 合否判定が accuracy gate と top-k の一致数に基づくこと。
- `CMakeLists.txt:501-521` — CUDA/HIP の `qsa_select_bench` 登録条件。
- `sycl/src/kernels/qsa_select_bench.cpp` — SYCL 版には `QSA_BENCH_HASH` の参照なし。
- `docs/AMD_HIP.md:707` — QSA selection bench の記述はあるが、`QSA_BENCH_HASH` 自体の説明はない。
