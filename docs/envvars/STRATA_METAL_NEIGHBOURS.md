# `STRATA_METAL_NEIGHBOURS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Apple Metal 版の DeepSeek-V4.1 エンジン `strata-dsv41` が、自プロセス以外のプログラムの匿名メモリ使用量を見積もり、その分だけ VRAM（Metal の共有メモリ）に置く expert の予算を減らすかを切り替えます。既定では見積もりを有効にし、`STRATA_METAL_NEIGHBOURS=0` で無効にします。

この変数は `STRATA_METAL` ビルドにだけコードが含まれます。また、expert の自動配置中で、`DS4_NO_AUTO_VX` が未設定のときだけ参照されます。CUDA/HIP ビルドや `--vram-experts` で明示予算を指定した実行には適用されません。

## 値と判定

`std::getenv()` の戻り値を `std::atoi()` に渡し、その結果が 0 かどうかで判定します。文字列全体の厳密な数値 parse やエラー検査はありません。

| 値 | 匿名メモリ見積もり |
|---|---|
| 未設定 | 有効 |
| `0`、空文字、数値に変換できない文字列 | 無効（`atoi` が 0） |
| `1`、`-1`、`2tail` など、`atoi` の結果が 0 以外 | 有効 |
| `0tail`、`00` など、`atoi` の結果が 0 | 無効 |

先頭の空白や符号は `atoi` の規則で扱われ、数値部分の後ろに文字があってもそこでの変換結果を使います。`atoi` による変換なので、無効文字列への警告や別の fallback 値はありません。

## 有効になる条件

- `src/dsv41/ds4_model.cu` が `STRATA_METAL` 定義ありでコンパイルされること。
- `place_experts()` の自動予算分岐が実行されること。`Options::vram_experts_auto` の既定値は `true` ですが、CLI の `--vram-experts F` は値を設定すると同時に `vram_experts_auto=false` にします。
- `DS4_NO_AUTO_VX` が未設定であること。設定値の内容は問わず、存在するだけで自動 cap の処理を止めます。

この変数が無効化するのは「他プログラム分」の差し引きです。Metal のメモリ cap 自体は残り、`STRATA_METAL_KEEP_FREE_GB` と `STRATA_METAL_LEAVE_SHARE` も別途 cap 計算に使われます。

## 実行時の詳細

モデル読み込み中、expert の配置を決める `place_experts()` が各 device group の budget を計算します。Metal 版の自動予算経路では `metal_expert_cap()` を呼び、プロセスの `phys_footprint` とホスト全体の `internal_page_count + total_uncompressed_pages_in_compressor` から、他プログラムの匿名メモリを見積もります。見積もりは `max(0, 匿名ページの bytes - 自プロセスの footprint - 8.0 GB)` です。その値を cap から差し引きますが、最終的な cap は最低 4.0 GB です。

見積もりが 0.5 GB を超える場合、stderr に `ds4: other programs hold ... of anonymous memory: ... less for the experts` と出ます。cap がその device group の既存 budget より小さい場合は `ds4: expert share: ...` の行も出て budget を cap まで下げます。配置された VRAM expert が少なくなると、残りはホスト側に置かれ、実行経路によりモデルファイルから読み込まれます。Apple Silicon の DeepSeek 説明書も、他プロセスが多くのメモリを持つ場合に engine が保持する expert 数を減らすと説明しています（`docs/DEEPSEEK_MAC.md:57-62`）。

環境変数値は `metal_expert_cap()` 呼び出しごとに `getenv()` で読み取られ、static cache はありません。呼び出しは expert 配置時に行われるため、リクエストごとの切り替えではありません。`host_statistics64()` が失敗した場合は匿名メモリ見積もりを加算せず、専用の失敗ログも出しません。cap がメモリ確保を保証するわけではなく、expert 配置後の `cudaMalloc` が失敗するとモデル読み込みは失敗し、`maya-ds4: ...` を stderr に出して終了コード 1 になります。

## 根拠

- `src/dsv41/ds4_model.cu:4423-4468` — Metal 専用 cap、`getenv` / `atoi` 判定、システム・プロセスのメモリ値、8 GB allowance、ログ、4 GB floor。
- `src/dsv41/ds4_model.cu:3041-3044,4585-4627` — モデル読み込み中の expert 配置と、Metal 自動予算での cap 適用条件。
- `src/dsv41/ds4_model.hpp:25-31`, `src/dsv41/ds4_main.cpp:1321` — 自動予算の既定値と `--vram-experts` による明示指定。
- `src/dsv41/ds4_model.cu:4695-4714`, `src/dsv41/ds4_main.cpp:1404-1406` — 配置後の expert 確保失敗とモデル読み込み時の終了経路。
- `CMakeLists.txt:906-920` — `strata-dsv41` が別の DeepSeek engine target として定義されること。該当コードはソース内の `#if defined(STRATA_METAL)` guard に限定される。
- `docs/DEEPSEEK_MAC.md:57-62` — 他プロセスのメモリ使用に応じて保持 expert を減らすという説明。文書の一般説明と実装は整合しますが、環境変数名やこの計算式の説明は文書にはありません。

候補一覧 `000_envvers.md` には名前があります。Strata 所有コード内では上記の直接読み取り一箇所を確認しました。外部ライブラリや GPU driver の環境変数動作はこの調査に含めていません。
