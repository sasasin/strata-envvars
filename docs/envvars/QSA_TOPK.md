# `QSA_TOPK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`QSA_TOPK` は Metal のテストプログラムで top-k カーネルを選ぶテスト用スイッチです。設定されていれば旧 `qsa_topk`、未設定なら `qsa_topk2` を選びます。製品エンジンがこの環境変数を読む箇所は見つかりませんでした。

読み取り箇所は `metal/tests/qsa_parity.cpp` と `metal/tests/token_chain.cpp` の 2 箇所です。前者は QSA の各段を CPU 参照実装と比較・計測するテスト、後者は Metal カーネルを使った decode 一段の実行・計測用プログラムです（各ファイル冒頭の説明）。

## 値と判定

どちらの読み取り箇所も `std::getenv("QSA_TOPK")` の null 判定だけを使い、値を parse しません。

| 状態 | 選ばれるカーネル |
|---|---|
| 未設定 | `qsa_topk2` |
| 設定あり（空文字を含む） | `qsa_topk` |

`1` 以外の文字列も、空文字も設定されていれば同じ扱いです。コメントには `QSA_TOPK=1` とありますが、実装は値が `1` かどうかを検査していません。CLI 引数による上書きはありません。

## 有効になる条件

このスイッチは Metal テストプログラムの起動時にだけ参照されます。Metal エンジン本体の decode 経路は `metal/src/engine/window.cpp` で通常 `qsa_topk2` を選び、`metal/src/engine/prompt_chain.inc` では `qsa_topk` を dispatch しています。これらの製品経路には `QSA_TOPK` の読み取りがなく、この環境変数で切り替わる根拠はありません。

## 実行時の詳細

`qsa_parity` は `main` 内で環境変数を見て `ptopk` を選び、その pipeline を QSA window の top-k dispatch に設定します（`metal/tests/qsa_parity.cpp:30-47,101-116`）。`token_chain` も初期化時に `qtopk` を選び、その pipeline を選択処理の dispatch に渡します（`metal/tests/token_chain.cpp:243-249,460-473`）。そのため、各プログラムの開始後に環境を書き換えても選択には反映されません。環境変数専用のログ、警告、終了処理はありません。選択された pipeline の利用結果は各テストの通常の実行結果に含まれます。

## 根拠

- `metal/tests/qsa_parity.cpp:1-6,41-47,101-116` — テストの用途、環境変数判定、選択した pipeline の dispatch。
- `metal/tests/token_chain.cpp:1-8,243-249,460-473` — 計測用プログラムの用途、環境変数判定、選択した pipeline の dispatch。
- `metal/src/engine/window.cpp:980-987` — 製品の decode window では `qsa_topk2` を使用。
- `metal/src/engine/prompt_chain.inc:278-286` — 製品の prompt chain では `qsa_topk` を使用。
- `docs/envvars/000_envvers.md:536` — 候補一覧に `QSA_TOPK` がある。これはテストコードで実際に読まれている名前だが、製品エンジン向けの設定を示すものではない。
