# `STRATA_PACK_THREADS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`packaging/feed_tool.py` の配布アーカイブ作成で、`.tar.gz` の gzip 圧縮に使うワーカースレッド数を選ぶ。既定は 1 で、1 より大きい値では tar を一時ファイルに書いてから並列圧縮する。Strata エンジンの実行時設定ではなく、`feed_tool.py pack-engine` と `pack-control` のパッケージ作成用である（`packaging/feed_tool.py:130-137,166-182,217-228,240-250,456-479,516-526`）。

## 値と判定

`gzip_threads()` は `os.environ.get("STRATA_PACK_THREADS", "")` で取得し、前後の空白を `strip()` で除いてから `str.isdigit()` を判定する。条件を満たせば `int(raw)` に変換し、1 以上なら 64 を上限として返す。それ以外は 1 を返す（`packaging/feed_tool.py:130-137`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `fmt == "tar.gz"` | 1 スレッド | `1` は 1、`2` は 2、`64` と `65` は 64。前後に空白のある ` 4 ` や先頭ゼロの `001` も、それぞれ 4、1 として扱う | 空文字、空白だけ、`0`、`-1`、`+2`、`1.5`、`true` は 1 |
| `fmt != "tar.gz"` | 圧縮スレッド数の判定自体をしない | なし | `STRATA_PACK_THREADS` は参照されず、zip / tar.xz の処理には適用されない |

判定は大文字小文字に関係しない数値変換ではなく、空白除去後の `isdigit()` と `int()` による。ASCII のみを許可する検査ではない。`isdigit()` が真でも `int()` が受理しない文字（例: `²`）や、実行 Python の整数文字列長制限を超える値では `ValueError` になり得る。例外を捕捉して 1 に戻す処理はない（`packaging/feed_tool.py:134-137`）。

## 有効になる条件

- `_write_archive()` に渡される形式が `tar.gz` であること。`pack-engine` は `--format` の既定が `tar.gz`、`pack-control` も同じ既定だが、どちらも `tar.gz` / `tar.xz` / `zip` を指定できる。別形式では環境変数による判定を呼ばない（`packaging/feed_tool.py:166-182,456-479`）。
- `pack-engine` または `pack-control` がアーカイブを書き出す経路であること。Drafter、モデルファイル、feed の生成などにはこの変数の読み取り箇所がない（`packaging/feed_tool.py:217-250,254-265,268-276,516-536`）。
- OS、GPU backend、ビルド macro、モデル状態による追加条件はない。値の優先順位を変える別環境変数や CLI のスレッド数引数もない。`--format` は圧縮経路を選び、`STRATA_PACK_THREADS` はその形式が `tar.gz` の場合にのみスレッド数を選ぶ（`packaging/feed_tool.py:134-137,166-182,456-479`）。

## 実行時の詳細

アーカイブごとに `_write_archive()` が `gzip_threads()` を呼ぶため、値はアーカイブ書き出し時に読み取られ、関数内でキャッシュされない。プロセス中に Python の `os.environ` が変更された場合は次のアーカイブ作成で再評価される（`packaging/feed_tool.py:130-137,166-182`）。

戻り値が 1 の場合は通常の `tarfile` の `w:gz` 経路で書く。2 以上では `.tar-part` という一時 tar を作成し、4 MiB ごとのブロックを `ThreadPoolExecutor(max_workers=threads)` に渡して gzip メンバーとして圧縮し、結果を元の順に出力する。圧縮後は `finally` で一時 tar を削除する（`packaging/feed_tool.py:127-163,173-182`）。この経路で変わるのは gzip 圧縮の並列度と gzip メンバーの構成であり、ソース上の tar 作成ではファイルの並び、属性・内容を書き込む処理は共通である（`packaging/feed_tool.py:166-195`）。

この変数は `feed_tool.py` から子プロセスへ渡されない。同ツール自身が同一プロセス内で圧縮スレッドを作る（`packaging/feed_tool.py:140-163,448-526`）。

## ログと測定値

スレッド数を報告する専用ログや警告はない。パッケージ作成が成功すると `pack-engine` / `pack-control` の CLI 分岐がエントリー情報を JSON で標準出力へ表示するが、スレッド数は含まれない（`packaging/feed_tool.py:516-526`）。値の `int()` 変換や圧縮処理が例外になった場合の個別 fallback / 警告処理はなく、成功時の表示に到達しない（`packaging/feed_tool.py:134-137,173-182,516-526`）。

この環境変数による性能測定値は、対象ソースと関連する `docs/DETAILS.md` / `packaging/UPDATES.md` に確認できなかったため記載しない。

## 根拠

- `packaging/feed_tool.py:130-137` — 環境変数の読み取り、空白除去、整数判定、既定値、上限。
- `packaging/feed_tool.py:140-163,166-182` — 並列 gzip 実装、形式による分岐、一時 tar の扱い。
- `packaging/feed_tool.py:217-250,456-479,516-526` — `pack-engine` / `pack-control` の呼び出しと CLI 形式選択。
