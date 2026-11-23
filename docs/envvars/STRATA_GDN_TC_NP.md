# `STRATA_GDN_TC_NP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

CUDA の prompt GDN recurrence が tensor-core 経路を選び、通常の tensor-core scan の起動に失敗した後、split scan を再試行するときの積の分割数（NP）を選ぶ実験用設定です。`engine/src/prefill/kernels.cu` の `gdn_recurrence_impl()` が値を読み、`gdn_rec_tc(..., split=true, np=...)` に渡します（`engine/src/prefill/kernels.cu:3227-3236`）。

これは tensor-core 経路そのものを有効化するスイッチではありません。通常経路の最初の試行が成功すれば値は読まれず、split retry にも進みません。split kernel 内では NP=3 が各積を3段で計算し、NP=2 は出力だけの積を1段、状態更新に使う積を3段で計算し、NP=1 は全積を1段で計算します（`engine/src/prefill/gdn_tc.cuh:151-170`）。演算方法が変わるため結果の丸めも変わり得ますが、Strata のコードは NP=1/2 の出力・状態が NP=3 と同一になる保証をしていません。

## 値と判定

コードは `std::getenv` の結果を `std::atoi` で変換し、変換結果がちょうど `1` または `2` の場合だけ採用します。それ以外は `3` です。文字列全体の妥当性検査はなく、`atoi` が先頭から整数として読める部分を使います。空白や数値の後ろの文字も別途検査しません（`engine/src/prefill/kernels.cu:3233-3235`）。

| 条件 | unset | 有効になる値 | 無効値の例と結果 |
|---|---:|---|---|
| CUDA の split tensor-core retry が必要になった場合 | `3` | `1`, `2` | 空文字、`0`, `3`, `-1`, `true`, `x` は `3`。`1tail` は `1`、` 2tail` は `2` として扱われる |

この値は Linux CUDA の engine 既定値設定対象ではありません。`apply_gdn_defaults_cuda()` が設定するのは `STRATA_GDN_TC=1` と `STRATA_GDN_CONVL2=2` で、既存値は保持されます（`engine/src/core/arch_defaults.cpp:263-275`, `engine/src/program/generate.cpp:4405-4410`）。同じ helper による `STRATA_GDN_TC_NP` の既定値設定や上書きはありません。

## 有効になる条件

- CUDA build の `gdn_recurrence_impl()` を通ること。tensor-core dispatch は `#if !defined(__HIPCC__)` 内にあり、HIP ではこの読み取り・分岐を通りません（`engine/src/prefill/kernels.cu:3182-3190,3262-3267`）。
- 通常の自動 dispatch で `STRATA_GDN_TC` が `atoi` で非ゼロとなり、系列長 `T` が最低 `128` であること。Linux CUDA の `generate` 経路では未設定の `STRATA_GDN_TC` に `1` が補われます（`engine/src/prefill/kernels.cu:992,3186-3189,3227-3229`; `engine/src/core/arch_defaults.cpp:263-275`; `engine/src/program/generate.cpp:4405-4410`）。
- その通常の `gdn_rec_tc(... split=false ...)` 試行が失敗し、split retry に進むこと。成功時は `STRATA_GDN_TC_NP` を評価しません（`engine/src/prefill/kernels.cu:3227-3236`）。split retry も失敗すると、条件が合えば `STRATA_GDN_CHUNKED` の経路を試し、最後は key-head / pipelined / columns recurrence へ進みます（`engine/src/prefill/kernels.cu:3239-3255`）。
- `GdnProbe` が特定経路を強制していないこと。probe 強制時の tensor-core NP は force 値から `3`、`2`、`1` と決まり、この環境変数を使う自動 retry 分岐には入りません（`engine/src/prefill/kernels.cu:3190-3194,3203-3209`）。
- GPU が tensor-core 実装の実行条件を満たすこと。`gdn_rec_tc()` は compute capability 8 以上、必要な SM 数、経路に応じた shared memory、scratch 確保などを確認し、満たさない場合はエラーを返します（`engine/src/prefill/kernels.cu:1365-1384`）。この場合 split retry の可否も同関数で判定され、最終的に通常 recurrence に fallback し得ます。

## 実行時の詳細

値は `gdn_recurrence_impl()` 内の関数ローカル `static const int tc_np` です。起動時に必ず読むのではなく、自動 tensor-core 経路が `T >= 128` で通常試行に失敗し、最初に split retry へ到達したときに一度だけ評価・保存されます。その後の環境変更は同一プロセス内のこの値に反映されません。条件に到達しない実行では読み取り自体がありません（`engine/src/prefill/kernels.cu:3227-3235`）。

値は split retry の `gdn_rec_tc` に渡され、split scan kernel の NP テンプレート選択に使われます。NP=3 で2 tile の条件がそろう場合は2 tile の専用 kernel、それ以外は NP に応じた scan kernel が選択されます。出力 norm の融合が使える場合も NP=1/2/3 の scan specialization を選びます（`engine/src/prefill/kernels.cu:1405-1424`）。`STRATA_GDN_TC_FUSE` と `STRATA_GDN_TC_TILES` は `GdnTcNorm` の受け渡しや tile 選択に関係しますが、`STRATA_GDN_TC_NP` の値自体はこれらで変更されません（`engine/src/prefill/kernels.cu:3198-3202,1340-1355`）。

この設定に対応する CLI 引数、別環境変数からの値上書き、子プロセスへの個別転送は確認できません。Linux CUDA の engine 既定値 helper は NP 変数を触りません。呼び出しは prompt prefill 内の `gdn_recurrence()` から行われます（`engine/src/prefill/prefill.cpp:5209,9342`）。

## ログと測定値

この変数の値を表示するログ、無効値の警告、split retry の失敗理由を通常実行で出す処理はありません。失敗理由は test 用 `GdnProbe` がある場合にだけ記録されます。自動 dispatch では最終経路を選んで `check("gdn_recurrence")` を呼び、共通の kernel launch error を検査します。NP 専用の検証や終了処理はありません（`engine/src/prefill/kernels.cu:3229-3261,3271`; `engine/src/prefill/kernels.cu:1427-1431`）。

`docs/DETAILS.md` に `STRATA_GDN_TC_NP` の説明またはこの設定固有の測定値は見つかりませんでした。そこに記載された `STRATA_GDN_TC` の測定値を本変数の効果として転用していません。

## 根拠

- `engine/src/prefill/kernels.cu:3182-3199,3227-3269` — CUDA 条件、dispatch、値の読み取り、split retry と fallback。
- `engine/src/prefill/kernels.cu:992,1340-1355,1365-1425` — minimum T、tile selection、GPU eligibility と NP kernel selection。
- `engine/src/prefill/gdn_tc.cuh:151-170` — NP=1/2/3 が各積に適用する pass 数。
- `engine/src/core/arch_defaults.cpp:263-275`, `engine/src/program/generate.cpp:4405-4410` — Linux CUDA 既定値と環境上書き規則。
- `engine/src/prefill/prefill.cpp:5209,9342` — prefill からの呼び出し。
