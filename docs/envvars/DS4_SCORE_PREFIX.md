# `DS4_SCORE_PREFIX`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

同梱 executable `strata-dsv41` の `--score` モードで、ids データの先頭部分を prompt として先に読み、その後の位置だけを teacher-forced scoring するためのテスト用フックです。コメント上の目的は、長い prompt の layer skip 経路を scoring で通すことです。通常の `--serve` や単純な token generation を変更する環境変数ではありません。

## 値と判定

`score()` 呼び出し時に `getenv()` で取得し、設定があれば `std::atoll()` で変換します。未設定時の `prefix_n` は `0` です。`atoll` のため、先頭の空白と符号は許容され、数字列の後ろにある文字列は変換結果に影響しません。たとえば `" 12tail"` は `12`、数値として変換できない文字列は `0` として扱われます。コードは parse error や overflow error を別途検査しません。

| 値 | 動作 |
|---|---|
| 未設定、または変換結果が `0` 以下 | prefix prompt を使わない。`a0=0` から通常どおり score する |
| 正の値 `N` | ids stream の長さが `N + 1` より大きいとき、先頭 `N` token を先に `m.feed(..., N, 1, ...)` で読み、位置 `N` 以降を score する |
| 正の値だが `N + 1 >= ids.size()` | prefix 条件を満たさないため先読みせず、先頭から通常どおり score する |

変数は static cache されず、score 関数への各呼び出しで読み取られます。Strata のコマンドライン parser にこの値を上書きする option はありません。

## 有効になる条件

- `strata-dsv41` を `--score IDS.json` で起動した場合だけ `score()` が呼ばれます。`--serve` は先に別の serve 経路へ return するため、この変数を読みません。
- 先読みは `prefix_n > 0` かつ、各 scoring segment の ids 数が `prefix_n + 1` より大きい場合だけです。
- `prefix_n > 0` で入力 JSON に複数 segment があると、prefix 長チェックより先に全 segment の ids を順番に連結し、名前を `concat` とした単一 segment にします。prefix が長すぎて先読み条件を満たさない場合でも、この連結は行われます。
- 入力ファイルの読み込みに失敗した場合は scoring に進みません。実行ファイルと `--score` の指定が必要です。

## 実行時の詳細

各 segment の処理開始時に model state を reset します。prefix 条件が成立すると、先頭 `N` token を `m.feed(ids.data(), N, 1, err)` で一度に feed します。その後の scoring loop は位置 `N` から始まり、`--window`（既定は scoring / profiling 用に16）以下ずつ `m.feed(..., T, T, ...)` で feed し、各位置の次 token の log probability、top-1、top-64 等を出力します。score 結果の TSV と `.seg.json` は通常経路と同じ出力先へ書かれます。

コード上、`prefix_n` の値そのものによる専用ログや警告はありません。成功時は segment ごとの `score <name>: <positions> positions, ppl ..., top-1 ...` が stderr に出ます。feed が失敗した場合は `strata-dsv41: <error>` を stderr に出して status 1 で戻ります。関連する `tools/dsv41/test_prompt_skip.py` は `DS4_SCORE_PREFIX="4200"` を設定してこの経路を使いますが、そのテストの測定値をこの文書では独立に検証していません。

## 根拠

- `src/dsv41/ds4_main.cpp:962-966`: `--score` の入力形式と出力の概要
- `src/dsv41/ds4_main.cpp:1006-1022`: 環境変数の取得、segment 連結と prefix 条件
- `src/dsv41/ds4_main.cpp:1035-1053,1073-1095`: segment state reset、prefix feed、window scoring、出力と終了
- `src/dsv41/ds4_main.cpp:1263-1268,1301-1306`: `--score` と `--serve` の経路分岐
- `tools/dsv41/test_prompt_skip.py:8,44`: 同梱テストからの設定例（実装挙動の根拠ではなく利用箇所の確認）
