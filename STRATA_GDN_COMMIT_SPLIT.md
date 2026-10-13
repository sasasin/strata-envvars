# `STRATA_GDN_COMMIT_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

GDN（gated delta rule）の検証 commit で、出力を計算せず状態だけを更新する専用 CUDA kernel `gdn_step_commit_kernel` を選びます。通常の検証計算 kernel から commit の仕事を分け、commit 専用 kernel は state の更新だけを行います。これは Strata の CUDA カーネル内の分岐で、環境変数自体について `docs/DETAILS.md` に説明はありません。

## 値と判定

`std::getenv()` の結果の先頭文字だけを調べます。文字列全体の parse、数値変換、大文字小文字の判定はありません。

| 値 | 判定 |
|---|---|
| unset | 有効 |
| 空文字 | 有効（値は設定済みだが先頭文字が `\0`） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外（例: `1`, `true`, `false`, `2`, `x`） | 有効 |

判定結果は `gdn_step_norm_multi()` 内の関数ローカル `static const bool` に保存されます。その翻訳単位のプロセス内で初回にこの判定箇所へ到達した時に評価され、その後に環境を書き換えても反映されません。

根拠: `src/kernels/cuda/verify_kernels.cu:1020-1023`。

## 有効になる条件

環境変数の判定が有効であっても、専用 kernel を呼ぶには `n_keep != nullptr` かつ `t_out_begin >= n_tok` が必要です。これは出力なしの commit 呼び出しに対応します。条件を満たさない場合は通常の GDN kernel 経路へ進みます。

先行する `STRATA_GDN_SPLIT` 分岐には注意が必要です。`STRATA_GDN_SPLIT` が先頭文字 `1` で、かつ `(t_out_begin >= n_tok || n_tok - t_out_begin >= 2)` が成り立つと、その分岐が先に state-only replay kernel を起動して戻ります。この commit 経路では `STRATA_GDN_COMMIT_SPLIT` の判定箇所まで到達しません。したがって両方の分岐条件を満たす commit では `STRATA_GDN_SPLIT` 側が優先します。

呼び出し元では通常の `capture_commit()` が `n_keep=commit_`、`t_out_begin=MT` を渡し、batch commit も同様に `keep` と `t_out_begin=t - first`（行数と同じ値）を渡します。いずれも commit-only 条件を満たします。`STRATA_GDN_SPLIT` の値の既定設定は環境・アーキテクチャ別の処理に依存するため、この文書では `STRATA_GDN_COMMIT_SPLIT` 単独の既定動作と混同しません。

根拠: `src/kernels/cuda/verify_kernels.cu:1002-1024`; `src/core/verify.cpp:2002-2005,2651-2657`; `src/core/arch_defaults.cpp:32-57,61-69`。

## 実行時の詳細

専用 kernel は `n_keep` を device memory から読み、0 以下なら何も更新せず戻ります。正の行数について、各 GDN head の状態列を4つの block に分割して再帰を適用し、更新後の state を書き戻します。出力計算、norm、`z` や `y` の処理は行いません。CUDA 実装では `STRATA_DBG_GDN` の先頭文字が `1` の場合にだけ debug 版 kernel を選び、`n_keep > n_tok` なら commit を中止して診断文字列を出します。

この分岐で起動するのは `gdn_step_commit` で、GPU kernel 起動後のエラーチェック名も同じ文字列です。環境変数の値による警告や起動ログはありません。

根拠: `src/kernels/cuda/verify_kernels.cu:169-219,1024-1031`。

## 文書との照合

`docs/DETAILS.md` は `STRATA_GDN_CHUNKED` など別の GDN 最適化とその測定を説明していますが、`STRATA_GDN_COMMIT_SPLIT` の値判定、専用 commit kernel、性能測定は記載していません。そのため、この変数について速度向上や正確性の測定値は記載しません。

## 根拠

- 値の判定、優先分岐、起動: `src/kernels/cuda/verify_kernels.cu:1002-1047`
- state-only kernel の実装: `src/kernels/cuda/verify_kernels.cu:169-219`
- 通常 commit 呼び出し: `src/core/verify.cpp:1973-2005`
- batch commit 呼び出し: `src/core/verify.cpp:2631-2657`
- `STRATA_GDN_SPLIT` の gfx1151 既定値とユーザー指定の優先: `src/core/arch_defaults.cpp:32-69`
- 関連資料の GDN 最適化の説明: `docs/DETAILS.md:1668-1679`
