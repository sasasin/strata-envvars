# `STRATA_SPEC_T_CYCLE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

`--spec` による speculative generation の測定用フックです。設定すると verify window の候補幅をリスト順に巡回し、幅ごとのラウンド時間を stdout に出します。通常の生成設定ではなく、幅別コストを測る CLI ベンチ用途で、既定では無効です。

## 値と判定

環境変数が未設定、または空文字なら巡回リストは作られず、この機能は無効です。空でない場合、文字列をカンマ区切りで走査し、各要素の先頭から `std::atoi` で整数を読みます。整数全体を検証しないため、数値の後ろに文字があっても `atoi` が読んだ値を採用し、整数に変換できない要素は通常 0 となって無視されます。空要素、負数、範囲外値も無視されます。`1,2,2,8` のような重複値はそのまま順序付きリストに残ります。

有効として残るのは `1` 以上 `o.spec` 以下の整数です。したがって、上限は CLI の `--spec` 値で決まり、リスト中の値がすべて範囲外なら有効な巡回幅がなく、分岐は実行されません。コードは前後空白の除去や大文字小文字の処理を行いません（数値変換は `atoi` の規則によります）。

| 入力 | 結果 |
|---|---|
| 未設定、空文字 | 無効 |
| `1,2,4`（各値が `--spec` 以下） | `1 → 2 → 4` を巡回 |
| `1x,2` | `atoi` により `1 → 2` |
| `0,-1,99`（`--spec` が 8） | 有効値がなく無効 |

## 有効になる条件

- `strata generate --spec ...` の speculative generation 経路に入る必要があります。この経路では `Verifier` の初期化と drafter 設定後に値を読みます。
- `--spec` が巡回幅の上限です。値がそれを超えると除外されます。
- 最初の verify window は初回生成状態のため幅 1 で実行され、巡回値を使いません。
- 巡回値を選んだ後、suffix lookup が採用された場合はその幅で置き換わることがあります。さらに lookup-chain が後続の幅を加え、context 残量と `win_cap` による上限が適用されます。そのため報告される幅は、設定リストの値と常に一致するとは限りません。
- 同じループ内の `STRATA_VERIFY_PROFILE` が設定されている場合は、幅ごとの GPU stage 内訳も出ます。幅ごとの routed expert 数は `STRATA_ROUTE_STATS` が有効な場合にだけ出力されます。

## 実行時の詳細

値は speculative generation ループの初期化時に一度読み、`t_cycle` ベクターへ保存します。各ラウンドでは `rounds % t_cycle.size()` を添字として巡回し、通常の draft policy が選んだ `T` を置き換えます。ただし初回 window は除外され、その後に suffix lookup、lookup-chain、context/window cap の処理を通ります。処理中に環境変数を変更しても、すでに作られたベクターには反映されません。

`window cost (ms/round)` は、実際に実行された幅ごとに `round_ms` の平均とサンプル数 `n` を stdout に表示します。幅ごとの最初の実行は graph capture 時間を含むため集計から外し、2回目以降を集計します。`round_ms` はラウンド開始から、verify/commit と次の draft 処理を経たラウンド終了までの経過時間です。`--max-new` が短いなどで幅が複数回実行されなければ、その幅の平均は表示されません。失敗時は通常の generate エラー経路となり、幅別の最終集計には到達しません。

リポジトリ内の `tools/dflash2/README.md` も、この変数を「CLI bench only」と記し、`window cost (ms/round)` が幅別コストを示すと説明しています。コードでは実行された窓幅と集計条件がさらに定まり、README の `1,2,...,8` は例であって固定の受理範囲ではありません。

## 根拠

- `src/program/generate.cpp:16127-16169` — `--spec` 用 `Verifier` と drafter の初期化。
- `src/program/generate.cpp:16386-16397` — 既定無効、`getenv`、カンマ区切り、`atoi`、`1..o.spec` のフィルタ。
- `src/program/generate.cpp:16531-16567` — 通常の幅決定、初回窓の幅 1、巡回値の上書き、suffix lookup と窓上限。
- `src/program/generate.cpp:16569-16585` — lookup-chain が窓に加わる条件。
- `src/program/generate.cpp:16702-16712,16746-16756` — ラウンド時間の集計と stdout 出力、幅別 profile/stats の追加出力。
- `src/core/verify.cpp:934-948,2349-2378` — `STRATA_VERIFY_PROFILE` の設定有無判定と幅別 GPU stage 報告。
- `tools/dflash2/README.md:7-11` — ベンチ用途と表示項目の説明。
