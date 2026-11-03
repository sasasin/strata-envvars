# `DS4_CHUNK_LOG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-dsv41` の chunked feed 経路で、`forward_chunks` の分割・YOCO skip に関する値を stderr に出す診断用スイッチです。chunk 数や分割サイズ、計算経路を変更せず、ログの有無だけを切り替えます。

## 値と判定

値の parse は行わず、`std::getenv("DS4_CHUNK_LOG") != nullptr` だけを判定します。

| 状態 | 動作 |
| --- | --- |
| 未設定 | この変数によるログを出さない |
| 設定あり（空文字を含む） | ログを出す |

したがって `0`, `false` なども、変数が設定されていれば有効です。数値変換、文字列比較、範囲検査、無効値時の fallback はありません。CLI 引数や別の環境変数との値の優先順位もありません。

## 有効になる条件

ログ判定に OS、backend、build macro、CLI 引数、モデル状態による追加条件はありません。一方、出力箇所に到達するには `forward_chunks` が呼ばれる必要があります。

- `Model::feed` では `chunk > 0` かつ `n >= chunk_min` のとき chunk 対応経路に入り、`logits_rows > kWin` または `pick_path(n)` が真なら `forward_chunks` を使います。`pick_path(n)` が偽なら `feed_windows` となり、この変数のログは出ません。
- `Model::feed_mark` と `Model::feed_marks` では、入力長・chunk 設定・`pick_path(n)` などの条件を満たす場合に `forward_chunks` を使います。それ以外は window 経路です。
- `forward_chunks` 自体も `n < 1` ならログ箇所より前に戻ります。

## 実行時の詳細

`forward_chunks` は入力の有効性と context 上限を確認した後、YOCO layer、保持行数、skip 行数および chunk の数・サイズを算出します。その後、呼び出しごとに環境を読み、設定されていれば次の形式を stderr に出します。

```text
forward_chunks n %d nc %d per %d yoco %d keep %d skip_rows %d (after %d, first point at row %d)
```

各値はそれぞれ入力行数 `n`、chunk 数 `nc`、chunk あたりの行数 `per`、YOCO layer `yl`、保持行数 `keep`、実際の skip 行数 `a`、`after`、最初の restore point の相対行（ない場合 `-1`）です。環境値は関数内で毎回 `getenv` され、static cache はありません。プロセス中に環境を変更できる実行形態なら次の呼び出しで判定し直します。

ログ行は chunk 処理を始める前に出ます。後続の `borrow_begin` 失敗やデバイス処理失敗などで feed が失敗しても、このログ行はすでに出力され得ます。`DS4_CHUNK_LOG` 自体がエラー、終了、fallback を起こす分岐はありません。

## 根拠

- `src/dsv41/ds4_model.cu:12897-12934` — `forward_chunks` の早期 return、chunk/YOCO 値の算出と唯一の `DS4_CHUNK_LOG` 読み取り・stderr 出力。
- `src/dsv41/ds4_model.cu:12952-12953,13009-13013` — ログ後の処理とデバイス worker 実行。
- `src/dsv41/ds4_model.cu:14862-14875` — `Model::feed` が chunk 経路または window 経路を選ぶ条件。
- `src/dsv41/ds4_model.cu:14877-14924` — `feed_mark` / `feed_marks` の chunk 経路条件と fallback。

