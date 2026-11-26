# `STRATA_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバーの各要求で MTP draft の深さ別受理数を stderr に表示する診断用スイッチ。変数名に `=1` と書かれた例があるが、実装は値を読み取らず、`getenv` が null かどうかだけで出力を決める。draft の生成・検証・採用や応答 token を切り替える処理ではない。カウンターは要求ごとに初期化され、対象となる verify window ごとに環境変数の有無と無関係に更新される（`engine/src/program/generate.cpp:21748-21749,23050-23053,23929-23933`）。

この読み取り箇所は `strata serve` の要求処理にあり、同じファイルの CLI generate 経路にはこの名前の読み取りがない（全参照検索では実装上の `getenv` は `engine/src/program/generate.cpp:23929` のみ）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| サーバー要求の報告箇所 | 深さ別の行を出力しない | 空文字、`0`、`1`、`false`、その他どの文字列でも、環境変数が存在すれば出力する | 該当なし。文字列値による無効化はない |

`std::getenv("STRATA_SPEC_DEPTH") != nullptr` という設定有無判定であり、数値変換・文字列比較・trim・大小文字判定をしない。したがって空文字も「設定あり」。`1` 以外の値も出力を有効にする（`engine/src/program/generate.cpp:23929-23933`）。

## 有効になる条件

- `engine/src/program/generate.cpp` のサーバー要求処理が実行され、要求が深さ別集計の報告箇所まで到達すること。CLI generate の経路ではこの変数を読まない（`engine/src/program/generate.cpp:23923-23933`）。
- 実際に数が増えるのは、最初の window ではなく、suffix lookup 由来でもない window に MTP depth があり、検証が集計行まで進んだ場合。集計対象の深さは `T_mtp - 1` 未満かつ最大 8 深さで、報告されるのはそのうち先頭 5 深さ（`engine/src/program/generate.cpp:23050-23053,23929-23933`）。対象 window がなければ、設定していてもゼロ件の行になる。
- OS、別の環境変数、CLI 引数による優先順位・上書き条件はこの読み取り箇所にはない。build/backend 固有の値判定もない。

## 実行時の詳細

深さ別カウンターは要求処理のローカル変数としてゼロ初期化される。MTP の各候補深さ `d` について、`d <= a` なら tested を 1 増やし、`d < a` なら accepted を 1 増やす。ここで `a` は検証後に受理された連続行数で、suffix 由来および最初の window は集計から除かれる（`engine/src/program/generate.cpp:21748-21749,23029-23030,23050-23053`）。

要求の報告箇所で `getenv` を都度呼び、設定されていれば深さ 0〜4 の accepted/tested を出力する。値を static 変数などに cache しないため、その時点のプロセス環境を判定する。リポジトリ内にこの変数を設定・変更する処理は見つからず、外部から起動後にプロセス環境を変更する手段はこのコードからは確認できない。環境変数は MTP の有効化、サンプリング方式、CLI オプションの既定値を変更しない（`engine/src/program/generate.cpp:23929-23933`）。

## ログと測定値

設定時に要求の報告箇所まで到達すると stderr に次の形式で出力する（`engine/src/program/generate.cpp:23929-23933`）。各 `accepted/tested` は深さ 0、1、2、3、4 の順。

```text
strata serve: spec depth: accepted/tested N/N N/N N/N N/N N/N
```

unset のときこの行は出ない。この変数による警告、エラー、終了・timeout 経路はない。`docs/DETAILS.md:625-628` も `STRATA_SPEC_DEPTH=1` を draft depth ごとの acceptance を表示する設定として挙げている。実装上は `=1` に限定されず、設定の有無だけが条件。

## 根拠

- `engine/src/program/generate.cpp:21748-21749` — 要求ごとの深さ別カウンター初期化。
- `engine/src/program/generate.cpp:23029-23030,23050-23053` — accepted window の数え方と集計対象条件。
- `engine/src/program/generate.cpp:23923-23933` — 要求報告箇所、設定有無の判定、stderr の正確な書式。
- `docs/DETAILS.md:625-628` — 機能説明との照合（設定値の条件は現行コードに合わせて補足）。
