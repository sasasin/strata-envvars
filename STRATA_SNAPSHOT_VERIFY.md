# `STRATA_SNAPSHOT_VERIFY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

MTP（draft model）を使用中に、プロンプト処理経路を通ったことを示す診断行を出し、会話キャッシュから parked conversation を復元した直後に draft 層の K/V snapshot と GPU 上の K/V を照合するデバッグ用スイッチ。通常の生成処理や snapshot の保存・復元そのものを有効化する変数ではない。

## 値と判定

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | 診断行と復元後の照合を行わない |
| 設定あり（空文字、`0`、その他の文字列を含む） | 設定ありとして扱う |

値の文字列比較や数値変換は行わず、`std::getenv(...) != nullptr` で存在だけを調べる。

## 有効になる条件

- CUDA と SYCL のエンジン実装に参照がある。
- `DRAFT_PREFILL` 行は `use_mtp` が真で、`sp.on_chunk` が実行される場合に出る。変数が設定されていても MTP が使われなければ出ない。
- `SNAPSHOT_VERIFY` の照合は、会話キャッシュから `incoming` conversation を復元する経路で、かつ `use_mtp` が真の場合だけ実行される。snapshot の復元後に draft K/V image を選び、GPU 側の draft 状態と照合する。
- セッションファイルの復元経路（`conversation_snapshot_restore(image, ...)`）にはこの変数を使った照合がない。通常の snapshot 機能や conversation cache の有効化条件は `--conversation-cache-mib`、`--conversation-cache-slots` 等の別設定による。

## 実行時の詳細

環境変数はプロセス環境から各該当箇所で直接読み取られ、値を static cache する処理はない。MTP を使う prompt chunk の処理後には stderr に `strata serve: DRAFT_PREFILL path=... mode=... cells=...` を出す。`path` は `batched` または `token`、`mode` は K/V mode、`cells` にはその chunk の `T` が出力される。この行は prompt 側の MTP 経路の診断であり、それ自体は snapshot byte 照合の結果ではない。

会話キャッシュの parked conversation を復元した後、`conversation_kv_verify` が snapshot に保存された K/V、scale、pooled buffer のバイト列を最大64 KiBずつ GPU から読み戻し、image と比較する。`kv_mode == 2` の場合は、resident ring の該当ページも照合する。検証が成功すると stderr に `strata serve: SNAPSHOT_VERIFY draft=... cells=... mode=... source=ram resident=...` を出し、`draft` は照合対象 bytes の fingerprint である。照合や read-back に失敗した場合は stdout に `ERR verifying restored draft KV: ...` を出して、その処理は `return 1` で終了する。バイト不一致時のエラー文字列は `conversation snapshot: restored K/V bytes differ`。

## 文書との照合

`docs/DETAILS.md` は会話キャッシュが parked state、使用済み K/V pages、draft-layer K/V を snapshot に含め、復元後に再利用できる旨を説明している。環境変数による read-back 検証の説明は同節にはない。`tools/parking_test.py` はこの変数を値 `1` で子エンジンに渡し、`SNAPSHOT_VERIFY` 行の有無をログから確認する。ただし、実装は `1` との比較をせず、設定の有無で動作する。

## 根拠

- `src/program/generate.cpp:8199-8201` — MTP prompt chunk 後の `DRAFT_PREFILL` 行。
- `src/program/generate.cpp:10491-10525` — parked conversation 復元後の MTP 条件、K/V 照合、成功・失敗時の出力。
- `src/core/conversation_snapshot.cpp:257-297` — snapshot と authoritative K/V bytes、必要時の resident ring を照合して fingerprint を作る実装。
- `sycl/src/program/generate.cpp:7729-7732`, `9751-9777` と `sycl/src/core/conversation_snapshot.cpp:281-322` — SYCL 側の対応する診断・復元後照合実装。
- `src/program/generate.cpp:10065-10115` — session file の読み込み・復元経路。ここでは `STRATA_SNAPSHOT_VERIFY` による照合をしていない。
- `docs/DETAILS.md:974-1004` — conversation cache の利用条件と snapshot 内容。
- `tools/parking_test.py:36-59` — テストツールが変数を設定し、復元後のログ行を確認する例。
