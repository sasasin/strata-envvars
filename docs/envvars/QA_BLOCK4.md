# `QA_BLOCK4`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版の standalone `qsa_prompt_attn_parity` が作る合成データの選択セルを、4 セル単位のブロック選択に切り替えます。Strata エンジンのモデル実行や通常の `strata` 実行が読む変数ではありません。通常の選択では、最近の 512 セルと、クエリ間で少しずつ入れ替わる古いセルを合成します。`QA_BLOCK4` を設定すると、最近の最大 128 ブロックと、必要数に達するまで乱択した古いブロックを選び、各ブロックの 4 セルを展開します。

## 値と判定

値の内容は parse されず、`std::getenv("QA_BLOCK4")` が null かどうかだけで判定されます。

| 状態 | 分岐 |
|---|---|
| 未設定 | 通常の合成選択（最近 512 セルと古いセルの集合） |
| 設定済み | 4 セル単位のブロック選択 |

したがって `QA_BLOCK4=0`、`QA_BLOCK4=false`、空文字を含む、何らかの値が設定されていればブロック選択になります。文字列の大文字小文字、数値としての妥当性、値の境界は検査されません。既定値は未設定時の通常選択です。CLI 引数や他の環境変数による上書きはありません。

## 有効になる条件

- SYCL ビルドの parity target `qsa_prompt_attn_parity` に限られます。SYCL の CMake では `STRATA_SYCL_PARITY` が ON のときこの実行ファイルを追加します（既定値は ON）。この target は CTest には登録されず、明示的に実行する診断用プログラムです。
- CUDA 用の同名 parity ソース `src/kernels/qsa_prompt_attn_parity.cpp` には `QA_BLOCK4` の読み取りがありません。リポジトリ全体の完全一致検索では、読み取りは `sycl/src/kernels/qsa_prompt_attn_parity.cpp` の 1 箇所です。
- `run()` が選択幅 `w` をキャッシュセル数 `nkv` と等しいと判定したクエリでは、環境変数を調べる前に全セルを選んで次のクエリへ進みます。そのため短いコンテキストではブロック選択は実行されず、選択が疎になるクエリでのみ判定分岐に到達します。
- parity プログラムは合成 K/V・query・selection を使って新旧 attention の出力を比較・計時します。モデルの選択や engine の attention 入力へ値を渡す経路はありません。

## 実行時の詳細

`run()` 内で各クエリの選択を組み立てるループ中に環境を読みます。結果を static/local cache へ保存していないため、疎な選択のクエリごとに `getenv` が呼ばれます。ブロック分岐では `nkv / 4` 個の完全なブロックから `min(nbk, w / 4)` 個を選びます。末尾の不完全ブロックに属するセルは、選択ブロックを展開した後に追加します。ブロック ID は昇順に並べ、各ブロック内の 4 セルを連続して `ids` に書き、実際に書いたセル数を `steps` の幅へ反映します。

この変数自体はログ、警告、終了コードを発生させません。選択された合成 ID 群が後続の旧 attention と新 prompt attention の比較・計時入力になります。SYCL parity 実行ファイルは SYCL 側で prompt kernel が未移植のため、現行 CMake コメント上はこの kernel が pool を拒否する経路があります。その場合、`qsa_prompt_attn_batch refused the pools` を stderr に出して終了コード 2 になります。これは parity 実行経路の制約であり、`QA_BLOCK4` が起こす専用の失敗ではありません。

## 根拠

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:121-169` — 合成選択の幅、全セル選択時の早期 continue、`QA_BLOCK4` の有無判定、ブロックの選択・展開と通常選択。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:257-269,361-366` — 選択を旧・新 attention に渡し、結果比較と計時を行う処理。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:386-418` — standalone executable の引数と実行対象。モデルをロードする経路はない。
- `include/strata/kernels/qsa.hpp:127-134` — `qsa_selection_width` は `min(n_kv, idx_top_k + idx_block - 1)`。完全選択なら parity ソースの `w == nkv` 分岐に入る。
- `sycl/CMakeLists.txt:279-282,404-408` — `STRATA_SYCL_PARITY` による parity build block と、prompt attention parity target の追加。target は「Built, not registered」と記載。
- `CMakeLists.txt:522-528` — CUDA parity target は `src/kernels/qsa_prompt_attn_parity.cpp` を使う。ソース全体の完全一致検索で `QA_BLOCK4` の読み取りは SYCL 側だけに存在する。
- `sycl/CMakeLists.txt:404-405, sycl/src/kernels/qsa_prompt_attn_parity.cpp:263-265` — SYCL 側で prompt kernel が未移植で pool を拒否しうる旨と、拒否時の stderr・exit 2。
