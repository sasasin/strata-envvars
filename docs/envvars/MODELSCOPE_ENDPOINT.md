# `MODELSCOPE_ENDPOINT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

セットアップが ModelScope をダウンロード元として選んだ場合に使う ModelScope のベース URL を指定します。セットアップの通常の `auto` 選択は Hugging Face のままで、`MODELSCOPE_ENDPOINT` を設定しただけではダウンロード元は切り替わりません。ModelScope を選ぶには `--source modelscope` または `STRATA_SOURCE=modelscope` が必要です。

この値は `setup.py` のモデルファイル URL と ModelScope API URL、および ModelScope 選択時に起動する `tools/mtp_fetch.py` の MTP checkpoint URL に使われます。

## 値と判定

| 環境変数の値 | 使用する endpoint |
|---|---|
| 未設定または空文字 | `https://www.modelscope.cn` |
| 空白だけ | `https://www.modelscope.cn`（前後の空白を除いた結果が空） |
| その他 | 前後の空白と末尾の `/` をすべて除いた文字列 |

URL形式、scheme、ホスト名の検証や大文字小文字の変換はありません。文字列の途中にある空白やパスはそのままです。たとえば ` https://mirror.example/ms/// ` は `https://mirror.example/ms` になります。後から endpoint が不正と判明した場合の処理は、通常の通信失敗や ModelScope 到達確認の fallback に委ねられます。

## 有効になる条件

- `setup.py` は `--source modelscope` を受け付けます。`--source` を省略した場合、`STRATA_SOURCE` を読み、前後の空白を除いて小文字化した値が `ms` または `modelscope` の場合だけ ModelScope を選びます。他の値（`auto`、`huggingface`、未知の文字列を含む）は Hugging Face 扱いです。
- ModelScope のダウンロード URL へ変換するのは、ModelScope が選ばれ、かつ URL がセットアップの対応 repository に属する Hugging Face ファイルとして認識された場合です。`download()` は先にそのファイルの ModelScope URL へ HEAD 要求を行い、到達しなければ警告を出して Hugging Face の URL で続行します。
- MTP の `tools/mtp_fetch.py` は `STRATA_SOURCE` が `ms` または `modelscope` の場合にだけこの endpoint を読みます。それ以外では `HF_ENDPOINT`（未設定時 `https://huggingface.co`）を使います。
- macOS アプリ経路や SYCL 専用 setup など、`setup.py` が別のセットアップ実装へ早期に移る経路では、この関数によるファイル取得が使われるとは限りません。

## 実行時の詳細

`ms_endpoint()` は呼び出しごとに環境変数を読み、設定値の正規化を行います。`model_source()` は `(STRATA_SOURCE, HF_ENDPOINT, ms_endpoint())` の組をキーに選択結果をキャッシュするため、通常の起動中は各設定組ごとに一度判定します。endpoint の文字列自体は `ms_endpoint()` 側でキャッシュしません。

ModelScope を選んだセットアップは `${endpoint}/models/{repo}/resolve/master/{path}` からファイルを取得します。対応ファイルのサイズと SHA-256 は ModelScope API `${endpoint}/api/v1/models/{repo}/repo/files?Recursive=true` から取得します。ModelScope は pinned revision ではなく repository の現在のファイルを返す扱いで、セットアップは公開されたサイズ・SHA-256 と照合します。MTP fetch も ModelScope の `master` を使いますが、テンソルを Strata に記録された checkpoint の SHA-256 と照合します。これらは Strata が行う URL 構築、要求、照合の範囲の説明であり、ModelScope サーバー自体の挙動を保証するものではありません。

`setup.py` は MTP fetch を子プロセスとして起動する際、親プロセスの環境を含む環境辞書を渡し、`STRATA_SOURCE` を選択結果で上書きします。そのため `MODELSCOPE_ENDPOINT` は通常その子プロセスにも引き継がれます。endpoint の変更を実行中に反映するための監視や再設定処理はありません。

## 根拠

- `setup.py:147-182` — endpoint の既定値、正規化、source 選択とキャッシュキー。
- `setup.py:193-216, 2831-2858` — 対応ファイルの判定、URL/API 構築、ModelScope 到達確認と Hugging Face への fallback。
- `setup.py:8622-8625, 8673-8678` — `--source` の選択肢と `STRATA_SOURCE` への反映。
- `setup.py:890-908, 8488-8495, 9507-9515` — MTP fetch 子プロセスへの環境引き継ぎと起動箇所。
- `tools/mtp_fetch.py:37-51` — ModelScope 選択時の endpoint 読み取り、MTP URL の組み立て、その他の場合の Hugging Face endpoint。
- `setup.py:147-152, 9421-9425` — ModelScope が current files を返すことと、セットアップ側の照合についてのソース内説明。
