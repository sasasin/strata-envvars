# `STRATA_TEST_NAN_STOP_AT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-dsv41` の serve で、指定した要求番号に NaN 検出時と同じ停止経路を一度だけ注入するテスト用フックです。実際に NaN が発生したかどうかに関係なく、要求をエラー終了させて会話状態を破棄します。通常の生成設定ではありません。読み取りは `src/dsv41/ds4_main.cpp:1408-1412`、注入条件と停止処理は同 `:1421-1426,1472-1492` にあります。

## 値と判定

環境変数を `std::atol` で `long` に変換し、正数だけを有効な要求番号として扱います。文字列全体の妥当性検査はありません。`atol` が読み取れる先頭の整数部分が使われるため、たとえば `3tail` は `3`、空文字や整数で始まらない文字列は `0` となり、注入しません。先頭の空白と符号も `atol` の変換規則に従います。

| 値 | 動作 |
|---|---|
| 未設定 | `0` として注入しない |
| 空文字、数値で始まらない文字列 | `0` として注入しない |
| 変換結果が `0` または負数 | 注入しない |
| 変換結果が正数 `N` | この serve が処理する N 番目の単一会話要求に注入 |

大文字小文字の比較はなく、数値変換後の符号付き `long` の正負だけを判定します。読み取り値は関数内の `static const long` に保存されます。根拠: `src/dsv41/ds4_main.cpp:1408-1412`。

## 有効になる条件

- `strata-dsv41` がビルドされている必要があります。CMake では `STRATA_BUILD_DSV41` は既定 OFF で、ON かつ `STRATA_HIP_GFX906` でない場合にこの実行ファイルを追加します（`CMakeLists.txt:931-945`）。
- `--serve` で serve 関数を実行し、`--parallel` を指定しないか、会話数を 1 にして、単一会話ループを通る必要があります。`--parallel N` で会話数が 2 以上の場合は別ループに入り、このフックを含む判定箇所を通りません（`src/dsv41/ds4_main.cpp:513-520,1355-1357,1495-1503,2582-2589,2621-2629`）。
- 要求番号はこの serve プロセスが処理する要求の順番です。CLI、モデル状態、他の環境変数による上書きや fallback はこの読み取り箇所にありません。

## 実行時の詳細

serve 内で有効な `GEN` / `GENI` 要求の prompt を読み、最初の `m.sample(...)` を呼んだ後に環境変数を初期化します。したがって、プロセス起動後でも最初の該当要求より前に環境を書き換えれば初期化値に反映されますが、初期化後の変更は `static const` のため反映されません。正数が設定されている場合、prompt 読み込み後にこの位置まで到達した要求ごとに static カウンターを増やし、指定番号の要求だけ `produced == 0` の最初の poll で注入します。ただし、その poll より先に `STOP` が検出されると通常の cancel 分岐で終わり、注入条件には進みません。一つの要求への注入は一度です（`src/dsv41/ds4_main.cpp:1368-1397,1407-1426`）。

注入時は stdout に次の `ERR` を出して flush し、`DONE` 行を出さずに要求を終了します。

```text
ERR the model's numbers went non-finite (NaN reached the router), so the answer would be nonsense: the request is stopped and the conversation dropped
```

この条件式は注入が成立すると `m.router_nonfinite()` を短絡評価で呼ばないため、注入だけを理由に router の実 NaN 警告は出ません。後続では通常の serve 統計を stderr に出し、`m.reset()` と `held.clear()` でモデルの会話状態と保持画像を破棄し、profile を保存します。次の要求はリセット後の状態から始まります（`src/dsv41/ds4_main.cpp:1421-1426,1470-1493`）。通常の実 NaN 判定は別途、生成数 0 または 8 の倍数で `m.router_nonfinite()` を呼ぶ経路です。router 側の実 NaN はデバイスごとに初回だけ stderr に警告しますが、これはこのテスト変数が出す警告ではありません（`src/dsv41/ds4_main.cpp:1418-1426`; `src/dsv41/ds4_model.cu:8758-8778`）。

子プロセスへの転送処理はこの箇所にはありません。環境変数は `strata-dsv41` 自身が直接読みます。

## 根拠

- 値の読み取り、`atol` 変換、正数判定、要求カウンター: `src/dsv41/ds4_main.cpp:1407-1412`
- serve の要求受付、初回 sample、STOP と単一会話 / 並列会話の分岐: `src/dsv41/ds4_main.cpp:513-520,1355-1397,1413-1426,1495-1503`
- ERR / DONE 抑止 / reset / 状態破棄: `src/dsv41/ds4_main.cpp:1421-1426,1470-1493`
- 実際の router NaN 警告との区別: `src/dsv41/ds4_model.cu:8758-8778`
- 実行ファイルの任意ビルド条件: `CMakeLists.txt:931-945`
