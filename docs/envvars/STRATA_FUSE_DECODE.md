# `STRATA_FUSE_DECODE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

実験的 CUDA ビルドに含まれる decode 時の演算融合を選ぶ。対象は activation 量子化画像の一括生成、対応する BF16 射影のペア実行、shared expert の gate/up GEMV と SwiGLU、MoE SwiGLU と Q8 量子化など。値が有効でも、該当するモデル層・重み形式・通常経路に到達しない場合はその融合は使われない。読み取り関数は `strata::kernels::fuse_decode()` である（`engine/include/strata/kernels/fuse_decode.hpp:9-15`）。

このヘッダー内の関数が `STRATA_EXPERIMENTAL_SM60` の下で呼ばれる箇所に限って実際の融合分岐がコンパイルされる。CMake はこの macro を CUDA と `STRATA_EXPERIMENTAL_SM60` の両方が有効なときに定義する。これは Pascal sm_60 / Volta sm_70 向けの実験ビルドで、通常の配布エンジンには該当コードが入らない（`engine/cmake/backends/cuda.cmake:28,47-57,76-80`; `engine/cmake/strata_gpu_engine.cmake:14-17`）。

## 値と判定

`fuse_decode()` は `std::getenv` で値を取得し、値が存在し、かつ先頭文字が文字 `'1'` の場合だけ true とする。文字列全体の parse や数値変換はしない。値は関数内 `static const bool` に初回呼び出し時保存され、その後の環境変更は反映されない（`engine/include/strata/kernels/fuse_decode.hpp:9-14`）。

| 状況 | 判定 | 例 |
|---|---|---|
| 初回読み取り時に未設定 | false | unset |
| 空文字 | false | `STRATA_FUSE_DECODE=` |
| 先頭が `1` | true | `1`, `10`, `1anything` |
| その他 | false | `0`, `0anything`, `true`, `2`, ` 1`, `TRUE` |

CUDA の NVIDIA 既定値処理は、環境変数が未設定のときだけ値 `1` を設定するため、既に定義された空文字や無効値はそのまま残る。sm_60 では `STRATA_SM60_PERF` の先頭文字が `0` の場合は既定値テーブルを使わず、それ以外（未設定を含む）では `STRATA_FUSE_DECODE=1` を既定値候補に含める。テーブル適用時、ユーザーが対象変数を何らかの値で定義済みならその値を優先する（`engine/src/core/nv_defaults.cpp:14-18,164-175,222-234`）。

## 有効になる条件

- 融合コードがビルドに含まれるには CUDA ビルドで `STRATA_EXPERIMENTAL_SM60=ON` が必要。CMake は Pascal / Volta の実験ビルドとして説明し、CUDA 12.x を要求している。HIP、Metal、SYCL、および通常の sm_75 以降用配布ビルドではこの macro 付き融合経路はコンパイルされない（`engine/cmake/backends/cuda.cmake:47-57,76-80`; `engine/cmake/strata_gpu_engine.cmake:14-17`）。
- 自動で `=1` が入るのは、実行時に NVIDIA CUDA 初期化が成功し、可視 GPU が 1 台以上あり、全可視 GPU の compute capability が同一で、その capability が sm_60 である場合。さらに `STRATA_SM60_PERF` の先頭文字が `0` ならテーブル全体が適用されない。既定値処理は環境変数未設定時にだけ値を設定する（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:164-175,222-234`）。
- sm_70 では既定値テーブルにこの変数は含まれないが、ユーザーが `STRATA_FUSE_DECODE` を有効値に設定し、実験ビルドに該当コードがあれば呼び出し側の分岐条件を満たす箇所で使われる（`engine/src/core/nv_defaults.cpp:136-163`; `engine/src/core/layer.cpp:326-335`; `engine/src/kernels/cuda/shared_expert.cu:350-378`）。
- モデル側の条件として、GDN 層、MoE/shared expert、QSA 層などの対応コードを実行する必要がある。例えば GDN 的 activation 画像生成は必要な重みが native 形式でない場合に行い、QSA の画像生成も K/V/Q のいずれかが native でない場合に行う。QSA の BF16 射影ペアは `fuse_decode()` が true の場合に選ばれる（`engine/src/core/layer.cpp:263-273,326-335,1172-1186,1204-1217`）。
- shared expert の gate/up ペア GEMV は両方の射影が native でない場合にのみ試され、S-family 条件を満たせない場合は通常の個別射影に戻る。MoE SwiGLU-Q8 の専用 fast 経路が成立する場合はそちらが先に選ばれ、`fuse_decode()` の分岐には入らない（`engine/src/kernels/cuda/shared_expert.cu:350-378`; `engine/src/kernels/cuda/s2_expert_grouped.cu:601-625,1296-1321`）。

## 実行時の詳細

既定値が適用される NVIDIA 起動経路では、device 検出後、エンジンの switch 読み取り前に `apply_nv_defaults` が呼ばれる。変数が未設定なら値 `1` を設定し、設定した switch 名をまとめた stderr の既定値案内に出す。出力には `strata: sm_60 (Pascal):`、`speed switches on by default`、`STRATA_SM60_PERF=0 turns them off`、`a switch you set is kept` が含まれ、一覧には接頭辞を除いた `FUSE_DECODE` と表示される。ユーザーが既に変数を設定している場合、その変数は既定値として追加されない（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:222-255`）。

初回 `fuse_decode()` 呼び出し時に判定を cache する。したがって、呼び出し後に同一プロセス内で環境値を書き換えても切り替わらない。対応する呼び出し箇所では、通常の複数処理を融合版に置き換える。例として、GDN の二つの BF16 射影を `project_bf16_pair` にまとめ、通常時の二回の `project_bf16` を省く（`engine/src/core/layer.cpp:326-335`）。shared expert では条件成立時、gate/up の S-family GEMV と SiLU 積を一つの kernel で行い、条件不成立時は通常の個別射影経路を使う（`engine/src/kernels/cuda/shared_expert.cu:350-378`）。MoE grouped expert では通常の SwiGLU と量子化の別処理を融合呼び出しに置き換える（`engine/src/kernels/cuda/s2_expert_grouped.cu:1307-1321`）。

この環境変数専用の CLI 引数や設定ファイル上書き経路は見つからなかった。明示設定と NVIDIA の自動既定値の関係は上記のとおりで、CLI からの別優先順位はない。環境値による独立した警告・エラー・終了経路もない。NVIDIA sm_60 で既定値が設定されたときの一般的な既定値ログ以外に、融合の有効化を示す専用ログは確認できなかった。

## ログと測定値

コードコメントは融合経路について「bitwise」相当の一致を述べている（例: shared expert の gate/up ペアは unfused sequence と bit-exact、`engine/src/kernels/cuda/shared_expert.cu:352-355`）。Strata の `docs/NVIDIA_V100.md` には V100 で `STRATA_FUSE_DECODE=1` のとき「4-16 us per token saved, not visible end to end」と記載されているが、同じ表のこの項目には個別レポートや測定条件が付いていないため、ここでは資料上の記載としてのみ扱う（`docs/NVIDIA_V100.md:138`）。環境変数自体についての専用ログ文言はない。自動既定値のログ条件と形式は「実行時の詳細」を参照。

## 根拠

- `engine/include/strata/kernels/fuse_decode.hpp:9-15` — 値の読み取り、先頭文字判定、初回評価 cache。
- `engine/src/core/nv_defaults.cpp:14-18,164-175,222-255` — sm_60 既定値条件、ユーザー設定優先、環境への設定とログ。
- `engine/src/program/generate.cpp:4421-4449` — CUDA 起動時の device 条件と既定値適用箇所。
- `engine/cmake/backends/cuda.cmake:28,47-57,76-80`; `engine/cmake/strata_gpu_engine.cmake:14-17` — 実験ビルド条件。
- `engine/src/core/layer.cpp:263-273,326-335,374-383,483-495,1172-1217`; `engine/src/kernels/cuda/shared_expert.cu:350-378`; `engine/src/kernels/cuda/s2_expert_grouped.cu:601-625,1296-1321` — 呼び出し経路と条件付き fallback。
