# `STRATA_ADAPT_ASYNC_BATCH`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena を使う非同期 adaptive tier（`--adapt-async 1`）で、1回の補充ラウンドにおいて GPU キャッシュへコピー投入する expert 数を制限します。正の値 `N` なら、swap-in を最大 `N` 件ずつのバッチに分けます。コピーエンジンを decode window と共有する arena 経路で、投入を小分けにするための値です。

arena 以外の resident RAM 経路ではこの変数は読み取られず、通常はブロッキング tier に切り替わる条件では効果もありません。

## 値と判定

`a_env()` は値が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数に変換します。その結果を `std::max(0, ...)` で0以上にして `size_t` にします。

| 値 | `a_batch` | 動作 |
|---|---:|---|
| unset / 空文字 | 0 | そのラウンドの残りの swap-in をまとめて投入 |
| `0`、`00`、数値変換結果が0 | 0 | 同上 |
| 正の整数 `N` | `N` | 最大 `N` 件ずつ投入し、バッチが完了してから次を投入 |
| 負の整数 | 0 | 負値を0に丸め、まとめて投入 |
| 数字で始まらない文字列 | 0 | `atoi()` の変換結果0となり、まとめて投入 |
| 数字の後ろに文字がある文字列 | 数字の先頭部分 | `atoi()` が先頭の整数部分を変換（例: `12junk` は12） |

文字列全体の妥当性検査やエラー報告はありません。整数型で表現できない値に対する `atoi()` の動作は、この実装で保証されていません。

## 有効になる条件

- `srcp == &arena_src` の arena モードであること。arena 以外では三項演算子が `a_env()` を呼ばず `a_batch` を0にします。
- `--adapt-async 1` が有効になり、適応層が稼働していること（`--adapt-every` と `--adapt-swaps` が正で、usage table が空でないこと）。
- async tier が無効化される条件に該当しないこと。例として `--serve` 以外、arena の layer split または `--pipeline-windows 2`、`--batch-groups`、`--peer-device`、`--remote-expert-opt` との組み合わせでは blocking tier に戻ります。

arena の async tier は `--adapt-async` の条件判定に加え、arena 用の `--pipeline-windows 2` は使えません。これらの条件で切り替わる理由は `--adapt-async 1 is off (...)` の stderr ログに出ます。

## 実行時の詳細

環境変数は adaptive tier のローカル設定を作る際に読み、`a_batch` はその設定中に一度だけ決まります。`static` キャッシュではないため、別の generate 実行では再読込されますが、同じ実行中の変更は反映されません。

arena の swap-in では、次のバッチ範囲を `[a_bi, min(aswaps.size(), a_bi + a_batch))` として helper thread に投稿します。`a_batch == 0` の場合は上限に全 swap 数を使うため、残り全部を一度に投稿します。バッチのコピー完了後に該当 expert を resident として登録し、残りがあれば次のバッチを投稿します。したがって、正の値はラウンド全体の swap 数を制限するのではなく、各投入バッチの最大件数を制限します。

変数の値は stderr の累積統計にも表示され、arena の行には `(arena, copy-in only, batch N, ...)` と出ます。表示される `batch 0` は「0件に制限」ではなく「全件投入」を意味します。

## 根拠

- `src/program/generate.cpp:10385-10406`: arena 判定、`a_env()` の unset/空処理、`atoi()`、非負 clamp、arena 条件付き評価、async tier 起動。
- `src/program/generate.cpp:10416-10426,10516-10532`: コピー投入範囲と helper thread への投稿。
- `src/program/generate.cpp:10647-10676`: arena swap-in の初回投入、完了済みバッチの反映、残りバッチの投入。
- `src/program/generate.cpp:7948-7975,8191-8192`: `--adapt-async` の適用条件と blocking tier への fallback。
- `src/program/generate.cpp:15376-15385`: arena 統計ログに `a_batch` を出力。
- `docs/DETAILS.md:202-209`: arena でのコピー分割と既定値0を説明。RTX 3090 + Ryzen 5 5600X の cold prompt に関する性能値は同資料に記載されていますが、この調査ではソース上の挙動確認に限り、性能値は独自に検証していません。
