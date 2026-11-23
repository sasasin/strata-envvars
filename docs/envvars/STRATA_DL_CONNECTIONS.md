# `STRATA_DL_CONNECTIONS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata Terminal のセットアップが大きなモデルファイルを HTTP byte range で取得するときの並列 worker 数を指定する。また、同梱 `terminal/tools/mtp_fetch.py` の MTP checkpoint 読み込みでも range worker 数に使われる。どちらも対象はダウンロード処理であり、エンジン実行時の推論並列度や GPU 設定は変えない。実装は `terminal/setup.py` の `dl_connections()` と `download()`、および `terminal/tools/mtp_fetch.py` の `connections()`、`inventory()`、`fetch()` にある（`terminal/setup.py:2754-2761,3556-3569`; `terminal/tools/mtp_fetch.py:285-292,374-381,407-424`）。

## 値と判定

両実装とも `os.environ.get(...) or ""` の後に前後空白を `strip()` し、非空なら Python の `int()` で文字列全体を整数へ変換する。未設定・空文字・空白だけの値は既定値16。変換時の `ValueError` も16へ戻る。変換後は `max(1, min(n, 32))` で1〜32に制限する。したがって `0`、負数は1、33以上は32になる。`+4`、`-4` など整数として受理される書式を使える。`true`、`1x`、`1.5` は無効値で既定値16。大文字小文字は数値変換に関係しない。setup と MTP helper は同じ値規則と既定値を持つ（`terminal/setup.py:2754-2761`; `terminal/tools/mtp_fetch.py:285-292`）。

| 呼び出し経路 | unset / 空文字 / 空白 | 有効値の例 | 無効な整数・変換失敗の例 | 実際の上限・下限 |
|---|---|---|---|---|
| `terminal/setup.py` のモデルファイル取得 | 16 | `1`, ` 4 `, `+8` | `0`・`-2` は1へ制限、`33` は32へ制限、`true`・`1x` は16へ fallback | 1〜32 |
| `terminal/tools/mtp_fetch.py` の `inventory` / `fetch` | 16 | `1`, ` 4 `, `+8` | `0`・`-2` は1へ制限、`33` は32へ制限、`true`・`1x` は16へ fallback | 設定上1〜32。`inventory` はさらに8および shard 数まで |

この変数に対応する CLI 引数はありません。setup は既定の接続数を先に読み、ファイルが256 MiB以上かつ接続数が1より大きいときに range 取得を試します。条件外、または range probe が失敗したときは1ストリームの `download_single()` 経路になります（`terminal/setup.py:2743-2748,3556-3569`; `terminal/setup.py:3188-3195`）。

## 有効になる条件

- setup の通常モデルファイル取得では、既知の合計サイズが `DL_MIN_PARALLEL`（256 MiB）以上で、判定後の接続数が2以上であること。満たさない場合はこの値に関係なく単一ストリーム経路（または既存ファイル処理）になる（`terminal/setup.py:2747,3556-3569`）。
- setup の parallel download が range 対応を probe し、サーバーが使える range response を返すこと。range 非対応なら `parallel_download()` が false を返し、呼び出し元が単一ストリーム取得へ進む（`terminal/setup.py:3188-3195,3567-3569`）。
- MTP の `inventory` は shard header を並列取得するが、実 worker 数は `max(1, min(connections(), 8, len(shards)))`。環境値が32でも最大8で、shard が少なければその数まで（`terminal/tools/mtp_fetch.py:374-381`）。
- MTP の `fetch` は `connections()` を一度呼び出し、各 tensor の byte range をその worker 数で処理する。tensor の残りが一つの range 以下なら `ranged()` は逐次読み込みへ進み、並列化されない（`terminal/tools/mtp_fetch.py:407-424,294-305`）。
- `mtp_fetch.py verify` は hash 検証だけを行い、`connections()` を呼ばないため、この変数の影響を受けない（`terminal/tools/mtp_fetch.py:482-512,515-530`）。
- setup の MTP ダウンロードは、モデル状態・設定により MTP が必要で、まだ取得済みでない場合に限り呼ばれる。たとえば `--mtp off` で未取得、または未取得の状態で drafter が `dflash2` の場合は fetch を省略する。MTP を使う経路では setup が `mtp_fetch.py fetch` を子プロセスとして起動する（`terminal/setup.py:1160-1173,11079-11103,12262-12273`）。

## 実行時の詳細

値は関数が呼ばれるたびにプロセス環境から読み直され、関数内にもモジュール内にもこの値の cache はない。setup はファイルごとの `download()` で `dl_connections()` を評価し、その値を当該取得と SHA-256 不一致時の修復 callback に渡す（`terminal/setup.py:2754-2761,3556-3569`）。MTP の `inventory` と `fetch` も処理ごとに `connections()` を呼ぶ。setup から MTP helper を起動するときは `run()` が渡された環境辞書を subprocess に設定し、`fetch_mtp()` 自体は `STRATA_DL_CONNECTIONS` を上書きしないため、setup プロセスの値が子プロセスにも渡る（`terminal/setup.py:1141-1152,1160-1173`; `terminal/tools/mtp_fetch.py:285-292,407-424`）。

setup の range 取得は32 MiB pieceを管理し、最大 `min(conns, 残りpiece数)` 個の worker thread を起動する。接続あたりの失敗は再試行され、完了 piece の記録を保存して中断後の再開に使う。range が利用できないと単一ストリーム経路へ切り替える（`terminal/setup.py:2740-2750,3188-3255`）。MTP の `fetch` は `connections()>1` のとき16 MiB単位、それ以外は64 MiB単位で range を読み、失敗時には worker 数を `max(4, workers // 2)` にして再試行する。このため、初回値が1〜3であっても失敗後の再試行は最低4 worker を使う（`terminal/tools/mtp_fetch.py:407-424,294-322,452-461`）。

## ログと測定値

setup の並列取得中は2秒ごとに取得済み量と割合を表示し、停滞や再試行時は警告を出すが、接続数そのものを示すログはこの経路にはない（`terminal/setup.py:3205-3251`）。単一ストリームに fallback する理由も、ここでは接続数付きのログとしては出さない（`terminal/setup.py:3188-3195,3567-3569`）。MTP helper は range 取得失敗時に stderr へ `"<tensor>: <error> - continuing with <N> connections (try <N>)"` を出し、継続失敗時は失敗対象と接続確認・別 source の案内を含むメッセージで終了する（`terminal/tools/mtp_fetch.py:452-460`）。セットアップから起動した MTP fetch は失敗コードに応じて offline を許容するか、再試行して最終的にセットアップを失敗させる（`terminal/setup.py:1170-1189`）。

`docs/DETAILS.md:210` は setup が既定16接続でダウンロードし、`STRATA_DL_CONNECTIONS` で1〜32を指定できると記しており、実装の範囲と一致する。速度向上の数値はここでは記載しない。

## 根拠

- `terminal/setup.py:2739-2761` — setup ダウンロード定数と値判定。
- `terminal/setup.py:3188-3255,3556-3589` — range 条件、worker 起動、単一 stream fallback とファイル処理。
- `terminal/setup.py:1141-1152,1160-1189,11079-11103,12262-12273` — 子プロセスへの環境引き継ぎと MTP fetch の呼び出し条件。
- `terminal/tools/mtp_fetch.py:285-322,374-381,407-475,482-539` — MTP helper 内の判定、並列処理、ログ、verify の非該当経路。
- `docs/DETAILS.md:210` — setup の接続数に関する説明。
