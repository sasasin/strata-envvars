# `STRATA_PARK_COPY_THREADS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_PARK_HOST_MEMCPY` が選ぶホスト間 K/V コピー経路で使う、コピー pool の合計スレッド数を指定する。pool は `total_threads - 1` 本の常駐 worker を作り、呼び出し元スレッドも同じタスク列を処理するため、値は worker 数ではなく合計数である。各コピー範囲は最大 4 MiB のチャンクに分けられ、呼び出し元と worker が分担する（`engine/src/core/conversation_snapshot.cpp:300-324,328-360,376-391`）。

この変数だけではホストコピー経路を有効にしない。`STRATA_PARK_HOST_MEMCPY` が有効で、K/V 状態の `kv_mode != 0` のときに保存・復元がこの pool を使う。`kv_mode == 0` の状態や通常の device copy 経路ではスレッド数は使われない（`engine/src/core/conversation_snapshot.cpp:274-283,441-465,680-699,726-745`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atoi` で整数変換する。未設定なら `8`。変換結果が正数なら 1〜16 に制限し、0 以下なら既定値の `8` に戻す。文字列全体の妥当性検査はなく、`atoi` が読む先頭の数値部分が使われる（`engine/src/core/conversation_snapshot.cpp:285-292`）。

| 条件 | unset | 有効になる値（例） | 無効値・fallback の例 |
|---|---|---|---|
| `park_copy_threads()` が初回評価されたとき | 合計 8 スレッド | `1`〜`16` は指定数、`20` は上限の 16 | 空文字、`0`、`-2`、`true`、`0anything` は変換結果が正でないため 8。`3workers` は先頭の `3` が変換され 3 |

`atoi` を使うため、先頭空白や符号は整数変換に従い、大文字小文字の区別や `true` / `false` の特別扱いはない。上限超過は 16 に丸め、正数の最小値は 1。無効値を知らせる警告やエラーはこの関数にはない（同 `:285-292`）。

## 有効になる条件

- `STRATA_PARK_HOST_MEMCPY` も有効であること。この別変数は未設定・空文字・先頭文字が `0` の場合は無効、それ以外の非空文字列は有効として cache される（`engine/src/core/conversation_snapshot.cpp:274-283`）。
- 保存または復元対象の `QsaState` が `kv_mode != 0` であること。保存は K/V の先頭 4 部分をホスト間 `memcpy` に切り替え、復元も K/V の先頭 4 部分に同じ経路を使う。pooled/index 部分は引き続き `transfer` を使う（同 `:441-465,680-699,726-745`）。
- その呼び出しでコピー対象の span があること。保存時は再利用済み prefix より後にコピーするバイトがある場合、復元時は対象の各バッファにデータがある場合に pool が実行される。空の span では pool は作られない（同 `:449-465,528-534,376-391`）。
- この C++ 実装は CUDA/HIP 共通 GPU engine に含まれる。CMake の `strata_gpu_engine` は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` の場合にその engine と `conversation_snapshot.cpp` をビルドする。設定一覧も NVIDIA / AMD 向けとしている（`engine/cmake/strata_gpu_engine.cmake:1-9,310-316`; `docs/SETTINGS.md:190-191`）。CPU-only、Metal、SYCL engine にはこの実装の適用を確認できない（`engine/CMakeLists.txt:3-7,25-32`）。
- 主な利用経路は `--serve` の conversation cache による park/restore、および batch slot の K/V 保存・復元。serve では会話 cache が無効、または park 対象にならない場合はコピー経路に到達しない。`--conversation-cache-mib` 等の CLI 値がこの環境変数を上書きする実装はない（`engine/src/program/generate.cpp:13768-13804,14174-14191,14375-14412,16804-16825,16888-16911`）。

## 実行時の詳細

`park_copy_threads()` 内の `static const int` は最初の呼び出し時に一度だけ評価される。さらに pool は最初の `parallel_host_memcpy()` 呼び出し時に `static HostCopyPool*` として作られ、プロセス終了時まで保持される。したがって、pool 作成より前の環境変更は初期値に反映され得るが、値の cache 後や worker pool 作成後の変更は反映されない（`engine/src/core/conversation_snapshot.cpp:285-292,376-391`）。

worker は pool 作成時に `合計数 - 1` 本だけ生成され、idle 時は condition variable で待機する。タスクが一つ以下、または worker がいない場合は呼び出し元が逐次コピーする。複数タスクなら呼び出し元もタスクを処理し、worker 全員が終わるまで待ってから戻る。各チャンクの完了で `core::progress_beat()` が呼ばれる（同 `:300-360`）。

この値は token 生成数や K/V の内容を変える設定ではなく、条件付きホスト間コピーの並列度を変える。CLI のスレッド数指定との優先順位や別の copy-thread 環境変数は、該当実装にない（同 `:285-391`）。

## ログと測定値

この変数の読み取り、fallback、thread 数について専用ログはない。コピー自体が失敗して保存 API が `false` を返すと、serve の park 処理は snapshot 失敗として扱い、park を省略する経路がある。`std::bad_alloc` の場合は `strata serve: conversation cache: allocation failed; skip parking` を stderr に出し、通常の prompt 処理を続ける（`engine/src/core/conversation_snapshot.cpp:264-271,441-465`; `engine/src/program/generate.cpp:14375-14380,14420-14425`）。

`docs/DETAILS.md` にこの変数の測定値や性能比較はなく、速度向上は断定できない。`docs/SETTINGS.md` には NVIDIA / AMD 向け `number` 設定として登録されているが、値の解釈と効果は上記ソース実装に基づく（`docs/SETTINGS.md:190-191`）。

## 根拠

- `engine/src/core/conversation_snapshot.cpp:285-292` — 環境変数の読み取り、変換、既定値、clamp、cache。
- `engine/src/core/conversation_snapshot.cpp:300-391` — pool の worker 数、待機・分担、チャンク化、初期化時期。
- `engine/src/core/conversation_snapshot.cpp:441-465,528-534,680-699,726-745` — 有効条件と保存・復元での使用。
- `engine/src/program/generate.cpp:13768-13804,14174-14191,14375-14425,16804-16825,16888-16911` — serve cache と batch slot の呼び出し、失敗時の扱い。
- `engine/cmake/strata_gpu_engine.cmake:1-9,310-316`; `engine/CMakeLists.txt:3-7,25-32` — 対象 backend とビルド範囲。
- `docs/SETTINGS.md:190-191`; `docs/DETAILS.md:834-838` — 設定一覧と関連する conversation cache の CLI 記述。
