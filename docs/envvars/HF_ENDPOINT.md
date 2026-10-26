# `HF_ENDPOINT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Hugging Face を使うセットアップ時のファイル取得先ホストを、既定の `https://huggingface.co` からミラーなどへ差し替える。環境変数そのものがダウンロードを開始するわけではなく、セットアップが Hugging Face の URL を組み立てるときに参照する。エンジンの実行時設定ではない。

対象には通常モデルの固定 revision ファイル、画像モデル、MTP ドラフト層テンソルが含まれる。また、同梱の `tools/quantscope.py` は Hugging Face リポジトリを調べる際にこの値を使う。

## 値と判定

| 読み取り箇所 | 未設定・空 | 設定値の処理 |
| --- | --- | --- |
| `setup.py` の `hf_endpoint()` | 既定値 `https://huggingface.co` | `.strip()` で前後の空白を除去し、`.rstrip("/")` で末尾の `/` をすべて除去。残りが空なら既定値 |
| `tools/mtp_fetch.py` | 既定値 `https://huggingface.co` | `.strip()` と `.rstrip("/")` を適用して URL を組み立てる。モジュール読み込み時に一度評価 |
| `tools/quantscope.py` | 既定の Hugging Face API / ファイル URL | `os.environ.get()` が真なら値を使い、末尾 `/` だけ除去。空文字は既定 URL のまま。モジュール読み込み時に一度評価 |

値の URL 構文、scheme、ホストの妥当性をこの変数の読み取り箇所では検証しない。`setup.py` と `mtp_fetch.py` では URL 文字列へ直接連結するため、空白除去後に `https://` 等を含む完全なベース URL を指定する前提である。`quantscope.py` は前後空白を除去しない。

## 有効になる条件

- セットアップ本体では、未取得の Hugging Face ファイルをダウンロードする処理で有効。既に `.done` マーク付きで取得済みのファイルは、`download()` がサーバーへアクセスせず戻るため、この値を変えてもその取得済みファイルの再取得は起こらない。
- `--source modelscope` または `STRATA_SOURCE=modelscope`（別名 `ms`）を選んだ通常モデルの取得先は ModelScope になる。`HF_ENDPOINT` は Hugging Face のミラー選択であり、ModelScope を自動選択するものではない。ModelScope の該当ファイルが応答しない場合、セットアップは Hugging Face 側へ戻り、`hf_endpoint()` が返すホストを使う。
- MTP 取得ツールは直接実行時、`STRATA_SOURCE` が `ms` / `modelscope` なら `MODELSCOPE_ENDPOINT` の URL を使い、`HF_ENDPOINT` を使わない。セットアップ経由では `fetch_mtp()` が選択済み `STRATA_SOURCE` を子プロセス環境へ渡す。環境の他の値は子プロセスへ引き継がれる。
- `quantscope.py` では `hf:<owner>/<repo>` の参照先に反映される。`ms:`、任意 URL、ローカルファイルを指定する経路はこの上書き対象ではない。

## 実行時の詳細

`setup.py` の `hf_endpoint()` は呼び出しごとに `os.environ` を読む関数で、値を静的キャッシュしない。`hf(repo)` はそのホストに `/<repo>/resolve/<HF_REVISIONS[repo]>/` を加え、固定 revision の URL を作る。`ready_fetch()` は各必要ファイルについて URL を作り、`download()` に渡す。画像モデルは `QI.file_url(name, hf_endpoint())` を `download()` に渡す。セットアップのモデル選択画面は、既定値と異なる場合 `Downloading from <host> (HF_ENDPOINT)` と表示する。

`download()` が ModelScope へ切り替えるのは、ソース選択が ModelScope で、URL が対応する Hugging Face ファイルとして認識され、対応する ModelScope URL が応答した場合。応答しなければ `ModelScope does not answer; downloading it from <hf_endpoint>` の警告を出して Hugging Face URL を維持する。ダウンロード後のサイズ・SHA-256 照合などはこのホスト指定とは独立しており、ミラー指定だけでピン検証を無効化しない。固定 revision が見つからない場合の未固定取得は `STRATA_ALLOW_UNPINNED=1` の別条件である。

`tools/mtp_fetch.py` はモジュール読込時に `HF_ENDPOINT` から `REPO` と `PINNED` のベース URL を作る。セットアップから起動した場合も子プロセスは別プロセスなので、実行開始時の環境値で決まる。`tools/quantscope.py` もモジュール読込時に Hugging Face API とファイル URL のテンプレートを差し替える。

## 文書との照合

`docs/SAFETY.md` はモデルファイル、画像リーダー、MTP の取得先について、Hugging Face または `HF_ENDPOINT` で指定したミラーと記載しており、セットアップおよび MTP ツールの実装と一致する。測定値や性能への効果はソース、関連資料とも確認できないため記載しない。

## 根拠

- `setup.py:106-117`: 既定値、値の正規化、固定 revision URL の生成。
- `setup.py:174-182`: `STRATA_SOURCE` による source 選択。`HF_ENDPOINT` はキャッシュキーにも含まれるが、source を ModelScope に切り替える条件ではない。
- `setup.py:2831-2853`: 取得済みファイルの早期終了、ModelScope 選択時の到達確認と Hugging Face への fallback。
- `setup.py:3140-3161`: 通常モデルファイルの URL 生成と取得。
- `setup.py:4890-4910`: 画像モデルの URL 生成と取得。
- `setup.py:902-918`: MTP 取得子プロセスの起動と `STRATA_SOURCE` の引き渡し。
- `setup.py:9413-9427`: Hugging Face / ModelScope の取得先表示。
- `tools/mtp_fetch.py:37-51`: MTP 用 URL の起動時生成と ModelScope 指定時の分岐。
- `tools/quantscope.py:34-43,78-92`: `hf:` 用 API / ファイル URL の既定値と環境変数による差し替え。
- `docs/SAFETY.md:41-47`: インストール時の接続先についての説明。
