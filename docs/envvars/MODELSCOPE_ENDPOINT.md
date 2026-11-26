# `MODELSCOPE_ENDPOINT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

ModelScope を明示的にダウンロード元として選んだセットアップで、ModelScope API とモデルファイル URL の基底ホストを指定する。変数だけでは配信元を ModelScope に切り替えない。通常の `setup.py` は `ms_endpoint()` でこの値を使い、同梱ツール `tools/mtp_fetch.py` も MTP テンソル取得時に同じ値から URL を組み立てる。根拠: `terminal/setup.py:169-184,212-220,252-267`、`terminal/tools/mtp_fetch.py:52-57`。

## 値と判定

両読み取り箇所とも `(os.environ.get("MODELSCOPE_ENDPOINT") or "").strip().rstrip("/") or <既定値>` で文字列を処理する。空白を前後から除去し、その後末尾の `/` をすべて取り除く。URL 形式やホスト到達性の事前検証はしない。根拠: `terminal/setup.py:182-183`、`terminal/tools/mtp_fetch.py:55-57`。

| 読み取り箇所 | unset・空文字・空白だけ | 設定値の処理と例 |
|---|---|---|
| `setup.py` | `https://www.modelscope.cn` | `" https://mirror.example/ "` → `https://mirror.example`。`https://mirror.example///` も末尾スラッシュを除去。`/` や `///` は除去後に空になり、既定値に戻る。 |
| `tools/mtp_fetch.py` | `https://www.modelscope.cn`（ただし ModelScope が選ばれた場合にだけ読み取る） | 同じ trim と末尾スラッシュ除去。`not a URL` のような文字列も検証で拒否せず URL に連結するため、後続のリクエストで失敗し得る。数値・大小文字・URL scheme の検証はない。 |

`setup.py` は `model_source()` のキャッシュキーを作る際にも endpoint を含めるため、ModelScope を選ばない場合でもその関数呼び出しでは値を読み取る。一方、取得先が ModelScope になるかは別の `STRATA_SOURCE` 判定による。根拠: `terminal/setup.py:178-183,212-220`。

## 有効になる条件

- セットアップの `--source modelscope` または `STRATA_SOURCE=modelscope`（小文字化されるため大文字小文字を区別しない値）を指定する。`--source` は `STRATA_SOURCE` に設定され、`--source auto` は既定で Hugging Face を選ぶ。`--source huggingface` も Hugging Face を選ぶ。`model_source()` は `ms` も ModelScope の別名として受け付ける。根拠: `terminal/setup.py:212-220,11536-11539,11619-11623`。
- 通常のモデルファイルでは、セットアップが認識する Hugging Face リポジトリ URL が対象である。ModelScope が応答しなければ Hugging Face へ fallback する。根拠: `terminal/setup.py:244-249,3546-3552`。
- MTP テンソル取得では、セットアップが起動する `tools/mtp_fetch.py fetch` に `model_source()` の結果を `STRATA_SOURCE` として渡し、元の環境を継承する。MTP の取得自体が必要なセットアップ経路で、`STRATA_SOURCE` が `ms` または `modelscope` のとき endpoint が使われる。根拠: `terminal/setup.py:1160-1164`、`terminal/tools/mtp_fetch.py:52-57`。
- OS、GPU backend、build macro による条件分岐は、これらの Python 読み取り箇所にはない。

## 実行時の詳細

`setup.py` の `ms_endpoint()` は呼び出すたびに環境を読み直す。ModelScope 選択結果 `_sources` のキャッシュキーは `(STRATA_SOURCE, HF_ENDPOINT, ms_endpoint())` なので、endpoint が変われば異なるキーとなる。モデル取得では正規化した endpoint に `/models/{repo}/resolve/master/{path}` を足し、メタデータ取得では `/api/v1/models/{repo}/repo/files?Recursive=true` を足す。ModelScope の通常ファイル取得先が応答しない場合は `ModelScope does not answer; downloading it from ...` と警告し、Hugging Face に戻る。根拠: `terminal/setup.py:178-183,212-220,252-267,3546-3552`。

`tools/mtp_fetch.py` はモジュール読み込み時に `STRATA_SOURCE` を判定し、ModelScope が選ばれているときだけ endpoint を一度読み、`REPO` と `PINNED` を `.../models/Qwen/Qwen3.8-Flash-Next/resolve/master/` に設定する。この経路では `STRATA_MTP_REVISION` を使った Hugging Face URL は後続で上書きされる。単体実行で `--repo` を渡すと、引数処理時に `REPO` がその値で上書きされる（セットアップからの起動では `--repo` を渡さない）。セットアップから起動された子プロセスでは、endpoint は `run()` が複製した環境を通じて継承される。実行中に環境変数を変更しても、同プロセスの `mtp_fetch.py` が保持する URL は変わらない。根拠: `terminal/setup.py:1142-1152,1160-1173`、`terminal/tools/mtp_fetch.py:43-57,515-525`。

MTP の取得失敗が `netpolicy.NetFailure` になると stderr に `[X]` の見出しと次の手順を出し、ネットワークなしなら終了コード 5（セットアップは MTP なしで続行）、応答なしなら終了コード 4（セットアップを停止）を返す。設定 endpoint の形式不正を専用に検出する処理はなく、URL リクエストの結果として失敗経路に進む。根拠: `terminal/tools/mtp_fetch.py:515-539`、`terminal/setup.py:1170-1189`。

## ログと測定値

通常のモデルファイルの ModelScope 接続に失敗すると、`setup.py` は `{what or dst.name}: ModelScope does not answer; downloading it from {hf_endpoint()}` を警告として出す。ModelScope を選んだ通常セットアップでは `Downloading from ModelScope ({ms_endpoint()}); --source huggingface downloads from Hugging Face` も表示する。MTP 取得失敗時の `[X]` 見出しと次の手順は `mtp_fetch.py` が stderr に出す。変数値だけを示す専用ログはない。性能測定値は該当しない。根拠: `terminal/setup.py:3551-3552,12393-12397`、`terminal/tools/mtp_fetch.py:536-539`。

## 根拠

- `terminal/setup.py:169-184` — ModelScope の既定 endpoint と値の正規化。
- `terminal/setup.py:212-220,244-267` — 配信元選択、endpoint の URL 使用箇所。
- `terminal/setup.py:3546-3552,3584-3588` — ModelScope URL の選択、応答なし時の fallback。
- `terminal/setup.py:1142-1152,1160-1189` — 環境継承と MTP 子プロセスの終了経路。
- `terminal/setup.py:11536-11539,11619-11623` — `--source` と `STRATA_SOURCE` の指定。
- `terminal/tools/mtp_fetch.py:43-61,515-539` — MTP 側の読み取り条件・既定値・失敗表示と終了コード。
