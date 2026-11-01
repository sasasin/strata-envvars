# `SYCL_CACHE_PERSISTENT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の SYCL engine やサーバー本体が、この変数の値を読み取って処理を切り替えるコードは見つかりませんでした。Strata 側で確認できるのは、SYCL 実行用 Docker image の既定値を `0` にする処理、SYCL 起動ラッパーがホスト環境から `SYCL_*` 変数をコンテナへ渡す処理、および ARC ベンチ用ツールが engine の環境へ値を設定する処理です。

したがって、Strata のコードから説明できるのは値の設定と転送までです。永続 JIT cache に対する意味や効果は Strata の挙動としては扱いません。

## 値と判定

| 経路 | 未設定 | 空文字 | `0` | その他の値 |
|---|---|---|---|---|
| `sycl/serve/strata-sycl.sh` と同梱 Docker image | image の `ENV` 既定値 `0` | ラッパーは `-e` を付けず、image の既定値が残る | ラッパーは `-e` を付けず、image の既定値が残る | ラッパーは文字列をそのまま `docker run -e` に渡す。変換・検証なし |
| `tools/arc/b.py` | ツールがまず `0` を設定 | `--env SYCL_CACHE_PERSISTENT=` で空文字を設定可能 | 既定値または `--env` で設定 | `--env` の文字列をそのまま設定。変換・検証なし |

SYCL 起動ラッパーの値比較は文字列 `0` または空文字との完全一致です。たとえば `00`、`false`、`0 ` は除外対象と一致せず、そのままコンテナへ渡されます。設定値を真偽値や数値として parse する処理はありません。

## 有効になる条件

- コンテナ経由の SYCL 起動では、`serve/server.py` が engine の子環境を作り、設定ファイルの `env` をそこへ反映します。その環境で `sycl/serve/strata-sycl.sh` が実行され、`SYCL_*` 名の変数が設定されている場合に転送処理の対象になります。ラッパーが `0` または空文字を除外した後の値は、同梱 image の既定値である `0` になります。
- `sycl/tools/Dockerfile` が image に `SYCL_CACHE_PERSISTENT=0` を設定します。別 image を `STRATA_SYCL_IMAGE` で指定した場合の image 側既定値は、この Dockerfile からは分かりません。
- `tools/arc/b.py` はベンチ用の同梱ツールです。`--env K=V` は初期環境を作った後に適用されるため、`--env SYCL_CACHE_PERSISTENT=V` はツールの既定 `0` を上書きします。この経路は通常のサーバー設定とは別です。
- ネイティブ実行については、ソース内にこの名前を読んだり設定したりする Strata の処理は見つかりませんでした。文書 `docs/INTEL_ARC.md` と `docs/INTEL.md` は native 起動時にも値を export する手順を案内していますが、これは文書上の手順です。

## 実行時の詳細

サーバー経路では、`child_env()` がプロセスの環境を複製し、設定の `env` を文字列化して上書きします。engine 起動時にその環境が子プロセスへ渡されます。SYCL の `exe` は `sycl/serve/strata-sycl.sh` で、ラッパーは親環境にある `SYCL_*` を列挙して Docker の `-e` 引数に変換します。ラッパーは値を保存・parse せず、起動ごとに環境を参照します。

`tools/arc/b.py` は起動ごとに `dict(os.environ)` を作り、`SYCL_CACHE_PERSISTENT` を `0` に設定した後、各 `--env` を順番に適用して engine subprocess に渡します。値による分岐、警告、Strata 独自の終了・失敗経路はこの変数についてありません。起動後の環境変更を再読込する処理もありません。

Strata の Intel 向け説明文書は `0` を推奨し、Xe2 の初回 compile 時の問題を理由に挙げています。しかし、この文書ではその外部ランタイムの挙動を Strata のコードで確認した事実として記述しません。また、SYCL 起動ラッパーはホストから明示的に渡された非空・非 `0` 値を受け入れるため、コード上は利用者の値で image 既定値を上書きできます。

## 根拠

- `sycl/tools/Dockerfile:8` — SYCL image の `SYCL_CACHE_PERSISTENT=0` 既定値。
- `sycl/serve/strata-sycl.sh:13-16,28-38,42-48` — `SYCL_*` 環境変数の列挙、`0` と空文字の除外、`docker run -e` への転送、engine 起動。
- `serve/server.py:3747-3760,9191-9194,9277-9279,1077-1079` — ホスト環境と設定 `env` からの child env 作成、engine subprocess への引き渡し。
- `tools/arc/b.py:19-39,44-46` — ベンチ用ツールが初期値 `0` を設定し、`--env` 値で上書きした環境を subprocess に渡す処理。
- `docs/INTEL_ARC.md:123,142-147`、`docs/INTEL.md:140-141` — `0` を勧める文書上の記述。外部 runtime の効果を裏付ける Strata 実装ではありません。
- 候補一覧には `docs/envvars/000_envvers.md:1662` に掲載されています。リポジトリ全体の完全一致検索では、実行コード上の直接参照は Dockerfile と ARC ベンチ用ツールだけで、engine による値の読み取りは確認できませんでした。
