# `STRATA_DBG_GDN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の GDN（線形 attention）state commit カーネルにある診断ガードを有効にします。commit 対象数 `n_keep` がその verify window の行数 `n_max` を超えた場合、デバイス側の `printf` で異常値を出し、state の commit をスキップします。通常の GDN 計算を切り替える設定ではなく、異常な commit 数による state バッファ範囲外アクセスを避ける診断用フックです。

## 値と判定

環境変数の文字列全体や数値としての妥当性は解析せず、値が設定されていることと先頭文字だけを見ます。

| 値 | 診断ガード |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| その他 | 無効。例: `0`, `true`, ` 1` |

大文字小文字や後続文字は判定に影響しません。値の評価結果は `gdn_step_norm_multi()` 内の関数ローカル `static const bool` にキャッシュされます。プロセス起動時に必ず読むのではなく、後述する commit kernel 分岐に最初に入った時に評価し、その後の環境変更は反映されません。

## 有効になる条件

次の条件を満たす CUDA 経路でだけ参照されます。

- 呼び出しが `src/kernels/cuda/verify_kernels.cu` の `gdn_step_norm_multi()` に到達する。
- `STRATA_GDN_SPLIT` の state replay 分岐で先に return していない。
- `STRATA_GDN_COMMIT_SPLIT` が有効である。これは未設定なら有効、設定値の先頭文字が `0` なら無効。
- `n_keep != nullptr` で、`t_out_begin >= n_tok`（出力を作らず state を commit する呼び出し）である。

この分岐では `n_max` に `n_tok` が渡されます。`STRATA_DBG_GDN` が有効なら `gdn_step_commit_kernel<true>`、そうでなければ診断条件を持たない `gdn_step_commit_kernel<false>` が起動されます。ソース上の参照は CUDA カーネル実装だけにあり、HIP/SYCL 実装や通常の非 commit GDN 呼び出しでこの変数が使われる根拠は確認できません。

## 実行時の詳細

commit kernel は device memory から `n_keep` を読みます。`n <= 0` なら何もせず終了します。診断版で `n > n_max` の場合、grid の先頭 block/thread だけが次のメッセージを出し、全 block が state 更新を行わず終了します。

```text
strata DBG: gdn_step_commit: n_keep %d is past the window's %d rows: commit skipped (#937)
```

`n <= n_max` の場合は通常の state-only commit を実行します。非診断版では `n > n_max` を検査せず、通常の commit ループへ進みます。したがって、この変数は有効時に異常な件数の commit を防ぎ、無効時は既定の高速カーネル選択を保ちます。診断カーネルは CUDA device `printf` を使います（出力の表示タイミングや転送先の詳細は CUDA runtime 側の動作なので、ここでは断定しません）。

GDN commit は verify 呼び出しからも使われます。たとえば `src/core/verify.cpp` の通常 commit capture と batch commit capture が、`t_out_begin` を `MT` または複数行 group の長さにして `gdn_step_norm_multi()` を呼びます。生成経路では、`self_commit` が真の場合に `n_keep` を渡す呼び出しがあります。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:169-185`: state-only commit kernel、`n_keep > n_max` の診断、メッセージ、commit skip。
- `src/kernels/cuda/verify_kernels.cu:1002-1031`: 先行する split 経路、`STRATA_GDN_COMMIT_SPLIT` の判定、`STRATA_DBG_GDN` の先頭文字判定と static cache、kernel 選択。
- `src/core/verify.cpp:1162-1176`: GDN verify の recurrence 呼び出しと、条件付き `n_keep` 渡し。
- `src/core/verify.cpp:1989-2005`: 通常 commit capture から `t_out_begin = MT` と commit pointer を渡す経路。
- `src/core/verify.cpp:2631-2657`: batch commit capture の GDN commit 呼び出し。
- `docs/DETAILS.md`: `STRATA_DBG_GDN` の挙動について対応する説明は見つかりませんでした。
