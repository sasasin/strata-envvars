# `QA_SAME`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（`2026-10-26` 時点）。

## 役割

`QA_SAME` は通常の Strata engine の設定ではなく、QSA prompt attention の単体 parity/benchmark 実行ファイルが使う合成入力用の診断フックである。実行ファイルが生成する各 query の選択 cell ID を差し替え、query 間で cell を共有する度合いを変える。実際のモデル選択、推論出力、engine の dispatch は変更しない。

CUDA では `qsa_prompt_attn_parity`、HIP では `hip_prompt_attn_wmma` としてビルドされる。CUDA target は `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` と CUDA backend が条件で、HIP target は HIP のテスト設定内で CTest に登録される。SYCL 側も `qsa_prompt_attn_parity` という独立実行ファイルをビルドするが、CMake コメントは「Built, not registered」としている。したがって `QA_SAME` はこれらの診断バイナリを実行した場合に限って意味を持つ。

## 値と判定

読み取りは `std::getenv("QA_SAME")` の有無判定の後に `std::atoi` で行う。文字列全体の検証はしない。未設定なら合成 cell ID は既定の生成処理のまま。設定値が空でも `atoi` の結果は 0 になり、設定されているため差し替え処理に入る。

| `atoi` の結果 | 各 query の cell ID |
| --- | --- |
| `1` | 選択幅 `w` 個を常に `[0, w)` にする。全 query が同じ先頭範囲を読む。 |
| `2` | query `i` ごとに `base = min((i / 4) * 64, nkv - w)` とし、`[base, base + w)` を読む。4 query ごとに64 cellずつ進み、近傍 query の範囲を重ねる。 |
| `3` | query ごとに異なる seed で `nkv - 512` 個の候補から `w - 512` 個を選び、直近512 cellを加える。 |
| `4` | 4 query ごとに同じ seed を使って `w - 512` 個を選び、直近512 cellを加える。各4 query group が同じ選択集合を共有する。 |
| その他 | `2` と同じ処理。 |

`atoi` のため、先頭の空白や符号、数値の後ろの文字列は通常の C `atoi` の規則で扱われる。例えば `3tail` は 3、数値を含まない文字列や空文字は 0 となり、後者は上表の「その他」に入る。`2` と `4` 以外の正数も特別なモードではなく、`2` と同じ分岐になる。

## 有効になる条件

- 合成選択を作る `run()` が呼ばれ、`QA_SAME` が環境に設定されていること。
- 各 query について `w != nkv` であること。短い文脈で選択が全 cell（identity）になる query は変更されず、そのまま次へ進む。`qsa_selection_width()` は `min(nkv, idx_top_k + idx_block - 1)` を返す。
- 対象は CUDA の `qsa_prompt_attn_parity`、HIP の `hip_prompt_attn_wmma`、SYCL の `qsa_prompt_attn_parity` であり、main engine に `QA_SAME` の読み取りはない。ソース全体の完全一致検索では、CUDA と SYCL の2つの parity ソース以外に実装参照は見つからなかった。

## 実行時の詳細

環境変数は各 `run(fmt, ctx, nq, reps)` 呼び出しで一度読み、`ids` 配列を書き換える。static cache はない。1回のプロセス内でも各 run のたびに環境を読み直すが、この実行ファイル自身は `QA_SAME` を書き換えない。書き換え後の `ids` は parity 対象 kernel と FP64 host reference で使われ、誤差・出力一致の判定および時間計測に影響する。環境変数固有のログ出力はない。実行結果としては通常の `PASS`/`FAIL` 行と計時値が出るが、これは変更後の合成入力に対する parity tool の結果であり、性能を一般化する根拠ではない。

入力生成は `w == nkv` の query を先に除外するため、mode 3/4 の「直近512 cell + 以前の `w - 512` cell」という構成は sparse selection の query にだけ適用される。実行ファイルの既定の context（32768）では selection width は最大2051だが、短い context の追加 run では全 cellを読むため、`QA_SAME` を設定してもその query の selection は変わらない。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:43-56, 95-150`: run の役割、合成選択の生成、環境変数の読み取りと mode 1〜4 の ID 差し替え。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:120-175`: SYCL parity 実装にも同じ分岐がある。
- `include/strata/kernels/qsa.hpp:127-135`: 選択幅が context 以下で最大幅に制限されること。
- `src/kernels/qsa_prompt_attn_parity.cpp:280-342`: 変更された入力で行う精度比較、出力一致判定、計時および表示。
- `CMakeLists.txt:444-450, 905-907, 989-994`: CUDA parity target のビルド条件と、HIP parity target が HIP test setup 内で作られ CTest に登録されること。
- `sycl/CMakeLists.txt:376-380`: SYCL parity target がビルドされること。
- `docs/DETAILS.md:908-927`: prompt attention の実行時 opt-in 変数を列挙する関連資料。`QA_SAME` の説明はなく、同資料から runtime 設定としての意味は確認できない。
