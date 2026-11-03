# `STRATA_BATCH_DF2_DEFER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--serve` のバッチ DFlash2 で、slot に draft row が割り当てられなかった window の後処理を切り替えます。既定ではその window の tap row を保留し、slot に draft row が戻るまで DFlash2 drafter の処理を遅らせます。値の先頭が `0` のときは保留せず、その window の committed row から DFlash2 の draft を作ります。

この設定はバッチ DFlash2 自体を有効にするものではなく、slot drafter の起動条件や verifier row 数も変えません。

## 値と判定

環境変数は `main` のバッチ用状態を初期化するときに一度読みます。文字列全体や数値としての妥当性は検査せず、先頭文字だけを見ます。空文字は設定済みですが、先頭が `\0` なので保留が有効です。

| 値 | 判定 |
|---|---|
| 未設定 | 保留する（既定） |
| 空文字 | 保留する |
| 先頭文字が `0` | 保留しない。`0`, `0abc` など |
| それ以外 | 保留する。`1`, `false`, `abc` など |

大文字小文字、空白、後続文字は判定に影響しません。`atoi` などの数値変換、無効値の fallback、clamp はありません。`--batch`、`--spec` などの CLI 引数がこの値判定を上書きする分岐もありません。

根拠: `src/program/generate.cpp:13600-13605`。

## 有効になる条件

設定の効果が現れるには、DFlash2 機能を含むビルド（`STRATA_HAVE_DFLASH2`）で `batch_df2` が有効になり、batch window の処理が走る必要があります。通常の有効化経路は `--serve`、`--batch` 2 以上、`--draft dflash2`（`--draft auto` ではない）、同一 GPU 上の layer split ではないことです。`STRATA_BATCH_DF2` が先頭 `0` なら無効で、非空かつ先頭が `0` 以外なら強制有効を要求します。未設定または空文字では、層分割があり batch groups が 1 以下の場合に有効になります。さらに、`--spec` 2 以上、native pack と `--draft-model` が必要で、`--pipeline-windows` とは併用できません。層分割では slot を serial window にする条件もあり、既定では複数 group に pipelined される構成は batch DFlash2 の対象になりません。Metal では `batch_df2_wanted` を常に false にします。

これらの条件を満たさない場合、この環境変数を設定しても DFlash2 の slot draft には影響しません。DFlash2 が起動せず fallback になった場合も batch DFlash2 は有効にならず、当該環境変数の分岐は実行されません。

根拠: `src/program/generate.cpp:6464-6481,6765-6772,6820-6840,11185-11197`。

## 実行時の詳細

`batch_step` は active slot ごとの verifier row を組み立てます。DFlash2 の slot に与える余剰 row 数は、window 容量から active slot 数を引いて分配し、drafter の上限、残り生成長、最大 context、`STRATA_BATCH_DF2_MAXX`、`STRATA_BATCH_DF2_CONF` によってさらに制限します。そのため `nrow[t] == 1` は、その slot にこの window の draft row が割り当てられなかった状態です。これは active slot が多く余剰 row がない場合のほか、上記の上限や確信度条件で row 数が 0 になった場合も含みます。

`STRATA_BATCH_DF2_DEFER` が保留を有効にしていると、window の実行・commit 後に、その slot の committed row の tap を host 側の deferred buffer に保存し、`draft_ready` を false にします。余剰 row が後続 window で割り当てられると、保留 tap を drafter に反映して slot の現在位置まで追いつかせ、最新 token から draft を作ってから verifier rows を組み立てます。保留が無効（値の先頭が `0`）なら、row が割り当てられなかった window でも直ちに catch-up、tap の gather、draft launch を行います。

環境値は `const bool` としてこの batch 状態の初期化時に保存され、各 batch window やリクエストごとには再読込しません。コード上に実行中の再評価や子プロセスへの転送はありません。

保留時の pinned host buffer 確保に失敗すると `ERR batch DFlash2 slot ...` を stdout に出して batch 処理が失敗します。後続の catch-up が失敗した場合は stderr に `strata batch: DFlash2 slot ...: catch-up failed (...): no drafts for it this round` と出し、その round の draft を見送ります。通常の保留モードでは batch の集計 stderr 行に deferred row 数と catch-up 数・行数・時間が出ます。環境変数そのものの有効・無効を知らせるログはありません。

根拠: `src/program/generate.cpp:13884-13935,14084-14116,14205-14212`; `src/core/dflash2.cpp:620-663`。

## 根拠

- 読み取りと値判定: `src/program/generate.cpp:13600-13605`。
- バッチ DFlash2 の有効条件と slot drafter の準備: `src/program/generate.cpp:6464-6481,6765-6772,6820-6840,11185-11197`。
- spare row の算出と保留 tap の次 window での catch-up: `src/program/generate.cpp:13884-13935`。
- row 不足時の保留／即時 draft、およびエラー経路: `src/program/generate.cpp:14084-14116`。
- 保留行 buffer と catch-up の処理: `src/core/dflash2.cpp:620-663`。
- 保留・catch-up 集計ログ: `src/program/generate.cpp:14205-14212`。

