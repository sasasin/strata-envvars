# `STRATA_CKPT_THREADS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve` の会話チェックポイント保存で、layer split の各 GPU stage が持つ状態を並行して保存します。通常は stage ごとに同期と保存を順番に行います。有効時は最初の stage を呼び出しスレッドで処理し、後続 stage を専用の永続スレッドで同時に処理し、全 stage の完了を待ちます。チェックポイントの内容や保存先の意味を変える設定ではなく、保存処理のスケジュールを変える設定です。

## 値と判定

初回の判定結果を関数内の `static const bool` に保存します。`getenv()` の値の先頭文字だけを確認し、数値や真偽値として全体を parse しません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効（設定値が存在し、先頭文字が `\0`） |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外 | 有効（例: `1`, `true`, `false`, 空白で始まる文字列） |

大文字小文字、後続文字、数値としての妥当性は調べません。プロセス内で初めて `ckpt_threads_env()` が呼ばれたときに判定し、その後の環境変更では再評価しません。

## 有効になる条件

- `strata serve` の会話キャッシュでチェックポイントを新規保存する経路で使われます。保存先の token 位置が既存チェックポイントと重複する場合や、`--prompt-cache` が無効、保存位置 `L` が 1 未満の場合は保存処理自体がありません。
- `checkpoint_at()` に stage ごとの保存済み部分 (`parts`) が渡された場合、この環境変数による並列保存分岐は通りません。コード上、layer split の prompt chunk で各 stage が個別に作った部分を組み立てる経路がこれに当たります。
- 後続 stage がない場合、並列化する仕事がないため追加スレッドは作られません。
- `STRATA_CKPT_POOL` が無効でも、この変数が有効なら stage ごとのチェックポイント保存分岐を使います。逆に `STRATA_CKPT_POOL` だけが有効で本変数が無効なら同じ分岐で保存しますが、stage の処理は順次実行されます。プールによる領域再利用と、この変数による並列化は別の効果です。

## 実行時の詳細

チェックポイントを一括保存する経路では、stage 数に先頭側の session を加えた件数だけ保存 job を作ります。各 job は担当 device を選び、`cudaDeviceSynchronize()` 後に `checkpoint_save()` を実行します。環境変数が有効なら `StageThreads::run()` が job 0 を呼び出しスレッドで実行し、job 1 以降を stage ごとの永続スレッドで実行してから、すべての job の終了を待ちます。各 stage の同期・保存に失敗した場合は、通常のチェックポイント失敗経路に戻ります。

追加スレッドは `StageThreads` オブジェクトの寿命中に保持され、初回の並列実行時に必要数が作られます。Linux ではスレッド開始時に CPU affinity を広げた後、`strata::aux_cpus::pin_current_thread()` を呼びます。同 helper は aux CPU 機能が無効なら何もしません。Linux 以外ではこの affinity 処理はコンパイルされません。

`STRATA_TRACE` が設定されている場合、チェックポイントごとの診断ログに stage 数と `at once` が出ます。本変数単独で有効化を知らせるログはありません。失敗時は保存・GPU 同期の既存エラー経路が使われます。

## 根拠

- 値の判定と初回キャッシュ: `src/program/generate.cpp:202-210`。
- stage 保存用スレッドの起動、全 job の完了待ち、Linux affinity 処理: `src/program/generate.cpp:1736-1800`。
- checkpoint 保存の条件、`parts` 経路の除外、pool との分岐、同期・保存 job、逐次/並行の選択、trace 表示: `src/program/generate.cpp:9095-9175`。
- prompt chunk の stage 部分を組み立てる経路: `src/program/generate.cpp:9310-9346`。
- 関連資料 `docs/BATCHING.md:110-120` は `STRATA_CKPT_POOL` と本変数を同じ表行に記載し、「split's stage parts are saved at once」と説明しています。ソースでは pool の有効化と本変数の有効化は独立しており、並列実行を選ぶのは本変数の判定です。性能値の記載はありません。
