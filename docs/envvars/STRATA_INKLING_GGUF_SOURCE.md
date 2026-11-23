# `STRATA_INKLING_GGUF_SOURCE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2-Mini の GGUF ファイルを Strata のセットアップがダウンロードするときに、先に試す HTTP ソースを指定する。`gguf_sources()` はこの値を通常の `STRATA_INKLING_SOURCE` と同梱の `gguf_sources` より前に追加するが、後続ソースも候補に残すため、単独の置き換え設定ではない。実際のセットアップ経路は `inkling_fetch()` から `sources_for()` を呼ぶ（`terminal/strata_control/inkling_family.py:142-165`, `terminal/setup.py:10458-10485`）。

## 値と判定

環境変数名は `GGUF_SOURCE_ENV` に定数として保持され、`gguf_sources()` が `env.get(...)` で読み取る。通常の呼び出しでは `env` の省略値が `os.environ` であり、関数が呼ばれるたびに現在の環境辞書を参照する。truthy な値だけを `_normalise()` に渡すため、未設定と空文字はどちらも候補に加わらない。環境変数から渡る文字列は `http://` または `https://` で始まる場合だけ HTTP ソースとなり、末尾の `/` を除去する。前後の空白除去、URL 全体の検証、大小文字を無視した判定はない（`terminal/strata_control/inkling_family.py:121-123,142-158,168-180`）。

| 条件 | unset | 有効になる値（例） | 無効・無視される値（例） |
| --- | --- | --- | --- |
| `gguf_sources()` の通常呼び出し | `env.get()` が `None` となり、環境由来ソースなし | `https://mirror.example/models`、`http://localhost:8080/gguf/`（末尾 `/` は除去） | 空文字（truthy でない）、`true`、`ftp://host/path`、先頭に空白がある ` https://host/path`（HTTP 接頭辞に一致しない） |

文字列は URL として解釈されるだけで、整数変換や真偽文字列のパースはない。`0`、`1`、`false` は HTTP URL の接頭辞でないためソースにならず、値が無効でも警告は出ず後続候補に進む。`https://` の後のホストやパスの妥当性はこの関数では検証せず、実際の取得時に失敗し得る（`terminal/strata_control/inkling_family.py:148-149,168-176`; `terminal/setup.py:10470-10482`）。

## 有効になる条件

- `sources_for()` に渡すファイル名が `UNSLOTH_GGUF_FILES` に含まれるか、`.gguf` で終わること。その他のファイル名は通常の `sources()` に進み、この変数は参照されない（`terminal/strata_control/inkling_family.py:161-165`）。
- セットアップがそのファイルを実際に取得すること。既にファイルがある場合は `inkling_have()` の判定後に取得を省く（`terminal/setup.py:10458-10466`）。
- `--gguf-dir` を指定したローカル所有ファイル経路では、欠けたファイルをダウンロードせず `fail()` するため、この環境変数による取得先指定は使われない（`terminal/setup.py:10464-10468,10596-10600`）。
- ソースコード上、この判定に OS・GPU backend・build macro・サーバーモードの条件はない。GGUF モデルを選び、セットアップが不足ファイルを取得する経路で適用される（`terminal/setup.py:10646-10656`）。

## 実行時の詳細

GGUF のモデルファイル、または GGUF セットアップで要求される補助ファイルの取得時に `inkling_fetch()` が `sources_for(name)` を呼び、`gguf_sources()` がソース候補を組み立てる。既定引数の `env` は `os.environ` で、値を関数外や `static` に保存するキャッシュはない（`terminal/strata_control/inkling_family.py:142-158,161-165`; `terminal/setup.py:10458-10476`）。

候補の順は、ヘルパーに `cfg` を渡した場合は設定キー `inkling_gguf_source`、設定キー `inkling_source`、この環境変数、`STRATA_INKLING_SOURCE`、同梱ファイル `terminal/data/inkling-sources.json` の `gguf_sources`。ただし Strata 内の実際の `inkling_fetch()` は `sources_for(name)` に `cfg` を渡していないため、このセットアップ経路では設定キー候補はなく、対象環境変数、`STRATA_INKLING_SOURCE`、同梱候補の順になる（`terminal/strata_control/inkling_family.py:142-158`; `terminal/setup.py:10466-10471`）。

各候補について `urls_for()` がファイル別 URL、または `base/name` を作る。セットアップはその候補の `urls` の先頭だけでダウンロードを試し、検証を通れば終了する。`SystemExit` となる取得・検証失敗が後続候補より前に起きた場合は `warn(f"{name}: that source did not work; trying the next one")` を出して次の候補を試す。候補が一つもなければ `no download source for {name} is configured`、URL が一つもそのファイルを列挙しなければ `no source lists {name}` で失敗する。候補をすべて試して失敗した場合は最後の `SystemExit` を再送出する（`terminal/strata_control/inkling_family.py:183-190`; `terminal/setup.py:10466-10485`）。

## ログと測定値

対象変数の値が読み取られたこと自体を示すログはない。ソース失敗時の警告文は `{name}: that source did not work; trying the next one`。候補なしの場合は `no download source for {name} is configured` と案内文 `put the file in {folder} (or set STRATA_INKLING_SOURCE) and run this again` が `fail()` に渡される（`terminal/setup.py:10468,10482`）。この変数に関する性能測定値は、対象 commit のソース・資料で確認できない。

## 根拠

- `terminal/strata_control/inkling_family.py:121-123,142-158` — 環境名、環境・設定・同梱候補の追加順。
- `terminal/strata_control/inkling_family.py:161-190` — GGUF 判定、値の正規化、URL の組み立て。
- `terminal/setup.py:10458-10485` — 実際の取得、候補の順次試行、警告と失敗経路。
- `terminal/setup.py:10596-10600,10646-10656` — ローカル GGUF 指定とセットアップでの適用箇所。
