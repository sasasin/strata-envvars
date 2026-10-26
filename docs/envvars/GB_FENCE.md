# `GB_FENCE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`GB_FENCE` は Strata の通常実行エンジンの設定ではなく、Metal の grid barrier 動作を調べる専用ベンチマーク `gridbar_bench` のコンパイル選択肢です。設定されていると、ベンチマークが実行時にコンパイルする Metal ソースへ `GB_FENCE` を定義します。これにより grid barrier の前後に device scope の sequentially consistent atomic thread fence が含まれます。

この環境変数名を読むコードは `metal/tests/gridbar_bench.cpp` だけです。実装ソース `metal/kernels/gridbar.metal` 自体が環境変数を読むわけではありません。

## 値と判定

| `GB_FENCE` | 判定 | コンパイルされる prelude |
|---|---|---|
| 未設定 | 無効 | `#define NO_GGML_COMMON 1` |
| 空文字を含め、何らかの値が設定済み | 有効 | `#define NO_GGML_COMMON 1` と `#define GB_FENCE 1` |

C++ の `std::getenv("GB_FENCE")` の戻り値が null かどうかだけで判定します。値を文字列比較・数値変換しないため、`0`、`false`、空文字も設定されていれば有効です。大小文字や値の末尾は判定に影響しません。

## 有効になる条件

この分岐は `metal/tests/gridbar_bench.cpp` の `main` でのみ評価されます。`metal/CMakeLists.txt` は `metal/tests/*.cpp` を実行ファイルとして登録するため、macOS 向け Metal プロジェクトを構成した環境で `gridbar_bench` がビルド対象になります。通常の CUDA/HIP/SYCL エンジンやサーバーの動作を切り替えるコードは確認できません。

## 実行時の詳細

ベンチマーク起動時に環境変数の設定有無を調べ、`Context::compile` に渡す prelude を選びます。`Context::compile` は prelude を Metal 標準ヘッダーと対象カーネルのソースより前に連結し、そのソースを Metal の `newLibraryWithSource` でコンパイルします。従って、この判定はベンチマークの起動ごとのコンパイルに適用されます。プロセス起動後に環境を変更して再評価する経路はありません。

`GB_FENCE` が有効な場合、`grid_barrier` は `threadgroup_barrier` の直後と、atomic counter の待機後の `threadgroup_barrier` の直後にそれぞれ `atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device)` を実行します。無効時にはこの二つの fence 呼び出しがプリプロセッサで除かれます。ベンチマークは dispatch 境界方式と grid barrier 方式の時間および stale flag 数を表示しますが、環境変数そのものによる性能差や結果の保証はソースから断定できません。

## 根拠

- `metal/tests/gridbar_bench.cpp:11-17` — 起動時の `getenv` 判定とコンパイル prelude の選択。
- `metal/CMakeLists.txt:41-47` — `tests/*.cpp` を実行ファイルとして登録。
- `metal/src/mtl_rt.h:91`, `metal/src/mtl_rt.mm:75-105` — `Context::compile` の宣言と prelude を先頭に付けて Metal ソースをコンパイルする処理。
- `metal/kernels/gridbar.metal:9-22` — `GB_FENCE` により条件付きとなる barrier 前後の fence。
- `metal/tests/gridbar_bench.cpp:24-64` — dispatch と grid barrier の計測および stale flag カウント出力。

リポジトリ全体での完全一致検索では、環境変数として読む箇所は上記ベンチマーク一か所でした。`docs/DETAILS.md` にこの変数の説明や比較測定値は見つからなかったため、性能値は記載していません。
