# `STRATA_CKPT_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の会話 checkpoint 保存で、層分割された各 GPU stage の状態を同時にコピーするための opt-in スイッチです。stage 0 は呼び出しスレッドで保存し、後続 stage はそれぞれ専用の worker thread で保存します。コード上、保存対象の checkpoint 状態やコピー関数は通常経路と同じで、変わるのは stage ごとの同期・保存の実行方法です（`engine/src/program/generate.cpp:14618-14650`）。

複数 stage がない場合は並列する後続 job がなく、実質的な並列化は起きません。値の判定結果は `ckpt_threads_env()` の関数内 `static` に初回評価時から保持されます（`engine/src/program/generate.cpp:550-559`）。

## 値と判定

`std::getenv` の戻り値が null でなく、かつ先頭文字が `'0'` でないとき有効です。文字列全体の比較や数値変換はありません。したがって、空文字、`1`、`true`、`false`、`off`、先頭が空白の ` 0` は有効、`0`、`00`、`0anything` は無効です。大文字小文字や後続文字は判定されず、未設定のみ無効です（`engine/src/program/generate.cpp:553-557`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `ckpt_threads_env()` の判定 | 無効 | 空文字、`1`、`true`、`false`、`off`、` 0` | `0`、`00`、`0anything` |

CLI 引数による値の上書きはありません。CLI の `--prompt-cache` は checkpoint 数を決め、0 以下なら保存自体を行わないため、この変数が有効でもその場合は効果がありません（`engine/src/program/generate.cpp:1086-1089, 14595-14598`）。

## 有効になる条件

- 対象は `generate.cpp` の `strata serve` checkpoint 処理です。呼び出し側では、`--prompt-cache` が正で checkpoint 位置 `L` が 1 以上であることが必要です（`engine/src/program/generate.cpp:14595-14598`）。
- 実際に複数 GPU stage がある場合に、stage 間で同時実行されます。stage 数 `n` に対し `run(n, ...)` は job 0 を呼び出しスレッドで実行し、job 1 から `n-1` を worker thread に割り当てます（`engine/src/program/generate.cpp:2666-2670, 2684-2701`）。
- checkpoint pool が有効なら、変数が未設定でも pooled checkpoint 用の保存経路に入り、stage は順次保存されます。この変数が有効なら、その経路を同時保存に切り替えます。pool が無効でも、この変数が有効なら同じ同時保存経路に入ります（`engine/src/program/generate.cpp:14604-14606, 14618-14620, 14649-14655`）。pool の有効化には `STRATA_CKPT_POOL` 等の別判定がありますが、この変数自体の値を上書きしません。
- 層分割の周期的な prompt checkpoint は各 stage が `on_stage_chunk` で自身の part を保存し、後で `checkpoint_at(done, &parts)` に渡します。この `parts != nullptr` 経路は part を組み立てて戻るため、`STRATA_CKPT_THREADS` の同時保存分岐を通りません（`engine/src/program/generate.cpp:14609-14617, 14857-14883, 14829-14841`）。したがって、すべての checkpoint 保存を並列化する設定ではありません。
- OS 固有の条件分岐は値判定や job の起動にはありません。Linux では worker の CPU affinity を調整する追加処理があり、Linux 以外ではその処理はコンパイルされません（`engine/src/program/generate.cpp:2703-2710`）。

## 実行時の詳細

最初に `ckpt_threads_env()` が呼ばれた時点で値を一度読み、static に保存します。以降にプロセス環境を書き換えても再評価されません（`engine/src/program/generate.cpp:553-559`）。

同時保存経路では、stage ごとに対象 device を選び、`cudaDeviceSynchronize()` が成功した後に `checkpoint_save()` を実行します。job 0 は呼び出し元、後続 stage は `StageThreads` 内の worker が担当し、全 job 完了を待ってから結果を検査します。thread は `StageThreads` が保持し、必要になった stage 数まで初回 `run` 時に作成され、同オブジェクトの破棄時に停止・join されます（`engine/src/program/generate.cpp:2677-2683, 2684-2701, 2713-2728, 14629-14662`）。

保存に失敗した場合、GPU 同期失敗は理由文字列 `: the GPU stopped responding before it (...) - a GPU hang; on Windows the driver is then reset` を設定します。呼び出し元で回復可能でない失敗または同期理由があると要求を失敗させます。コピーだけの回復可能な失敗は checkpoint を飛ばして要求を続けます（`engine/src/program/generate.cpp:14633-14637, 14659-14662, 14843-14850`）。

## ログと測定値

成功時に `STRATA_TRACE` が設定されていると、checkpoint ごとに stderr へ `strata trace: checkpoint at ...` の計測行が出ます。同時保存経路では stage 数に続いて ` at once` が表示され、stage ごとの時間と `into a dropped checkpoint's vectors` または `new vectors` が出ます。`STRATA_TRACE` が未設定ならこの計測行は出ません（`engine/src/program/generate.cpp:14579-14585, 14663-14678`）。

保存を飛ばす回復可能な失敗では stderr に `strata serve: checkpoint at ... skipped: its state could not be copied out (see above); the request goes on without it` が出ます。stage ごとの周期保存失敗には stage 番号付きの別文言があります（`engine/src/program/generate.cpp:14868-14876, 14843-14850`）。資料には、この変数単体の性能測定値は確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:550-559` — 値の読み取りと static cache。
- `engine/src/program/generate.cpp:2666-2728` — stage worker の実行、待機、thread 寿命と Linux の affinity 処理。
- `engine/src/program/generate.cpp:14594-14662` — checkpoint 条件、pool/thread 分岐、stage ごとの同期・保存・失敗判定。
- `engine/src/program/generate.cpp:14663-14678` — `STRATA_TRACE` による成功時の計測行。
- `engine/src/program/generate.cpp:14829-14850` — 層分割の周期 checkpoint 経路と回復可能失敗時のログ。
