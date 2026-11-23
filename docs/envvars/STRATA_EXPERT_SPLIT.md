# `STRATA_EXPERT_SPLIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL の native expert grouped カーネルで、コンパイル時に `kSplit<T>` が有効な量子化形式の gate/up と down の処理を、通常の lane カーネルから multi-entry カーネルへ切り替える。変数は `iq_kernels.dp.cpp` のグローバル `g_split_multi` を初期化し、multi-entry 側は 1 行あたり 1 warp、`GU_ROWS` 行単位の grid で起動される。未設定時の lane カーネルが既定経路であり、この変数は expert の選択や他の計算経路そのものを切り替えるものではない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3937,6002-6016,6053-6067,6115-6121`）。

この読み取り箇所を含むファイルは SYCL build のソース一覧にだけ登録されている。したがって CUDA build や HIP build に対する本変数の効果は、この実装からは確認できない（`engine/sycl/CMakeLists.txt:40-46`）。SYCL 実行時でも、native expert grouped 経路に入らない処理には適用されない。モデルの native expert を処理する runtime 呼び出しは `remote_experts.cpp` と `verify.cpp` にある（`engine/sycl/src/core/remote_experts.cpp:431-441`、`engine/sycl/src/core/verify.cpp:1728-1750`）。

## 値と判定

`env_on()` は `std::getenv()` で得た文字列について、未設定でなく、空文字でなく、先頭文字が `'0'` でないことだけを判定する。数値変換や文字列全体の比較は行わない。設定文字列はロード時のグローバル初期化で一度読まれ、`g_split_multi` に保持される（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3937`）。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| SYCL カーネル実装 | lane カーネルを選ぶ | `1`、`true`、`false`、` 1`、`2`、`1anything` | 空文字、`0`、`0anything` |

空白の trim、大文字小文字の正規化、数値としての妥当性検査はない。したがって `false` は先頭が `f` のため有効、`0anything` は先頭が `0` のため無効となる。一般的な値域・境界値・負値の parse は存在しない。

## 有効になる条件

- `engine/sycl/CMakeLists.txt` に含まれる SYCL 実装を使うこと。候補名の参照は SYCL 移植ファイル内の読み取り 1 箇所だけで、CUDA 側の `engine/src/kernels/cuda/iq_kernels.cu` にはありません。
- native expert grouped の gate/up または down の起動に到達し、その量子化型がコンパイル時の `kSplit<T>` に該当すること。該当しない型は変数が有効でも `launch_*_lanes` に進む（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6053-6067,6115-6121`）。
- `STRATA_OLD_IQ_MMVQ` が有効でないこと。同変数が有効なら `g_old_kernels` が優先され、`g_split_multi` が有効でも lane 経路を使う（同 `:3931-3937,6053-6066,6115-6120`）。
- `STRATA_IQ_STAGE_GRID` は multi カーネルを選ぶ条件ではないが、該当する `kStageIqGrid<T>` 型で真なら gate/up multi 経路が `STAGE_GRID=true` の variant を使う。偽または対象外の型では通常の multi variant になる（同 `:1251,3955-3968,6059-6067`）。

## 実行時の詳細

環境値はライブラリ／実行ファイル内の静的初期化時に取得され、`g_split_multi` に保存される。プロセス起動後の環境変更は再読込されない。CLI 引数や設定ファイルによる上書きは、この変数の読み取り・分岐経路にはない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3937`）。

有効で、対象形式かつ `g_old_kernels` が無効なら、gate/up は `launch_gu_multi()`、down は `launch_down_multi()` を呼ぶ。両者は `GU_ROWS` に基づく grid で SYCL `parallel_for` を起動する。無効値、未設定、旧カーネル指定、または対象外の形式では lane カーネルを呼ぶ。サブワープの `SUB16` / `SUB_DOWN` variant はこの分岐から起動しない（同 `:6002-6016,6053-6067,6071-6080,6115-6121`）。

## ログと測定値

この変数の読み取りや有効化だけを知らせるログ、警告、終了経路は見つからない。分岐後の SYCL kernel 起動には共通の `check("native_expert_grouped/gu")` と `check("native_expert_grouped/down")` があるが、本変数固有の診断ではない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7883,7980-7982`）。

`docs/INTEL.md:435` は B70 に関する decode 性能差を記載しているが、表の当該記述だけでは測定条件を特定できないため、この文書では性能値として扱わない。ソース上確認できるのは、SYCL 実装で lane カーネルを既定にし、本変数で multi カーネルを選択できることまでである。

## 根拠

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3937` — env 判定関数、旧カーネルとの別 global、および `g_split_multi` の初期化。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6002-6016,6053-6067,6071-6080,6115-6121` — multi kernel 起動と lane/multi の選択条件。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1250-1253,1251,3955-3968` — compile-time `kSplit<T>` と stage-grid 関連の条件。
- `engine/sycl/CMakeLists.txt:40-46` — 調査対象ファイルが SYCL build に含まれること。
- `engine/sycl/src/core/remote_experts.cpp:431-441`、`engine/sycl/src/core/verify.cpp:1728-1750` — runtime の native expert grouped 呼び出し。
