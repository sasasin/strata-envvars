# `STRATA_TG_FLUSH_US`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP 共通 GPU engine と SYCL engine の token graph 実行中に、GPU が各 layer の doorbell を鳴らすのを CPU が待つ間、submission queue を再 query する間隔をマイクロ秒単位で指定する。指定値はグラフの計算や layer 順序を変えず、待機中の追加 flush と graph 完了・失敗の検出タイミングに関係する。CUDA/HIP 側では `session_run_token`、SYCL 側では同名関数が読み取る（`engine/src/core/session.cpp:923-936, 941-964`、`engine/sycl/src/core/session.cpp:1337-1370, 1375-1412`）。

## 値と判定

両実装とも `std::getenv` で値を取得し、未設定なら `2000`、設定されていれば `std::atoi` の戻り値を使う。関数内 `static const int` のため、各プロセスで最初に `session_run_token` がこの箇所へ到達した時点の値を一度だけ読み、その後は環境を変えても反映されない。空文字は設定済みなので `atoi("") == 0` となり、既定値には戻らない（`engine/src/core/session.cpp:934-937`、`engine/sycl/src/core/session.cpp:1367-1370`）。

`atoi` は整数として読める先頭部分を変換する。先頭の空白と符号は受け付け、数値の後ろの文字列は検査しない。数値に変換できない文字列は `0` になる。値の範囲検証や clamp はなく、`atoi` で `int` に表現できない数値は C/C++ の仕様上定義されない結果となり得る。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 共通 engine または SYCL engine の token graph 実行 | `2000` µs | `1`, `2000`, `+25`, ` 25`, `25us`（それぞれ `atoi` の結果は 1, 2000, 25, 25, 25） | `0`, `-1`, 空文字, `true`, `abc`, `0anything`（いずれも待機ループの flush 間隔としては即時相当の 0 以下） |

この値は flush 周期として使われるが、コードは正値チェックをしない。0 または負値では、1024 回ごとの spin 後に調べる時刻差が常にその値を上回るため、待機中はそのたびに queue query を行う。`atoi` は小数・基数接頭辞・文字列全体の妥当性を検証しない（`engine/src/core/session.cpp:947-965`、`engine/sycl/src/core/session.cpp:1381-1412`）。

## 有効になる条件

- 対象プロセスが token graph 経路で `session_run_token` を呼ぶ必要がある。`--no-capture` では通常の `session_token` 経路となり、この変数は読まれない。`--no-token-graph`、layer/half dump などにより token graph が capture されない場合も、`session_run_token` には到達しない（`engine/src/program/generate.cpp:10969-10978, 11069-11076, 24296-24314`）。SYCL の `generate.cpp` にも同じ呼び分けがある（`engine/sycl/src/program/generate.cpp:13504-13522`）。
- CUDA/HIP の共通 engine では `engine/src/core/session.cpp` が GPU engine に組み込まれ、SYCL engine では `engine/sycl/CMakeLists.txt` が対応する `src/core/session.cpp` を組み込む（`engine/CMakeLists.txt:22`、`engine/cmake/strata_gpu_engine.cmake:305-316`、`engine/sycl/CMakeLists.txt:290-300`）。この環境変数の判定自体に OS、GPU 世代、モデル形式、CLI の数値引数による追加分岐はない。
- graph が未 capture の場合、multi-GPU または native-pack などで別の layer loop に進む場合、あるいは通常の非 graph 経路では、この設定による追加 query はない。CLI の `--no-token-graph` は token graph を無効にする（`engine/src/program/generate.cpp:954, 1375, 4262, 11069-11076`）。

## 実行時の詳細

token graph を各 token で launch した後、両実装は一度 queue を query/flush し、各 layer の sequence counter が進むのを spin 待ちする。spin を 1024 回行うごとに時刻を確認し、前回 flush から `flush_us` を超えていれば追加 query を行う。CUDA/HIP は `cudaStreamQuery` が `cudaErrorNotReady` 以外を返し、まだ doorbell が鳴っていない場合に `session_run_token: layer N never rang (...)` を返す。SYCL は `ext_oneapi_empty()` で graph 完了を確認し、まだ doorbell が鳴っていなければ同じ形式のエラーを返す。SYCL runtime exception は catch 節が `exc.what()` と file/line を stderr に出して終了コード 1 で終了する。別に各 layer 待機には 20 秒の timeout があり、経過すると `session_run_token: timed out waiting for layer N` を返す（`engine/src/core/session.cpp:931-965`、`engine/sycl/src/core/session.cpp:1344-1412, 1462-1465`）。

関数内 static cache なので、CLI 引数や他の環境変数による優先順位・上書きはない。値が変えるのは待機中の再 query 頻度であり、GPU graph の演算や pool に渡すデータ自体をこの変数が変更するコードはない。標準の生成経路はエラー文字列を `strata generate: ...` として stderr に出し、終了コード 1 で終わる（`engine/src/program/generate.cpp:24302-24314`、SYCL は `engine/sycl/src/program/generate.cpp:13510-13522`）。

## ログと測定値

この変数を読み取ったことや値を適用したことを示す専用ログはない。`--stats` の token graph 集計は待機時間、pool 時間、flush 数、呼び出し位置数を表示するが、設定値そのものは表示しない（`engine/src/program/generate.cpp:25522-25526`）。Strata の `docs/DETAILS.md`、`docs/SETTINGS.md` にこの変数の説明や条件付き測定値は見つからなかった。コードコメントは既定周期 2000 µs とし、0 µs と 5 µs が同程度に速く「fault の検出のみ」と記すが、これは測定条件の記載がないコメントであり、一般的な性能値としては扱えない（`engine/src/core/session.cpp:936`、`engine/sycl/src/core/session.cpp:1369`）。

## 根拠

- `engine/src/core/session.cpp:923-983` — CUDA/HIP 共通 token graph 実行、値の読み取り、周期 query、失敗・timeout。
- `engine/sycl/src/core/session.cpp:1337-1465` — SYCL の対応実装。
- `engine/src/program/generate.cpp:10969-11076, 24296-24314, 25522-25526` — graph capture 条件、実行経路、エラー出力、stats。
- `engine/sycl/src/program/generate.cpp:13504-13522` — SYCL 側の実行経路。
- `engine/CMakeLists.txt:22`、`engine/cmake/strata_gpu_engine.cmake:305-316`、`engine/sycl/CMakeLists.txt:290-300` — 対応 session 実装の build 対象。
