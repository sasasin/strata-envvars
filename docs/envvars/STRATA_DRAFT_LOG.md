# `STRATA_DRAFT_LOG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--serve` のリクエスト処理で、DFlash2 drafter が利用可能なエンジンについて、リクエスト単位の draft 計測値を stderr に出す診断スイッチです。draft の選択や生成処理を有効化する変数ではなく、ログ出力だけを制御します。宣言と出力条件は `src/program/generate.cpp:13404,18673-18676` にあります。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_DRAFT_LOG") != nullptr` で設定の有無だけを判定します。

| 状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv` が `nullptr` | ログを無効化 |
| 設定あり | 値の文字列を問わず非 `nullptr` | DFlash2 が利用可能な場合、リクエストのログを有効化 |
| 空文字 | 非 `nullptr` | 設定ありとして有効 |

`1` など特定の値は要求されません。`0`、`false`、空文字を含め、何らかの値が設定されていれば同じ判定です。数値変換、大小文字判定、値域チェック、無効値時の fallback はありません。`STRATA_DRAFT_LOG` に対応する CLI 引数や、別設定との優先順位も実装されていません。

## 有効になる条件

- 判定箇所は `--serve` のリクエスト処理内です。`--serve` の分岐とその serve 要件は `src/program/generate.cpp:10054-10065` にあります。
- 変数が設定されているだけでは出力されません。出力側が `draft_log && use_df2` を条件としているため、DFlash2 がエンジンで利用可能である必要があります（`src/program/generate.cpp:18673-18676`）。
- DFlash2 の実装は `STRATA_HAVE_DFLASH2` ビルド macro の下で宣言され、macro がないビルドでは `use_df2` は常に `false` です（`src/program/generate.cpp:6683-6692`）。DFlash2 は `--draft dflash2` 等の設定後に初期化され、初期化失敗時は無効化される経路があります（`src/program/generate.cpp:6765-6778,11146-11172`）。従って変数単独では DFlash2 をロードしません。
- `--draft auto` でエンジンに DFlash2 がロードされていれば、個々のリクエストが MTP を選んだ場合も、この診断行は出ます。行の `drafter=` はそのリクエストの選択 (`req_df2`) を表示します（`src/program/generate.cpp:15190-15234,18673-18676`）。

## 実行時の詳細

値は関数内の `static const bool` で一度だけ評価されます。最初にこの宣言へ到達した時点の環境変数の有無がプロセス内で保持され、以後のリクエストやプロセス起動後の環境変更では再評価されません（`src/program/generate.cpp:13404`）。

ログ条件を満たすと、リクエストの decode loop 後に stderr へ次の形式で出力します（`src/program/generate.cpp:18664-18676`）。

```text
strata draft: request <連番> drafter=<dflash2|mtp> window<=<幅> tokens=<生成数> rounds=<round数> decode_ms=<decode時間> keep_ms=<upkeep時間> (<roundあたり時間> per round)
```

連番はこのログの出力ごとに増えます。値は対象リクエストの drafter、window 上限、生成 token 数、round 数、decode 時間、`--draft auto` 時の idle drafter upkeep 時間です。`keep_ms` は同モードでなければ通常 0 のままです。ログは `ver.wait_commit()` の最終確認より前に出るため、その後の commit 待ちが失敗する場合にも先に出力されることがあります（`src/program/generate.cpp:18673-18681`）。この変数による警告、終了、fallback はありません。

## 根拠

- 候補名の実装参照は `src/program/generate.cpp:13404` のみです。全参照検索で別の読み取り箇所や helper 経由の参照は見つかりませんでした。
- `std::getenv` の存在判定、static cache: `src/program/generate.cpp:13404`。
- serve 内の DFlash2 有効状態とビルド条件: `src/program/generate.cpp:6683-6692,11146-11172`。
- `--draft auto` のリクエスト別 drafter 選択: `src/program/generate.cpp:15190-15234`。
- ログの出力条件、書式、タイミング: `src/program/generate.cpp:18664-18681`。
