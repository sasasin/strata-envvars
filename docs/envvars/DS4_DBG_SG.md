# `DS4_DBG_SG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek エンジンの一部演算で、演算の入力・出力値や行列サイズを stderr に出す診断フラグです。読み取り箇所は `metal/src/engine/ds4_finish.cpp` の `hc_post`、`hc_mix_scale`、`hc_split` と、`metal/src/engine/ds4_host.cpp` の `sgemm_tn` です。値をカーネル選択や演算式に渡す処理ではなく、既存の Metal dispatch 前後の値を表示します。

## 値と判定

全箇所で `std::getenv("DS4_DBG_SG")` の null 判定だけを行います。文字列の変換・比較・数値 parse はありません。

| 環境の状態 | 判定 | 挙動 |
|---|---|---|
| 未設定 | 無効（`getenv` が null） | この変数による追加ログと、それに伴う `flush_runs()` は行わない |
| 空文字を含む任意の値が設定済み | 有効（`getenv` が非 null） | 該当演算で追加ログを出す |

`0`、`false`、空文字も設定されていれば有効です。無効値、境界値、clamp、fallback の概念はありません。CLI 引数・設定ファイル・別の環境変数による上書きや優先順位も実装されていません。

根拠: `metal/src/engine/ds4_finish.cpp:227-228,271,354,360`, `metal/src/engine/ds4_host.cpp:177`。

## 有効になる条件

- macOS 専用の Metal ビルドで DeepSeek エンジン `strata_ds4` をビルドし、対応する処理が呼ばれる場合に読み取り箇所へ到達します。Metal の CMake は macOS 以外を拒否し、Metal 実装の `.cpp` 群を glob でカーネルライブラリに含め、`strata_ds4` に DeepSeek ソースを含めます（`metal/CMakeLists.txt:14-18,110-127,132-171`）。
- `hc_post`、`hc_mix_scale`、`hc_split` は `src/dsv41/ds4_kernels.cu` から `STRATA_METAL` 条件で Metal host 実装を試し、成功すると通常の kernel launch に進まず戻ります（`src/dsv41/ds4_kernels.cu:2233-2238,2268-2279`）。各処理に到達しなければ、その箇所のログもありません。
- `sgemm_tn` は Metal 実装内で dispatch した後に環境変数を確認します（`metal/src/engine/ds4_host.cpp:148-180`）。この `.cpp` は CMake の Metal kernel source glob に含まれます（`metal/CMakeLists.txt:110-127`）。ただし `sgemm_tn` への直接の呼び出し箇所は Strata ソース内で確認できず、実行時にこのログが出る条件までは裏付けられません。
- `DS4_DBG_SG` の判定自体には build macro、OS 分岐、CLI、モデル状態、他変数による追加条件はありません。個々の処理が環境変数を確認する前に失敗して return する場合は、その処理の診断ログは出ません。

## 実行時の詳細

値は helper や起動ラッパー経由で渡されず、5 箇所すべてで直接 `std::getenv` されています。static cache はありません。`hc_post` は関数呼び出しごとに一度判定してローカル変数 `dbg` に保持し、その呼び出し内の前後ログに使います。ほかの各ログ箇所はそれぞれの演算実行後（`hc_split` は実行前・後）に `getenv` を評価します。そのため、処理ごとに読み直され、実行中に環境が変更された場合は後続の判定に反映され得ます。プロセス起動後の変更を Strata が禁止・固定する処理はありません。

設定時は、GPU dispatch の前後に `g_cx->flush_runs()` または `finish_cx().flush_runs()` を行い、host view 上の値を `fprintf(stderr, ...)` で表示します。

| 処理 | 記録する内容 |
|---|---|
| `hc_post` | dispatch 前に `y`, `h`, `post`, `comb` の一部を `hc_post in:` として表示し、dispatch 後に `h` の一部を `hc_post out:` として表示 |
| `hc_mix_scale` | dispatch 後に `T`, `hcdim`, `n_mix`, `eps` と `mixes` の先頭値を `hc_mix_scale ... ->` として表示 |
| `hc_split` | dispatch 前に `mix`, `scale`, `base` の一部を `hc_split in:`、後に `pre` の一部を `hc_split out:` として表示 |
| `sgemm_tn` | dispatch 後に行列サイズ・leading dimension と `A`, `B`, `C` の先頭要素を `sgemm ...` として表示 |

ログ出力のための flush は、それまでに積まれた処理を進めて host 側から読み出せる状態にする処理です。そのため観測時点・実行の同期タイミングには影響します。一方、この環境変数によって Strata が演算式、dispatch の選択、戻り値や終了コードを変更する分岐は確認できません。環境変数固有の警告、エラー、失敗・終了経路もありません。通常の処理が host view 不在等で失敗すれば各関数の既存経路に従いますが、それはこの変数によるものではありません。

根拠: `metal/src/engine/ds4_finish.cpp:227-241,271-276,354-365`; `metal/src/engine/ds4_host.cpp:148-182`。

## 根拠

- 全参照: `metal/src/engine/ds4_finish.cpp:227,271,354,360`; `metal/src/engine/ds4_host.cpp:177`。リポジトリ全体の候補名検索ではこの5箇所以外に参照はありません。
- Metal の `strata_ds4` が DeepSeek 実装と Metal host kernel を組み込むこと、および macOS 限定: `metal/CMakeLists.txt:14-18,110-127,132-171`。
- DeepSeek kernel wrapper が Metal host 実装を先に呼び、成功時は戻る条件: `src/dsv41/ds4_kernels.cu:2233-2238,2268-2279`。
- `docs/DETAILS.md` にこの変数の説明は見つかりませんでした。
