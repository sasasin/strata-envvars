# `STRATA_DBG_GDN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の GDN verify commit に境界診断を有効にする開発・診断用スイッチです。値が有効だと、state-only commit カーネルで device memory 上の `n_keep` が窓の行数を超えている場合に診断を出し、GDN の recurrence state 更新をスキップします。また、複数 GDN レイヤーを一括 commit する経路を選ばず、レイヤーごとの commit に戻します。通常の GDN 計算や生成 token の選択を切り替える設定ではありません。根拠: `engine/src/kernels/cuda/verify_kernels.cu:211-225,1231-1252,1357-1364`、呼び出し側 `engine/src/core/verify.cpp:3445-3469,3498-3520`。

## 値と判定

どちらの読み取りも C++ の `std::getenv` で値の先頭 1 文字だけを `'1'` と比較します。文字列全体の parse、数値妥当性検査、大文字小文字変換、空白除去はありません。

Strata の該当呼び出しはこの値を CLI 引数や設定ファイルから上書きしません。カーネル実装がプロセス環境から直接読みます（`engine/src/kernels/cuda/verify_kernels.cu:1235-1240,1357-1362`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `gdn_commit_layers` の一括可否判定 | debug 条件は false | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `true`, ` 1`, `2` |
| state-only per-layer commit の診断 | debug 条件は false | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `true`, ` 1`, `2` |

ここでいう「有効」は各コード位置での判定結果です。実際に診断が出るには後述の commit 経路にも入る必要があります。読み取り箇所: `engine/src/kernels/cuda/verify_kernels.cu:1235-1240,1357-1362`。

## 有効になる条件

- 対象の実装は `engine/src/kernels/cuda/verify_kernels.cu` の CUDA/HIP カーネルです。CUDA engine のソース一覧にも同ファイルが含まれます（`engine/cmake/strata_gpu_engine.cmake:92-97`）。この変数名を読む Strata 所有コードはこのファイルの 2 箇所で、Metal/SYCL の読み取りは確認できませんでした。
- GDN の複数レイヤー一括 commit を試す呼び出しで `STRATA_DBG_GDN` の先頭が `1` だと、`gdn_commit_layers` は `per_layer` を true として `false` を返します。呼び出し側は GDN レイヤーごとのループへ進みます（`engine/src/kernels/cuda/verify_kernels.cu:1231-1244`、`engine/src/core/verify.cpp:3453-3469,3498-3520`）。この戻り値は GPU カーネルの失敗ではなく、一括経路を使わない選択です。
- 診断付きカーネルに入るには、`gdn_step_norm_multi` が `n_keep != nullptr` かつ `t_out_begin >= n_tok` で呼ばれ、かつ `STRATA_GDN_SPLIT` が先頭 `1` でないことが必要です。さらに `STRATA_GDN_COMMIT_SPLIT` が未設定、空文字、または先頭が `0` 以外である必要があります。後者が先頭 `0` の場合は state-only commit 分岐を迂回します（`engine/src/kernels/cuda/verify_kernels.cu:1326-1364`）。
- `STRATA_COMMIT_BATCH=0`（先頭文字が `0`）は verifier 側で一括 commit 呼び出し自体を無効にしますが、per-layer の `gdn_step_norm_multi` 呼び出しは残ります（`engine/src/core/verify.cpp:3445-3452,3502-3520`）。`STRATA_DBG_GDN=1` はこの経路でも診断値として読み直されます。
- 上記以外の経路（例: `STRATA_GDN_SPLIT` の分岐、`STRATA_GDN_COMMIT_SPLIT=0`、state-only commit でない呼び出し）では、値が `1` でもこの診断付きカーネルは実行されません。

## 実行時の詳細

最初の `gdn_commit_layers` 呼び出し時に関数内 `static const bool per_layer` が初期化され、`STRATA_GDN_SPLIT`、`STRATA_GDN_COMMIT_SPLIT`、`STRATA_DBG_GDN` を一度読みます。`gdn_step_norm_multi` 側の `split` と `commit_split` もそれぞれ関数内 static で初期化されます。`dbg` は state-only commit 分岐に入ったときだけ初期化されます。したがって、各 static の初期化後にプロセス環境を変更しても、その判定には反映されません（`engine/src/kernels/cuda/verify_kernels.cu:1235-1240,1326,1353-1358`）。

診断経路では GPU カーネルが `*n_keep` を読み、`n <= 0` なら何もせず戻ります。`n > n_tok` のときは block 0 の thread 0 が `strata DBG: gdn_step_commit: n_keep %d is past the window's %d rows: commit skipped (#937)` を出し、recurrence state の commit を飛ばします。`1 <= n <= n_tok` なら通常の `gdn_step_commit_body` を実行します（`engine/src/kernels/cuda/verify_kernels.cu:211-225`）。この診断カーネルは出力計算を行いません。

per-layer verifier 経路では recurrence state の commit より前に `gdn_conv_commit` が別カーネルとして呼ばれます。そのカーネルは `n_keep <= 0` を無視しますが、`n_keep > n_tok` の上限検査はありません。したがって、この変数の診断ガードが抑止するのは recurrence state 更新であり、同じ異常値に対する conv history 側の処理を保護するガードではありません（`engine/src/core/verify.cpp:3513-3520`、`engine/src/kernels/cuda/verify_kernels.cu:81-95,1225-1229`）。

## ログと測定値

異常値 `n_keep > n_tok` が診断カーネルまで到達した場合、カーネル内 `printf` による上記メッセージが出て recurrence state commit はスキップされます。これはホスト側の stderr 出力やプロセス終了を行うコードではありません。カーネル起動後の CUDA エラーは `check` が検出した場合に `what: error` 形式で stderr に出して `exit(1)` しますが、診断条件そのものは `check` エラーにしていません（`engine/src/kernels/cuda/verify_kernels.cu:37-40,1357-1364`）。この変数に関する測定値はありません。

## 根拠

- `engine/src/kernels/cuda/verify_kernels.cu:1231-1252` — 一括 commit の可否、環境変数の先頭文字判定、per-layer への fallback。
- `engine/src/kernels/cuda/verify_kernels.cu:211-225,1320-1380` — debug カーネル、読み取り/cache、起動条件、境界時の挙動。
- `engine/src/kernels/cuda/verify_kernels.cu:81-95,1225-1229` — conv history commit の値扱い。
- `engine/src/core/verify.cpp:3445-3469,3498-3520` — verifier の一括/per-layer 選択と commit の呼び順。
- `engine/cmake/strata_gpu_engine.cmake:92-97` — CUDA engine のコンパイル対象。
