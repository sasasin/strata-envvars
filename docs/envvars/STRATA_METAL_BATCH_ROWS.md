# `STRATA_METAL_BATCH_ROWS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの batch decode で、複数 slot の行を一つの window としてまとめて実行する経路を選びます。既定では複数行対応の `run_rows()` を使います。`STRATA_METAL_BATCH_ROWS=0` にすると、各行を slot ごとに 1 token 実行し、その都度 commit する経路に切り替わります（`metal/src/engine/window.cpp:1781-1797`）。

この環境変数を読むのは Metal エンジンの `Window::run_slots()` です。Metal CMake プロジェクトで `STRATA_METAL_ENGINE` が有効なときに `metal/src/engine/*.cpp` がエンジンへ組み込まれます（`metal/CMakeLists.txt:73-77,110-130`）。CUDA、HIP、SYCL の同名変数読み取りは確認できません。

## 値と判定

文字列全体を `"0"` と比較します。数値変換はありません。

| 値 | `one_window` | 結果（`bigs_ok_` も真の場合） |
|---|---:|---|
| 未設定 | true | `run_rows(rows, S, ...)` で batch 行をまとめて実行 |
| 空文字 | true | 同上 |
| 完全一致の `0` | false | 各行について `run(1, ...)` の後に `commit(1, ...)` |
| その他すべて（`00`, `0 `, `false`, `1` など） | true | `run_rows(rows, S, ...)` で batch 行をまとめて実行 |

値は `Window::run_slots()` 内の関数ローカル `static const bool` に保存されます。最初にこの関数が呼ばれた時点で一度だけ評価され、その後プロセス内で環境を書き換えても再評価されません。batch 経路を通らない実行では読み取りません（`metal/src/engine/window.cpp:1781-1784`）。

## 有効になる条件

- Metal エンジンで batch slots が初期化され、`Verifier::run_slot_rows()` から Metal の `window_run_slots()` が呼ばれることが必要です。Metal の `Verifier::init_slots()` は slot を初期化し、batch run は `run_slot_rows()` から window に渡します（`src/core/verify.cpp:3696-3719,4394-4404`）。通常の生成側は `--batch` の値を `set_batch_slots()` に渡します（`src/program/generate.cpp:4039-4042`）。
- まとめて実行する分岐には `bigs_ok_` も必要です。これは window 初期化時に `g_slot_cap > 0` で始まり、`g_slot_cap` は `set_batch_slots(n)` により `n > 0` なら最大 8 に制限されます。slot 数が cap を超えると `slots_init()` が `bigs_ok_` を false にします。この場合、環境変数が未設定または `"0"` 以外でも逐次経路になります（`metal/src/engine/window.cpp:91-93,608-621,1751-1763,2921`）。
- `run_rows()` は `S` が 1 以上、`MAXT` 以下、かつ `max_t_` 以下であることを要求します。Metal window の `MAXT` は 8 です（`metal/src/engine/window.cpp:93,1359-1361`）。

## 実行時の詳細

まとめて実行する経路は `rows[]` の各 slot を `rows_set_` に対応付け、`run(S, ...)` を一度呼びます。`finish_rows()` が各 slot の履歴 parity と PLE 状態を更新します（`metal/src/engine/window.cpp:1359-1381,1384-1405`）。一つの window に同じ slot が複数回現れる場合や存在しない slot が指定された場合は `run_rows()` が失敗し、それぞれ `metal window: two rows of one batch window are the same slot`、`metal window: a batch row names a slot that does not exist` を `err` に設定します（`metal/src/engine/window.cpp:1364-1368`）。

逐次経路は各行の slot を activate し、`run(1, ...)` と `commit(1, ...)` を順に行います。同じ slot が複数行にあってもこの分岐では重複チェックを行いません。slot 番号が不正なら `metal window: a batch row names a slot that does not exist` を返し、`run()` または `commit()` の失敗もそのまま伝播します（`metal/src/engine/window.cpp:1788-1797`）。

環境変数の値だけを理由に出すログや警告はありません。batch slot 初期化時には `strata metal: %zu batch slots...`（`metal/src/engine/window.cpp:1768-1769`）、Verifier 初期化時には `strata verify: batch windows of up to %d sequences, run slot by slot in the Metal window`（`src/core/verify.cpp:3718`）が stderr に出ます。後者は環境変数で実際に選択された経路を報告するものではありません。上記の失敗は呼び出し元へ `false` と `err` を返します。

## 根拠

- 候補名の全参照を Strata リポジトリ全体で `rg -n --hidden --glob '!.git/**' 'STRATA_METAL_BATCH_ROWS'` で確認し、実行時読み取りは `metal/src/engine/window.cpp:1783` の 1 箇所でした。動的な helper 経由の参照はありません。
- 値判定、読み取り時期、分岐、行・slot の検査: `metal/src/engine/window.cpp:1359-1381,1751-1763,1781-1797`。
- batch slot の有効条件と verifier からの呼び出し: `src/program/generate.cpp:4039-4042`, `src/core/verify.cpp:3696-3719,4394-4404`。
- Metal エンジンの build 条件とソース組み込み: `metal/CMakeLists.txt:73-77,110-130`。
