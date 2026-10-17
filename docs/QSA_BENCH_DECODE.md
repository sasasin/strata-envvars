# `QSA_BENCH_DECODE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`qsa_select_bench` を通常の scorer 比較モードから decode block-score の計測モードへ切り替えます。Strata 本体やサーバーの動作を制御する設定ではありません。この変数の参照は `src/kernels/qsa_select_bench.cpp` のみにあり、同ユーティリティは CUDA/HIP のビルドでテストまたは parity 用オプションが有効な場合に追加されます。

## 値と判定

環境変数の値は parse せず、`std::getenv("QSA_BENCH_DECODE")` が null かどうかだけを判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | 通常モード。warp scorer と fast scorer、top-k の比較・計測へ進む |
| 設定あり | decode モード。block score の計測と hash 出力を行い、通常モードの比較には進まない |

空文字、`0`、`false` を含め、何らかの値が設定されていれば decode モードです。値の大文字小文字や数値としての妥当性は関係ありません。

## 有効になる条件

この変数を読むのは `qsa_select_bench` だけです。CMake では HIP の場合 `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が有効なとき、CUDA の場合 `STRATA_BUILD_TESTS` が有効なときに同実行ファイルを定義します。Strata の通常の実行ファイルやサーバーから、この変数を読む参照は確認できません。

decode 分岐は `qsa_block_scores(..., active_blocks=-1)` を呼びます。この呼び出しが multi scorer を使う条件は、`STRATA_SCORES_MULTI` が有効で、クエリ数が最大 8 以下であることです。ベンチはコマンドラインの第2引数でクエリ数を指定でき、既定値は 256 です。その条件を満たさない場合、この環境変数による decode 分岐自体は実行されますが、multi kernel の経路にはなりません。

## 実行時の詳細

ベンチは合成データを作り GPU に転送した後、この変数を一度確認します。設定されていると、`qsa_block_scores` を一度ウォームアップ実行し、CUDA event で `reps` 回の実行時間を計測します。結果をホストへコピーし、各 query の有効 block score から hash を計算して、`decode scores ctx ...` の行に context、query 数、平均時間、pooled keys の帯域換算値、hash を出力して終了コード 0 で戻ります。この分岐では通常モードの scorer 精度比較、選択差の集計、top-k 計測は実行しません。

値はベンチの実行中に分岐へ到達した時点で読みます。プロセス起動時の static cache ではありませんが、この分岐は `main` 内の一度だけ評価されます。子プロセスへの転送処理はありません。なお、実行時に GPU API 呼び出しが失敗した場合は既存の `ck()` によりエラーを stderr に出して終了コード 2 になります。

関連資料 `docs/AMD_HIP.md` は `qsa_select_bench` を scorer 比較の文脈で挙げていますが、`QSA_BENCH_DECODE` の値判定や decode モードの測定結果は記載していません。この文書では独自の性能値を主張しません。

## 根拠

- `src/kernels/qsa_select_bench.cpp:2-7` — 合成 GPU ベンチであること、コマンドライン引数と既定値。
- `src/kernels/qsa_select_bench.cpp:35-41` — 引数の読み取りと context/query/reps/capacity の設定。
- `src/kernels/qsa_select_bench.cpp:73-95` — 環境変数の有無判定、decode scorer 呼び出し、計測、hash 出力、早期 return。
- `include/strata/kernels/qsa_select.hpp:37-40` — `active_blocks` 引数の意味。
- `src/kernels/cuda/qsa_select.cu:975,1547-1549,1709-1744` — query 上限、`STRATA_SCORES_MULTI` の既定値・変換、および `active_blocks <= 0` の multi scorer 分岐条件。
- `CMakeLists.txt:470-490` — CUDA/HIP のビルド条件と CTest 登録。
