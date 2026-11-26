# `STRATA_DF_PLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数行の verify window で PLE の key/value 投影後の処理を、行ごとのループではなく一括 CUDA kernel `native_ple_postops_batch_snap` で実行するための opt-in です。適用時は各行の hidden/residual、PLE history、および commit 用の行別 history snapshot を更新します。通常の行ごとの `ple_block_projected` と `ple_history_advance` の経路も残っており、条件を満たさない場合はそちらへ進みます（`engine/src/core/verify.cpp:1748-1752,1756-1792`）。

この切り替えは `--native-ple-postops`（または全 native 経路を有効にする `--native`）で native post-ops を有効にした場合にだけ到達可能です。環境変数単独では native post-ops を有効化しません（`engine/src/program/generate.cpp:3923,5164,6141`; `engine/src/kernels/cuda/ple.cu:202-205`）。

## 値と判定

verify 実装内の関数ローカル `static` 初期化で `std::getenv` の値を `std::atoi` に渡し、戻り値が 0 でなければ有効とします（`engine/src/core/verify.cpp:1748-1751`）。文字列全体の妥当性検査や `true` / `false` の比較はありません。`atoi` は先頭の空白と符号を許し、先頭の整数部分を読み、後続文字は無視します。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `atoi(e) != 0` | 無効 | `1`, `-1`, `2`, `1junk`, ` 1` | 空文字、`0`, `0anything`, `false`, `true`, 数字で始まらない文字列 |

`atoi` が認識する整数部分が 0 なら無効、0 以外なら有効です。したがって `-1` も有効で、`0anything` は無効です。大文字小文字の比較はありません。整数として表現できない範囲の入力に対する `atoi` の結果は、この実装から規定できません（同所）。

## 有効になる条件

`STRATA_DF_PLE` が有効値でも、次の条件をすべて満たした verify window の PLE 処理でのみ一括 post-ops が実行されます（`engine/src/core/verify.cpp:1482,1704-1710,1752`）。

- PLE が ready で、現在の層が PLE を実行する段階であること（`ple_on`; `engine/src/core/verify.cpp:1482,1698`）。
- PLE バッチ投影条件 `ple_batch_kv` が成立すること: `STRATA_PLE_BATCH` が未設定または先頭文字が `'0'` ではなく、`STRATA_DEC_BATCH` が有効で、グループに 2 行以上あり、key/value の BF16 重みがあり、native BF16 と native PLE post-ops が有効であること（`engine/src/core/verify.cpp:1489,1704-1710`）。`STRATA_DEC_BATCH` は未設定時有効、設定時は `atoi(value) != 0` です。`STRATA_PLE_BATCH` のここでの判定は「未設定または先頭文字が `0` 以外」であり、`0` 始まりなら無効です（同所）。
- `batch_rec_` が false であること。複数 slot の batch-recording 経路では `STRATA_DF_PLE` が有効でもこの一括 post-ops 分岐を使いません（`engine/src/core/verify.cpp:1752`）。
- 個別指定時は `--native-bf16-extra` が native PLE BF16 を有効にし、`--native-ple-postops` が post-ops を有効にします。どちらも既定では無効です。`--native` は両方を有効にします（`engine/src/program/generate.cpp:780-781,803,3914-3923,5162-5164,6116,6141`; `engine/src/kernels/cuda/ple.cu:202-205`）。
- 環境変数の判定自体には OS/backend 条件がありません。ただし実動作には `verify.cpp` と対応する `native_ple_postops_batch_snap` 実装を含むビルドが必要です。確認した実装は CUDA kernel です（`engine/src/core/verify.cpp:1748-1752,1766`; `engine/src/kernels/cuda/native_ple_postops.cu:275-289`）。

上記の一つでも満たさなければ、`STRATA_DF_PLE` の値による変更はなく、通常の逐次処理経路に進みます（`engine/src/core/verify.cpp:1772-1792`）。

## 実行時の詳細

変数の読み取りはプロセス起動時ではなく、`verify.cpp` の PLE 層で `ple_post_env` 初期化に初めて到達した時です。その値は関数ローカル `static const` に保存され、以降の verify window で環境を変更しても反映されません（`engine/src/core/verify.cpp:1698,1748-1751`）。同じ関数内の `dec_batch` も初回の verify 処理でキャッシュされます（同所:1489）。

条件成立時、まず前段で各行の key/value 投影を行い、hyper-connection residual write を行った後、バッチ kernel に key、hidden、value、PLE history、scratch、および行ごとの history snapshot バッファを渡します（`engine/src/core/verify.cpp:1718-1723,1756-1767`）。kernel は key と hidden の正規化、gate の計算、value の gate 適用、gated 値の正規化、history を使った convolution/residual、history 更新と各行後の snapshot 書き込みを launch します（`engine/src/kernels/cuda/native_ple_postops.cu:275-289`）。逐次経路では `ple_block_projected` の後に `ple_history_advance` し、commit 用 snapshot をコピーします（`engine/src/core/verify.cpp:1773-1792`）。

## ログと測定値

この環境変数を有効化したことを示す専用ログは、読み取り・分岐箇所にありません（`engine/src/core/verify.cpp:1748-1767`）。バッチ処理で例外が発生すると、呼び出し側は `err` に `verify PLE (window): ` と例外文字列を設定して `false` を返します。通常経路の例外は `verify PLE: ` を設定します（`engine/src/core/verify.cpp:1766-1770,1781-1790`）。測定値は記載できる根拠がありません。

## 根拠

- `engine/src/core/verify.cpp:1482-1489,1698-1717,1744-1792` — PLE の実行条件、補助環境変数、値の読み取り、分岐と fallback。
- `engine/src/program/generate.cpp:3923,5162-5164,5209-5211,6114-6117,6141` — CLI / `--native` による native PLE 設定。
- `engine/src/kernels/cuda/ple.cu:202-205` — native BF16 / post-ops フラグの保持。
- `engine/src/kernels/cuda/native_ple_postops.cu:275-289` — 一括 kernel が行う処理。
