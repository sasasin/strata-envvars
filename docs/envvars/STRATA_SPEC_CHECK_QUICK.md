# `STRATA_SPEC_CHECK_QUICK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

## 役割

`strata-inkling` の `--spec-check N` 診断で、greedy の B=1 実行と speculative 実行の比較後に行う verify-window logits 比較および tap 比較を省略する。通常の生成経路やサーバーの speculative decoding の設定ではない。`cmd_spec_check` が比較結果の `rc` を出力して終了するまでの残りの診断量を減らすもので、すでに行った B=1 の反復チェックや speculative と plain の token 比較、その結果に基づく終了コードは変えない（`engine/src/inkling2/ink_main.cpp:659-664, 672-757`）。

## 値と判定

`cmd_spec_check` の speculative 比較が終わった箇所で `std::getenv` により取得し、値が非 null かつ先頭文字 `q[0]` が文字 `'1'` かだけを見る。文字列全体の parse・比較はせず、数値変換、空白除去、大文字小文字変換もない。したがって未設定と空文字は無効、`1` と `1anything` は有効、`0`・`true`・` 1`・`01` は無効。負値や数値境界の概念はない（`engine/src/inkling2/ink_main.cpp:753-756`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `strata-inkling --spec-check N` の比較後 | verify-window と tap 比較を実施 | 先頭が `1`（`1`, `10`, `1anything`） | 空文字、`0`、`true`、` 1`、`01` |

CLI 引数や別の環境変数による値の上書きはない。この変数の判定に既定値・fallback・clamp はなく、分岐を通らない場合は省略は適用されない（`engine/src/inkling2/ink_main.cpp:753-757, 966-969, 1062-1070`）。

## 有効になる条件

- `--spec-check` の引数を `std::atoi` で読んだ値が正で、`--prompt-ids` が与えられ parse できるときに `cmd_spec_check` が呼ばれる。満たさない場合はこの環境変数の読み取り箇所に到達しない（`engine/src/inkling2/ink_main.cpp:966-967, 1062-1070`）。
- モデルの open、backend の初期化、slot の確保、plain の 2 回実行、speculative 実行が成功し、比較後の分岐まで到達する必要がある。これらの失敗は環境変数による省略より前にエラー出力と終了コード 1 で終了する（`engine/src/inkling2/ink_main.cpp:599-611, 658-659, 672-687, 753-757`）。
- `--cpu` を含む backend 選択にかかわらず、この分岐自体には OS・backend・build macro の条件分岐がない。`strata-inkling` 実行ファイルは `ink_main.cpp` を含む standalone target として定義される（`engine/src/inkling2/CMakeLists.txt:176-180`）。

## 実行時の詳細

環境変数はプロセス内で `cmd_spec_check` の比較後に 1 回読み取られる。関数内 `static` cache ではなく、この分岐へ到達するたび現在のプロセス環境を読む。`q[0] == '1'` の場合は `[spec-check] RESULT: identical` または `[spec-check] RESULT: DIFFERS` を出力し、その場で `rc` を返す。そのため M=2, 3, 4, 8 の各 verify-window logits 比較、tap 比較、および関数末尾の同じ RESULT 出力を飛ばす。先行する plain B=1 の再現性確認、speculative/plain token 比較、steps 等の出力はすでに完了しており、token の生成方法を切り替えるものではない（`engine/src/inkling2/ink_main.cpp:659-669, 672-757, 759-783, 786-823`）。

この変数を使う子プロセスへの転送やリクエストごとの適用は実装されていない。読み取りは診断処理中の一度だけであり、同一プロセス実行中の環境変更が読み直される経路はない（`engine/src/inkling2/ink_main.cpp:753-756`）。

## ログと測定値

有効時は `[spec-check] RESULT: %s\n` の形式で結果を出力した後に終了する。`rc` は先行する plain B=1 の不一致または speculative と plain の token 差がある場合に 1 となるため、環境変数が有効でも差を成功扱いにはしない。先行する `open:`, `init:`, `alloc_slot:`, `prefill:`, `decode:`, `spec:` または `verify:` の失敗はそれぞれの診断を出して早期終了し、この quick 結果行には到達しない（`engine/src/inkling2/ink_main.cpp:603-611, 623-627, 647, 658-664, 687, 706-707, 735-757`）。この変数に関する性能測定値はソース・設計資料で確認できない。

## 根拠

- 候補名の実コード参照と読み取り: `engine/src/inkling2/ink_main.cpp:753-756`。リポジトリ全体の完全一致検索で、他の実コード読み取り箇所は見つからなかった。`terminal/data/settings-register.json:45080` にも名前があるが、これは設定レジストリ記載であり、環境から値を読む処理ではない。
- `--spec-check` の CLI 値と呼び出し条件: `engine/src/inkling2/ink_main.cpp:966-967, 1062-1070`。
- 診断の前段・省略対象・終了結果: `engine/src/inkling2/ink_main.cpp:583-587, 599-611, 658-669, 672-757, 759-823`。
- standalone target: `engine/src/inkling2/CMakeLists.txt:176-180`。
