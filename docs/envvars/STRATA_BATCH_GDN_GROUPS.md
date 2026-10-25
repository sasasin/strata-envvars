# `STRATA_BATCH_GDN_GROUPS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の batch window を処理する GPU verifier で、GDN（gated delta network）の再帰計算を複数 slot 分まとめて一つの kernel launch にします。対象は window 内の各 slot の状態と行グループで、各グループの行計算は個別 launch の経路と同じ kernel 算術を使います。通常の batch window と、window 後に行う 1 行 commit の両方に分岐があります。

## 値と判定

両方の読み取り箇所で `std::getenv()` の値を `std::atoi(v) != 0` で判定します。文字列全体の数値 parse や妥当性検査はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| `1`、`-1`、`2`、`1junk`、` 1` | 有効（`atoi` の結果が 0 以外） |
| `0`、`0junk`、`true`、`junk` | 無効（`atoi` の結果が 0） |

読み取り箇所は `record_window()` 内の batch GDN 経路と `capture_commit_batch()` 内の commit 経路にそれぞれあります。各値は別々の関数内 `static const bool` に保存され、その経路が最初に実行されたときに一度だけ評価されます。各 static の初回評価後に環境を書き換えても、その経路の値は変わりません。

## 有効になる条件

- batch window の GDN 再帰では `record_window()` が batch-recording 中（`batch_rec_`）であり、環境値が有効で、処理中の連続行範囲 `te - tb` が 8 以下であることが必要です。ここでは同じ slot の連続行を一グループにまとめ、グループごとの状態を `GdnGroups` に渡します。
- commit 経路では `capture_commit_batch()` の対象 layer が GDN であり、値が有効で、window が 8 行以下かつ各行が異なる slot に属する場合に使います。この経路は `one_row` を `S <= 8` と隣接 slot 重複なしで判定します。window の検証は同じ slot の行を連続 group に限るため、ここでの隣接 slot 重複なしは各行が別 slot であることを意味します。ソースコメント上の対象は `--batch-mtp` の proposal 行がない 1 行グループです。
- いずれも GDN layer のみです。QSA layer の処理はこの設定で変わりません。GDN の convolution 計算・履歴 commit はグループごとに先に実行され、まとめられるのは recurrence と出力 norm の呼び出しです。
- 8 を超える行またはグループ条件を満たさない場合、変数が有効でも既存の `gdn_step_norm_multi()` をグループ単位で呼ぶ経路に進みます。

## 実行時の詳細

batch window では、各 GDN layer の行を slot ごとの連続グループに分けて convolution を計算した後、条件を満たせば状態ポインタ、グループ先頭行、行数を `GdnGroups` に詰めて `gdn_step_norm_groups(..., commit=false, ...)` を一度呼びます。そうでなければ、各グループについて `gdn_step_norm_multi()` を個別に呼びます。group kernel の入力構造体は最大 8 グループを持ちます。

commit graph では各 slot の convolution 履歴 commit を行った後、1 行ずつの recurrence を `GdnGroups` に集め、`gdn_step_norm_groups(..., commit=true, ...)` を呼びます。条件外では各 slot group に対して `gdn_step_norm_multi()` をその場で呼びます。batch window 自身が commit を保持する経路（`STRATA_BATCH_SELF_COMMIT` が有効で、各行が別 slot）では commit graph が起動されないため、この commit 側の分岐は実行されません。

有効・無効を知らせる専用ログはこの変数の読み取り箇所にはありません。kernel wrapper は不正なグループ引数を受け取ると stderr に `gdn_step_norm_groups: invalid arguments` または `gdn_step_norm_groups: invalid group %d` を出して終了します。

## 文書との照合

Strata の `docs/BATCHING.md` は既定 OFF とし、window recurrence と 1 行 group commit を全 slot の一 launch にまとめること、convolution commit は slot ごとであることを説明しています（`docs/BATCHING.md:476-489`）。値の既定判定、上限 8、個々の call 条件は本調査の実装を根拠に記載しました。同資料は特定の RTX PRO 6000 Blackwell / IQ3_S / HTTP server / batch 条件で測定値も載せていますが、その値は資料記載の測定結果であり、本調査では再測定していません（`docs/BATCHING.md:491-505`）。

## 根拠

- `src/core/verify.cpp:1387-1419` — batch window の設定値読み取り、最大 8 行の条件、グループ launch と個別 fallback。
- `src/core/verify.cpp:3289-3358` — commit graph の構築、GDN 1 行 group の条件、convolution commit と recurrence の分岐。
- `src/core/verify.cpp:3458-3484,3674-3680` — batch window の記録・commit graph 呼び出しと、self-commit 時の commit graph 省略。
- `include/strata/core/batch_rows.hpp:4-7,16-27` — slot ごとの行が連続 group であることと layout validation。
- `include/strata/kernels/verify_kernels.hpp:38-54` — `GdnGroups` の用途と 8 group 上限、同一算術との API 説明。
- `src/kernels/cuda/verify_kernels.cu:1083-1104` — group kernel wrapper の引数検証、launch、stderr エラー。
- `docs/BATCHING.md:476-505` — Strata の説明と測定条件。
