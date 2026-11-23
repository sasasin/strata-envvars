# `STRATA_VERIFY_TIMEOUT_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`Verifier::run()` が CUDA/HIP の通常の verify window を処理するとき、GPU が各レイヤーの doorbell（`h_seq_`）を進めるまでホスト側で待つ上限時間を秒単位で指定する。GPU 計算量や verify window のサイズは変えず、待ちが上限を超えた場合に timeout として verifier を失敗させるまでの時間を変える。値を読むのはレイヤーごとの待ちループであり、全 resident 経路ではこのループ自体を通らないため、この変数も評価されない（`engine/src/core/verify.cpp:3979-4009`）。

## 値と判定

| ビルド条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| `STRATA_USE_HIP` 定義（HIP） | 30 秒 | `atoi` の結果が正の整数になる値。例: `1`, `45`, `  +7tail` はそれぞれ 1、45、7 秒 | 空文字は unset と同じ 30 秒。`0`, `-1`, `false`, `0anything`, `anything` は正の結果にならず 30 秒 |
| `STRATA_USE_HIP` 未定義（CUDA 側） | 20 秒 | `atoi` の結果が正の整数になる値。例: `1`, `45`, `  +7tail` はそれぞれ 1、45、7 秒 | 空文字は unset と同じ 20 秒。`0`, `-1`, `false`, `0anything`, `anything` は正の結果にならず 20 秒 |

実装は `getenv` が null または先頭文字が `\0` の場合に既定値を使い、それ以外は `std::atoi` で変換した値を採用する。ただし変換結果が 0 以下なら既定値に戻す。文字列全体の数値検査はなく、`atoi` が読む先頭の数値部分の後ろは無視される。先頭空白と符号は `atoi` の規則で扱われ、大文字小文字の比較もない。`int` で表現できない数値を渡した場合の結果はこの実装で保証されない（`engine/src/core/verify.cpp:4001-4010`）。

## 有効になる条件

- CUDA/HIP の `Verifier::run()` が通常のレイヤーごとの doorbell 待ちに入ること。`ar_on() && !test_stall` の経路は GPU にフラグを上げてこの待ちループを省くため、設定値は読まれない（`engine/src/core/verify.cpp:3979-4009`）。
- HIP ビルドでは既定値が 30 秒、HIP 以外では 20 秒。ファイル先頭では CUDA と Windows HIP で `STRATA_VERIFY_HGL` を定義する条件があり、待ち中の stream query 方法には差があるが、環境変数の判定規則は共通（`engine/src/core/verify.cpp:1-6,4018-4022`）。
- 通常の `run()` 以外にはこの値を適用しない。`run_slot_rows()` の待ちは 20 秒固定（`engine/src/core/verify.cpp:5444-5466`）、`service()` のパイプライン待ちも 20 秒固定（同:6007-6062）。Metal 側の `run()` は独自の `window_run()` に処理を渡し、この変数を読む箇所はない（同:3792-3818）。
- CLI 引数、設定ファイル、別の環境変数による上書きは、この読み取り箇所にはない（同:4001-4010）。

## 実行時の詳細

値は `Verifier::run()` の各レイヤー待ちを始めるたびにラムダ内で読み取られ、関数内 static やプロセス起動時の cache はない。そのためプロセス内で環境値が変更された場合、後続レイヤー待ちから再評価される。タイマーは各レイヤーの待ち開始時刻 `a` から計り、`*seq < want` の間に上限を超えると再公開処理に入る（`engine/src/core/verify.cpp:3993-4015,4031-4046`）。

上限を最初に超えたとき、`want > 1` なら一度だけ、すでに処理済みの flag を fence 付きで再公開し、待ちを続ける。さらに指定時間に 5 秒を加えた時点を超えると失敗する。`want == 1` では再公開を行わず、同じ 5 秒の猶予後に失敗する。従って実際の失敗時刻は設定値そのものではなく、設定値に約 5 秒の猶予を加えた後になる。timeout の際は `release_gpu_waits(5000)` を呼んで GPU wait を解放し、呼び出し元へ `false` とエラー文字列を返す（同:4031-4061）。

## ログと測定値

通常の timeout はエラー文字列 `verify: timed out at layer <層番号>...` を設定して `false` を返す。`g_trace` が有効な場合はその前に `diag(stderr)` と `trace_dump(stderr)` を出し、timeout の trace event も記録する。再公開時の `RETRY-PUBLISH`、timeout 時の `TIMEOUT`、GPU graph が先に終わって doorbell が鳴らない場合の `NEVER-RANG` も trace event 名である。graph 終了を検出した場合の別エラーは `verify: layer <層番号> never rang (graph finished)`（CUDA/HIP query がエラーなら括弧内は CUDA error 名）となる（`engine/src/core/verify.cpp:4016-4028,4043-4061`）。この環境変数に関する測定値は `docs/DETAILS.md` に見当たらない。

## 根拠

- `engine/src/core/verify.cpp:1-6` — CUDA/HIP および host graph launch の compile 条件。
- `engine/src/core/verify.cpp:3776-3827` — `Verifier::run()` の入口と Metal 経路。
- `engine/src/core/verify.cpp:3979-4015` — 全 resident 分岐、GPU のレイヤー待ち、既定値と環境値の読み取り。
- `engine/src/core/verify.cpp:4016-4064` — stream query、再公開、猶予、timeout とエラー経路。
- `engine/src/core/verify.cpp:5444-5466,6007-6062` — slot batch と pipeline service に残る固定 20 秒待ち。
- `docs/SETTINGS.md:345` — 設定一覧で NVIDIA/AMD 向け number と分類。`docs/DETAILS.md` には対象変数の記述なし。
