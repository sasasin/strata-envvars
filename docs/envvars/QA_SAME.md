# `QA_SAME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`QA_SAME` は QSA prompt attention の合成データ検証プログラム `qsa_prompt_attn_parity` が使う選択セル列を差し替え、複数 query 間のセル重複パターンを変える診断用スイッチである。Strata の通常の engine やサーバーが読む設定ではない。読み取り箇所は CUDA/HIP 共用ソースと SYCL 版の同名パリティプログラムだけで、どちらも生成した `ids` を GPU 計算へ渡す前に書き換える（`engine/src/kernels/qsa_prompt_attn_parity.cpp:128-150`、`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:179-201`）。

この実行ファイルは合成 pool と query を使い、旧 attention、検証対象 kernel、FP64 参照との誤差や所要時間を比較する。値により変わるのは入力として使うセル ID であり、モデルの推論設定ではない（`engine/src/kernels/qsa_prompt_attn_parity.cpp:43-58, 95-127, 199-219`）。

## 値と判定

各 `run()` 呼び出しで `std::getenv("QA_SAME")` を確認し、設定されていれば `std::atoi` で整数に変換する。文字列全体の妥当性検査はなく、`atoi` が読む先頭の十進整数部分で判定される。先頭空白と符号は整数変換で扱われ、後続文字は無視される。数字として読める部分がない文字列は `0` になる。範囲外整数の `atoi` 結果は規格上保証されない（`engine/src/kernels/qsa_prompt_attn_parity.cpp:130-132`、`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:181-183`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・別扱いになる値 |
|---|---|---|---|
| 共通（CUDA/HIP/SYCL のパリティ実行ファイル） | 生成済みの選択列を維持 | `1`: sparse な query ごとに先頭 `w` セルを選ぶ。`3`: query ごとに異なる乱数 seed で `w-512` 個を選び、末尾 512 セルを加える。`4`: 4-query グループごとに共有する乱数 seed で同じ形の集合を作る | 空文字、`true`、数字で始まらない文字列は `atoi` が 0 とし、`2` と同じスライディング窓。`0`、`2`、`5`、`-1` など `1/3/4` 以外も同じ窓扱い。例: `3tail` は 3、`1x` は 1 として扱う |

窓扱いでは query `i` の開始位置を `min(i / 4 * 64, nkv - w)` とし、そこから `w` 個を連続して選ぶ。`w` はその query の選択幅、`nkv` はその時点の KV cell 数である。mode 3 と 4 の乱数集合は `nkv-512` 個の範囲から `w-512` 個を選び、最後の 512 個を加えてから昇順に並べる（`engine/src/kernels/qsa_prompt_attn_parity.cpp:132-149`、`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:183-200`）。

## 有効になる条件

- `qsa_prompt_attn_parity` または HIP 版 `hip_prompt_attn_wmma` をビルドして実行すること。CUDA 版は `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` と `STRATA_ENABLE_CUDA` の条件で追加される（`engine/cmake/strata_gpu_engine.cmake:137-143`）。HIP 版もパリティ用ターゲットである（同 `:702-710`）。SYCL 版はパリティ実行ファイルとして追加され、CTest に登録される（`engine/sycl/CMakeLists.txt:583-588`）。通常の engine の動作には適用されない。
- 選択幅が全 KV cell 数と等しい query では `continue` して書き換えない。`qsa_selection_width` は `min(n_kv, idx_top_k + idx_block - 1)` で、この checkout の実 geometry では sparse 幅の境界は 2,051 cells である。そのためその境界以下の query には `QA_SAME` の効果がない（`engine/src/kernels/qsa_prompt_attn_parity.cpp:132-134`、`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:183-185`、`engine/include/strata/kernels/qsa.hpp:131-140`）。
- SYCL 版では `QA_BLOCK4` が初期 selection と `steps` の幅を作った後に `QA_SAME` が評価される。`QA_SAME` の対象 query では ID 列をさらに書き換える（`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:144-159, 179-200`）。
- 両版とも、その後 `QA_DUMP` が有効で該当する記録を読めた場合は dump 内の ID 列で `ids` を上書きするため、最終的な計算入力は `QA_SAME` の列ではなくなる（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:151-167`、SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:202-218`）。dump を開けない場合は `QA_DUMP: cannot open`、該当記録がない場合は `QA_DUMP: no record for layer %d, T %lld, ctx %lld` を stderr に出して終了コード 2 で終了する。
- CLI の `context` と `queries` 引数、および実行ファイル内の複数の `run()` ケースにより、どの query が sparse かが変わる。CUDA/HIP 版は複数 format と短い context のケースを実行し、SYCL 版も format と `--int8-only` に応じたケースを実行する（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:346-377`、SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:455-494`）。

## 実行時の詳細

初期選択列を CPU 上で用意した後、`run()` ごとに環境を読み、sparse query の `ids` 部分を上記の規則で変更する。その後 `ids` を device buffer に転送し、旧・新 kernel と参照計算へ渡す（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:95-150, 198-219`、SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:129-201, 249-280`）。関数内・プロセス内の cache はない。実行中に外部から shell の環境を変更しても既存プロセスの環境は変わらないが、プロセス環境自体が次の `run()` より前に変更された場合は次回の読み取りに反映される。子プロセスへの転送はこのコードにない。

モード 1 は先頭セルからの同一窓、3 は query ごとに異なる seed、4 は 4 query ごとに共通 seed の乱数窓を使う。2 およびその他の整数（0 を含む）は窓の開始位置を query 群ごとに 64 cell ずつ進める。これらはテスト入力の selection を変えるもので、通常の実行経路やモデル出力を直接制御しない。パリティ比較の結果や測定時間は入力 selection の変更に伴って変わり得るが、この変数の効果量はソースからは確定できない。

## ログと測定値

`QA_SAME` 自体について有効・無効を示すログはない。実行ファイルは CUDA/HIP 版で `PASS` / `FAIL`、誤差、所要時間、出力 checksum を表示し、各 `run()` の比較結果を返す（`engine/src/kernels/qsa_prompt_attn_parity.cpp:325-342`）。SYCL 版も比較結果と所要時間を表示し、`FAILURES: %d` を出して失敗数に応じた終了コードを返す（`engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:430-451, 482-494`）。これはソース上の出力形式であり、ここでは build や GPU 実行による測定を行っていない。

## 根拠

- `engine/src/kernels/qsa_prompt_attn_parity.cpp:128-150` — CUDA/HIP 共用ソースの getenv、変換、モード分岐。
- `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:179-201` — SYCL ソースの getenv、変換、モード分岐。
- `engine/cmake/strata_gpu_engine.cmake:137-143,702-710`、`engine/sycl/CMakeLists.txt:583-588` — 診断用実行ファイルの build / CTest 定義。
- `engine/include/strata/kernels/qsa.hpp:131-140` — selection 幅と sparse 境界。
