# `HF_ENDPOINT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Strata のセットアップが Hugging Face 上のモデルファイルを取得するときに使う URL のホスト部分を差し替える。モデルの各リポジトリ URL はこの値、リポジトリ名、固定 revision から構成される。これはエンジンの実行時設定ではなく、主に `setup.py` と MTP取得ツール `tools/mtp_fetch.py` のダウンロード先設定である。モデル取得前に手動でダウンロードしたファイルを配置する経路や、セットアップ完了後のサーバーには作用しない。

## 値と判定

| 値 | Strata の扱い |
|---|---|
| 未設定または空文字 | `https://huggingface.co` を使う。 |
| 空白だけ | 前後の空白を除去した結果が空になるため、既定 URL を使う。 |
| URL文字列 | 前後の空白を除去し、末尾の `/` をすべて除いてホスト文字列として使う。 |
| 不正な文字列 | URL形式・scheme・host の検証や拒否はこの値の正規化箇所にはない。生成された URL が後段の HTTP リクエストで失敗し得る。 |

数値変換、真偽値 parse、大小文字の変換は行わない。例えば `https://hf-mirror.com/` は `https://hf-mirror.com` になり、値にリポジトリ以下のパスが含まれていれば、そのまま後続パスが連結される。

## 有効になる条件

- `setup.py` が Hugging Face のモデルまたは vision encoder をダウンロードする場合、`HF_ENDPOINT` を先頭に付けた URL が使われる。対象リポジトリと revision は `HF_REVISIONS` の固定値を使い、404 で固定 revision が見つからない場合は `main` に切り替える。
- `--source modelscope` または `STRATA_SOURCE=modelscope` が選ばれると、対応ファイルについてまず ModelScope を使う。ModelScope が応答しない場合には `HF_ENDPOINT` の URL にフォールバックする。`HF_ENDPOINT` 自体が ModelScope 選択を有効化することはない。`--source` は `setup.py` 内で `STRATA_SOURCE` に設定され、`model_source()` は `ms` / `modelscope` だけを ModelScope と判定する。
- セットアップが MTP draft layer を取得するとき、`tools/mtp_fetch.py` に同じプロセス環境が渡される。通常はこの値を使うが、`STRATA_SOURCE` が `ms` / `modelscope` の場合は同ツールが `MODELSCOPE_ENDPOINT` の URL で上書きする。
- `tools/quantscope.py` にも同名の読み取りがありますが、ファイル先頭が外部プロジェクト `quantscope` のコピーであると明記されています。その実装は調査手順の除外対象のため、ここでは Strata 所有の挙動として扱いません。`tools/strata_inspect.py` の説明コメントは委譲先の機能を記したものです。

## 実行時の詳細

`setup.py` の `hf_endpoint()` は呼び出しごとに `os.environ.get()` を評価して正規化する。一方、モデルURLはモジュール読み込み中に `hf()` を通して作られ、`HF`、`FAMILIES` のモデル／encoder URLに格納される。そのため通常の起動では、起動時の `HF_ENDPOINT` がセットアップのダウンロードURLに反映される。プロセス内で値を後から変更した場合、既に作成済みの `HF` / `FAMILIES` のURLは再構築されないが、後から呼ばれる `hf_endpoint()` のログ表示やフォールバック先は新しい値を読む。

`model_source()` は `STRATA_SOURCE` を trim・小文字化し、`ms` または `modelscope` のときだけ ModelScope を選択する。その他（未設定時の `auto`、`huggingface` など）は Hugging Face のままである。判定結果は `STRATA_SOURCE`、生の `HF_ENDPOINT`、ModelScope endpoint をキーとする辞書にキャッシュされる。`HF_ENDPOINT` はこの選択結果ではなく Hugging Face 側の URL に使われる。

`setup.py` は ModelScope を選んだ場合、ダウンロード開始時に選択元を表示し、`HF_ENDPOINT` が既定値と異なる場合は `Downloading from <値> (HF_ENDPOINT)` を表示する。実際の HTTP ダウンロードは HEAD と Range リクエストを行い、固定 revision が 404 の場合は警告して `main` URL を試す。通信失敗時には到達できないホスト名を含むエラーを出す。

MTPツールでは `HF_ENDPOINT` をモジュール読み込み時に一度読み、`REPO` と `PINNED` の URL を作る。固定revisionが404なら stderr に切替メッセージを出して `REPO` を `main` に変更する。`PINNED` は固定revisionのまま保持され、固定版のMTPテンソルは SHA-256 で照合される。セットアップから子プロセスとして起動する際は環境を継承しつつ `STRATA_SOURCE` を上書きするため、通常、親の `HF_ENDPOINT` は子にも届く。`STRATA_SOURCE=modelscope` の場合はツール側で ModelScope URL に置き換わる。

## 根拠

- `setup.py:74-85` — 既定値、環境値の strip / 末尾 slash 除去、Hugging Face URL の組み立て。
- `setup.py:97-128` — `STRATA_SOURCE` による選択条件とキャッシュキー。
- `setup.py:165`, `setup.py:265-299` — モジュール読み込み時に `HF_ENDPOINT` を使ってモデル／encoder URLを作る箇所。
- `setup.py:1449-1491` — ModelScope の到達確認、HF fallback、HTTP取得と404時のrevision fallback。
- `setup.py:4894-4895` — `--source` を `STRATA_SOURCE` に設定。
- `setup.py:5477-5483` — 選択元と `HF_ENDPOINT` の表示。
- `setup.py:5541-5553` — MTP取得サブプロセスへの環境引き継ぎと `STRATA_SOURCE` の上書き。
- `tools/mtp_fetch.py:29-43`, `tools/mtp_fetch.py:146-173` — MTP URLの生成、ModelScopeによる上書き、404時のfallback。
- `docs/INSTALL.md:272-281` — 手動設定例と、固定revision・チェックを維持してミラーから取得するという利用者向け説明。コード上もモデルURLの固定revisionとMTPテンソルの固定版ハッシュ検証を確認した。
