# `INKLING_MOCK_PAD_ID`

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

これは通常の strata-inkling エンジン設定ではなく、terminal/tools/inkling_mock_engine.py のモック専用設定である。モックが画像プレースホルダーとして数える token ID を指定し、--info の image_pad= に表示する。値は GEN プロトコルの画像添付数検査に使われるが、BGEN 経路ではこの検査をしない（terminal/tools/inkling_mock_engine.py:23,64-68,163-185）。

E2E テストは inkling_mock_engine.py を strata-inkling という名前のラッパーから起動する。通常の serve 実装は <|unused_200054|> を使い、候補変数名を読み取らないため、この変数を変えても本番エンジンや serve 側の tokenizer の token ID は変わらない（terminal/serve/test_inkling_serve_e2e.py:147-165,198-205; terminal/serve/inkling_kind.py:10-14）。

## 値と判定

モジュール読み込み時に int(os.environ.get("INKLING_MOCK_PAD_ID") or 200054) として評価する。環境変数が未設定、または値が空文字なら既定値 200054。空文字以外は Python の int に渡す。文字列 "0" は空文字ではないため整数 0 になる。文字列全体が整数として変換できる必要があり、変換失敗時の fallback はなく、ValueError がモジュール読み込み時に伝播する。明示的な範囲検査や clamp はない（terminal/tools/inkling_mock_engine.py:23）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| モックエンジン | 200054 を使用 | `200054`、`0`、`-1`、`+12`、前後に空白がある `12` はそれぞれ整数値として使用 | `0anything`、`true` は `int` 変換で失敗し、例外になる |
| 空文字 | 200054 を使用 | 該当なし | 空文字自体は無効値ではなく、or 200054 により既定値へ戻る |

引数や他の環境変数による上書きはない。--info は計算済みの値を表示する。GEN では受信した token ID 列中のこの値の個数を画像パス数と比較し、画像パスが1件以上あり個数が異なると ERR image: {画像ファイル数} files for {プレースホルダー数} image placeholders を stdout に出してその要求を処理しない（terminal/tools/inkling_mock_engine.py:163-185）。

## 有効になる条件

- terminal/tools/inkling_mock_engine.py が実行される場合に限り読み取られる。E2E ハーネスはこのファイルを strata-inkling ラッパーから起動する（terminal/serve/test_inkling_serve_e2e.py:147-165）。
- --info では値が image_pad= の表示に反映される（terminal/tools/inkling_mock_engine.py:64-68）。
- 画像プレースホルダー数の判定は単一要求の GEN 経路で行われる。BGEN 経路は token ID と画像数を数えるものの、比較による不一致エラーを出さない（terminal/tools/inkling_mock_engine.py:142-161,163-185）。
- 通常の serve が使う IMAGE_PAD_TOKEN は <|unused_200054|> として固定されているため、mock の値を変更するだけでは serve の tokenization との整合は変わらない（terminal/serve/inkling_kind.py:10-14）。

## 実行時の詳細

Python モジュールのトップレベルで読み込まれるため、モックプロセスの起動時に一度だけ評価され、同じプロセスで環境を後から変更しても再読込されない。テストハーネスは親環境をコピーして serve プロセスへ渡し、そこから起動されるエンジンもそのプロセス環境を継承する（terminal/tools/inkling_mock_engine.py:23; terminal/serve/test_inkling_serve_e2e.py:198-205）。

値は --info の出力と GEN の ids.count(IMAGE_PAD_ID) に使われる。GEN で画像パスが無い場合はプレースホルダー数を検査せず、画像パスがある場合のみ画像数と比較する。不一致なら ERR image: ... を stdout に出し、そのコマンドの処理を続けない（terminal/tools/inkling_mock_engine.py:163-185）。不正な整数文字列はトップレベル評価中に ValueError となるため、main のプロトコル出力に到達しない。CLI でこの値を指定する引数はない（terminal/tools/inkling_mock_engine.py:15-23,36-52）。

## 根拠

- terminal/tools/inkling_mock_engine.py:1-5 — モックの用途をテスト用 stand-in と説明。
- terminal/tools/inkling_mock_engine.py:23-24 — 環境からの読み取り、変換、既定値。
- terminal/tools/inkling_mock_engine.py:64-68 — --info の image_pad 表示。
- terminal/tools/inkling_mock_engine.py:142-161 — BGEN 処理に画像プレースホルダー一致検査がない。
- terminal/tools/inkling_mock_engine.py:163-185 — GEN の画像プレースホルダー数検査とエラー応答。
- terminal/serve/test_inkling_serve_e2e.py:147-165,198-205 — E2E テストでモックをラッパー起動し、環境を渡す処理。
- terminal/serve/inkling_kind.py:10-14 — 通常 serve の Inkling 判定と固定画像プレースホルダートークン。
