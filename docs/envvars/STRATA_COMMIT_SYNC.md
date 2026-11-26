# `STRATA_COMMIT_SYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP と SYCL の `Verifier::commit` で、単一 GPU 用に有効化される非同期 commit を止め、commit graph の完了をその場で待たせる。環境変数の値は解釈されず、設定されているかどうかだけを使う。生成初期化で `set_commit_async(!multi_gpu)` が呼ばれ、`multi_gpu` は layer split があり、かつ同一 GPU の split でない場合に true になる（CUDA/HIP: `engine/src/program/generate.cpp:4856,6493`、SYCL: `engine/sycl/src/program/generate.cpp:2333,3586`）。

## 値と判定

`Verifier::set_commit_async` は `on && std::getenv("STRATA_COMMIT_SYNC") == nullptr` をグローバル状態 `g_commit_async` に代入する。したがって値の内容は parse されず、空文字を含め、変数が存在すれば非同期 commit は無効になる（CUDA/HIP: `engine/src/core/verify.cpp:4524-4525`、SYCL: `engine/sycl/src/core/verify.cpp:3161-3162`）。

| 条件 | unset | 設定時に非同期になる値 | 設定時に非同期にならない値 |
|---|---|---|---|
| 生成初期化で `on=true`（`multi_gpu=false`） | 非同期を有効化 | なし | 空文字、`0`、`1`、`true`、その他すべての文字列 |
| 生成初期化で `on=false`（`multi_gpu=true`） | 同期 | なし | 空文字、`0`、`1`、`true`、その他すべての文字列 |

文字列比較、数値変換、大文字小文字、空白、境界値の検査はない。CLI 引数や他の環境変数による値の上書きは、この setter にはない。

## 有効になる条件

- 通常の非同期化は `multi_gpu=false` のときに限り候補になる。コードでは `multi_gpu = !split_devs.empty() && !split_same` とし、`--split-skip-if-fits` が分割を取り消す経路もある（CUDA/HIP: `engine/src/program/generate.cpp:4856,6472-6493`、SYCL: `engine/sycl/src/program/generate.cpp:2333,3566-3586`）。
- `STRATA_COMMIT_SYNC` が設定されていれば、この単一 GPU 用の非同期化を止める。未設定でも `next_ != nullptr` の verifier chain では `commit` が待つため、非同期にはならない（CUDA/HIP: `engine/src/core/verify.cpp:4568-4575`、SYCL: `engine/sycl/src/core/verify.cpp:3197-3243`）。
- commit graph 自体を実行しない一 token の self-commit 経路では、この変数による待機の違いはない（CUDA/HIP: `engine/src/core/verify.cpp:4537-4540`、SYCL: `engine/sycl/src/core/verify.cpp:3171-3173`）。
- Metal の `commit` は `STRATA_GPU_METAL` 分岐から `metal_engine::window_commit` に直接委譲され、`wait_commit` も成功を返すため、確認した `g_commit_async` の待機分岐は通らない（`engine/src/core/verify.cpp:4527-4530,4597-4601`）。
- ソース上の読み取りは CUDA/HIP と SYCL の verifier にあり、OS、サーバーモード、モデル状態による追加の環境値判定はない。サーバーや通常生成での違いは、生成初期化時に決まる `multi_gpu` と verifier chain による。

## 実行時の詳細

環境値は各 backend の `set_commit_async` 呼び出し時に一度調べ、結果を `g_commit_async` に保存する。commit ごと・リクエストごとに `getenv` を再評価するコードはない。`generate` は `multi_gpu` を確定した後に setter を呼び、その後の verifier の commit がこの状態を参照する（CUDA/HIP: `engine/src/program/generate.cpp:6493`、SYCL: `engine/sycl/src/program/generate.cpp:3586`）。

同期経路では CUDA/HIP は `cudaGraphLaunch` 後に `cudaStreamSynchronize`、SYCL は graph enqueue 後に `cs_->wait()` を行う。非同期経路では commit 完了 event を記録して pending 状態にし、後続の `wait_commit` がその event を待つ。コードコメントは、同じ stream 上の次 window と独立した drafter が処理を進められる一方、別 stream や host から session を読む前には待つ設計を示す（CUDA/HIP: `engine/src/core/verify.cpp:4562-4575,4597-4608`、SYCL: `engine/sycl/src/core/verify.cpp:3174-3244,3259-3269`）。生成側も request 間や run 終了前の session 読み取りに `wait_commit` を呼ぶ（CUDA/HIP: `engine/src/program/generate.cpp:19150-19153,23346-23349,25250-25253`、SYCL: `engine/sycl/src/program/generate.cpp:10775-10780,12952-12955,14233-14237`）。

## ログと測定値

この変数の設定・未設定を知らせる専用ログは見つからない。CUDA/HIP の commit graph 起動失敗は `verify: commit launch: ...`、同期失敗は `verify: commit: ...`、非同期 event 記録失敗は `verify: commit event: ...` を `err` に設定して失敗を返す。SYCL も同じ prefix のエラーを返し、`wait_commit` 中の `sycl::exception` は `record_verify_sycl_exception("wait_commit", ...)` に渡す（CUDA/HIP: `engine/src/core/verify.cpp:4562-4573,4597-4608`、SYCL: `engine/src/core/verify.cpp:3189-3214,3223-3243,3259-3269`）。生成側の一部経路では失敗時に `ERR <err>` または `strata generate: <err>` を出して終了する（例: `engine/src/program/generate.cpp:23346-23350,25250-25254`）。この変数に関する条件付き測定値は確認できなかった。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:860`。
- 環境値を読む全実装: `engine/src/core/verify.cpp:4525`、`engine/sycl/src/core/verify.cpp:3162`。他に同名があるのはコメント・宣言と `terminal/data/settings-register.json` の登録情報であり、環境値の読み取り箇所ではない。
- setter の呼び出しと multi-GPU 判定: `engine/src/program/generate.cpp:4856,6493`、`engine/sycl/src/program/generate.cpp:2333,3586`。
- commit の同期・非同期分岐と待機・失敗処理: `engine/src/core/verify.cpp:4527-4575,4597-4608`、`engine/sycl/src/core/verify.cpp:3164-3244,3259-3269`。
