# `STRATA_BATCH_DF2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` で DFlash2 を使う batch slot に、slot ごとの DFlash2 drafter を割り当てるかを制御する。通常の既定は、明示的に `--draft dflash2` と `--batch N`（`N >= 2`）を指定し、他の条件も満たす場合に slot drafts を有効にすること。`STRATA_BATCH_DF2=0` は無効化し、空でない別の値は通常の既定条件を一部強制する。これは DFlash2 自体を選択・ロードする設定ではなく、DFlash2 が起動した後に各 slot 用 drafter を追加する設定である（`engine/src/program/generate.cpp:7822-7842,8328-8348`）。

各 slot は DFlash2 の pack 等を共有し、専用の K/V ring と buffers を持つ。slot の batch window で余分な行が使える場合にだけ drafter が提案を作り、余分な行がない場合は drafter の計算をせず tap を保留して後で追いつく。この変数が制御するのは slot ごとの draft 処理であり、`--batch` の slot 数そのものではない（`engine/src/program/generate.cpp:8151-8159,17148-17171,17343-17374`）。

Terminal の `slot_drafts_run` と `slot_drafts_by_default` もこの変数を読み、drafting の判定・表示や Auto の drafter 選択に使う（`terminal/strata_control/drafting.py:964-970,1146-1164,1732-1743`）。これら Python 関数は文字列全体がちょうど `"0"` かを判定する一方、エンジンは先頭文字を見るため、`0anything` のような値では Python の表示・選択判定とエンジンの実判定が一致しない。

## 値と判定

エンジンは起動時の server 初期化中に `std::getenv` で一度読み、文字列全体を parse せず先頭文字で分類する。`e[0] == '0'` なら off、値が空でなく先頭が `0` 以外なら forced、未設定または空文字なら通常の既定条件に従う（`engine/src/program/generate.cpp:7828-7840`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| エンジンの DFlash2 slot 判定 | 通常の既定条件を使う | `1`, `true`, `false`, ` 1`, `2abc` は非空かつ先頭が `0` 以外なので条件を強制 | `0`, `0anything`, `00` は先頭が `0` なので off。空文字は unset と同じ通常の既定条件 |
| Terminal Python 判定 | 通常の既定条件を使う | `1`, `true`, `false`, `0anything` は `"0"` と完全一致しないため抑止しない | `0` だけが slot drafts を抑止 |

大文字小文字、空白、数値としての妥当性は検査されない。エンジンで `0anything` は off だが Terminal 側では off と扱われず、Terminal の `Drafting:` 表示や Auto の選択と起動したエンジンの実動作が食い違う可能性がある（`terminal/strata_control/drafting.py:964-970,1155-1164`）。

## 有効になる条件

- 実行経路が server の batch slot 処理であること。エンジン条件に `o.serve` と `o.batch >= 2` が含まれる（`engine/src/program/generate.cpp:7835`）。
- `--draft dflash2` が明示され、`--draft auto` ではなく、同じ GPU 上に分割された layer split (`split_same`) でもないこと（`engine/src/program/generate.cpp:7835`）。
- Metal build では常に無効。さらに DFlash2 実装の `STRATA_HAVE_DFLASH2` は CUDA/HIP GPU engine に定義され、Metal と SYCL build は DFlash2 なしで compile される（`engine/src/program/generate.cpp:7832-7835,8151-8159`; `engine/cmake/strata_gpu_engine.cmake:6-13`）。
- 通常値（unset、空文字を含む）では、layer split の batch groups が 1 以下の場合に限り有効。batch groups が複数になる既定の pipelining では既定で slot drafts を使わない（`engine/src/program/generate.cpp:7835-7839`）。
- 非空かつ先頭が `0` 以外の値は上記 group 数の既定条件を bypass して slot drafts を要求する。ただし、後続の `--batch-mtp` gate が `--spec < 2`、`split_same`、非 server、layer split の group 構成や helper-GPU expert cache などで失敗すると `batch_mtp` は off になり、slot drafter は作られない（`engine/src/program/generate.cpp:7841-7873,8328-8348`）。
- DFlash2 本体が `--draft-model` から正常にロードされること。DFlash2 の起動条件には fallback/MTP 状態、native pack、`--pipeline-windows` の不使用があり、失敗時は通常 MTP に fallback する（`engine/src/program/generate.cpp:8266-8275,8310-8326`）。
- 別の `STRATA_BATCH_MTP` が有効でも、DFlash2 が選択・起動していなければこの変数は DFlash2 slot drafts を有効にしない。DFlash2 slot drafts が要求されると `batch_df2_wanted` 自体が `batch_mtp` を立てる（`engine/src/program/generate.cpp:7841-7848`）。

## 実行時の詳細

エンジンは batch setup 時に `STRATA_BATCH_DF2` を一度読み、`batch_df2_wanted` として保持する。環境を実行中に変更してもこの起動の判定には反映されない。条件を通り、solo DFlash2 が起動していれば、`o.batch` 個の `Dflash2Drafter` を `clone_alloc` し、失敗時は stderr に slot 番号とエラーを書いて終了コード `1` で起動を中止する。成功すると各 slot が solo drafter の head/embedding を bind し、専用 landing を prepare する。bind/prepare 失敗も stderr に記録して `1` で終了する（`engine/src/program/generate.cpp:8328-8348,13623-13634`）。

solo DFlash2 が起動していなければ `strata generate: WARNING: STRATA_BATCH_DF2 is off: DFlash2 is not running` を出し、batch drafting を無効にする。slot drafting が有効な場合は `strata generate: STRATA_BATCH_DF2: ... slot drafters on CUDA...` と、各 slot の private K/V ring/buffers の量などを stderr に出し、bind 後に `strata serve: STRATA_BATCH_DF2: ... slot drafters ready ...` を出す（`engine/src/program/generate.cpp:8340-8348,13623-13634`）。

batch 処理では slot が余分な window row を得た場合に draft を更新する。余分な行がない slot は tap を host 側に defer し、次に draft が必要になった時点で catch-up する。catch-up に失敗した slot はその round の drafts を行わず、理由を `strata batch: DFlash2 slot ... catch-up failed (...): no drafts for it this round` と stderr に出す（`engine/src/program/generate.cpp:17148-17171,17343-17374`）。batch 集計を出す経路では defer/catch-up 行数も記録する（`engine/src/program/generate.cpp:17511-17518`）。

## 根拠

- `engine/src/program/generate.cpp:7822-7842` — 環境変数の読み取り、値の判定、既定 group 条件、batch MTP との結合。
- `engine/src/program/generate.cpp:7843-7873` — batch drafting gate と理由付き警告。
- `engine/src/program/generate.cpp:8151-8159,8266-8275,8328-8348` — build macro 下の drafter 状態、DFlash2 起動、slot drafter 割り当て。
- `engine/src/program/generate.cpp:13623-13634,17148-17171,17343-17374,17511-17518` — bind/prepare、slot window の draft/defer/catch-up、集計ログ。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — DFlash2 macro が CUDA/HIP GPU engine に定義される箇所。
- `terminal/strata_control/drafting.py:964-970,1146-1164,1732-1743` — Python 側の exact-string 判定と drafting 決定への利用。
- `terminal/serve/server.py:3690-3705` — server 起動時の drafting decision 利用。
- `docs/BATCHING.md:498-515` — batch pipelining と MTP draft の説明。現行実装の `STRATA_BATCH_DF2` 固有の値判定や slot DFlash2 条件を記載した資料は確認できなかった。
