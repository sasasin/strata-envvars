# `STRATA_ALLOW_UNPINNED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Hugging Face 上で Strata が固定した revision が見つからず、HTTP 404 になったとき、モデルファイルまたは MTP checkpoint をリポジトリの現在のファイルへ切り替えて取得するかを許可する、セットアップ用の opt-out です。通常の pinned 取得に使う変数ではなく、Strata engine やサーバーの実行時設定でもありません。通常ファイルは `terminal/setup.py` の `allow_unpinned()` と `download()`、MTP テンソルは `terminal/tools/mtp_fetch.py` の `resolve_repo()` が読み取ります（`terminal/setup.py:148-156,3513-3572`; `terminal/tools/mtp_fetch.py:347-364`）。

## 値と判定

両方の読み取り箇所が `(os.environ.get("STRATA_ALLOW_UNPINNED") or "").strip() == "1"` を使います。環境変数の文字列全体を前後 strip した後、大小文字を区別して `1` と完全一致するかだけを判定します。数値変換はありません。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `setup.py` のモデルファイル取得 / `mtp_fetch.py` の MTP 取得 | 無効 | `1`、` 1 `（strip 後に `1`） | 空文字、`0`、`01`、`true`、`TRUE`、`1x`、`x1` |

有効値でも、固定 revision の取得が成功した場合には動作を変えません。通常ファイルでは pinned URL の HEAD が 404 となり、URL が pinned revision を含む場合に判定されます。MTP では pinned revision の index HEAD が 404 となった場合に限って判定されます（`terminal/setup.py:3557-3572`; `terminal/tools/mtp_fetch.py:351-364`）。

## 有効になる条件

- 通常の `download()` は HTTP(S) の URL を使います。固定 revision を指す Hugging Face URL の HEAD が 404 であることが必要です。404 以外のエラー、pinned revision を含まない URL、`file://` やローカルパスのコピーではこの変数による切替は行いません（`terminal/setup.py:3537-3545,3557-3573`）。
- 通常ファイル取得で値が無効なら、`fail()` が「the pinned version of … is no longer on Hugging Face」と更新案内を出し、setup を終了コード 1 で止めます。有効なら URL の revision 部分を `main` に置き換えます（`terminal/setup.py:1049-1055,3563-3572`）。
- MTP 取得でも Hugging Face の checkpoint index が `REVISION` の URL で 404 になることが条件です。`STRATA_MTP_REVISION` が設定されていればその revision が使われ、未設定なら内蔵 pinned revision です。値が無効ならエラーメッセージを出して終了します。有効なら `REPO` の revision を `main` に置き換えます（`terminal/tools/mtp_fetch.py:43-58,347-364`）。
- `setup.py` は `fetch_mtp()` の子プロセスへ既存環境を渡したうえで `STRATA_SOURCE` を設定します。そのため、この変数も通常は子プロセスに継承されます。`--source modelscope` / `STRATA_SOURCE=modelscope` の場合、MTP ツールは ModelScope の `master` URL を使い、Hugging Face pinned URL の 404 切替分岐を通りません（`terminal/setup.py:1160-1164`; `terminal/tools/mtp_fetch.py:47-58,351-364`）。
- MTP を取得しないモデル状態や設定（既存 MTP ファイルがある、`--mtp off`、`--drafter dflash2`、モデル一覧に MTP がない、stream 条件で MTP を使わない等）では `fetch_mtp()` 自体が呼ばれず、この変数はそこで評価されません（`terminal/setup.py:11297-11321`; `12474-12494`）。
- OS、GPU backend、build macro、サーバー起動、通常推論 CLI による追加条件は、読み取り箇所からは確認できません。通常ファイル取得または MTP 取得が実行されるかどうかが実質的な適用条件です。

## 実行時の詳細

値は import 時には保存されず、通常ファイルでは `download()` の pinned HEAD 要求が 404 になったときに `allow_unpinned()` が環境を読みます。同関数は値を毎回読み直しますが、許可時の注意ログだけは `_unpinned_said` によって setup プロセス内で一度に抑制されます（`terminal/setup.py:145-156,3557-3572`）。MTP ツールは起動後に `resolve_repo()` で読み取り、起動時に環境から決めた `REPO` を変更します。取得コマンドのたびに別プロセスが起動されるため、各起動ではその時点の環境値が使われます（`terminal/setup.py:1160-1173`; `terminal/tools/mtp_fetch.py:47-58,515-535`）。実行中に環境を変更しても、既に切り替えた URL や進行中の取得には反映されません。

通常ファイルでは、`main` から取得したサイズを使ってダウンロードし、`pin=None` のまま後段へ進むため、固定 SHA-256 検証を行わず完了マークを作成します。通常の pinned 取得では固定サイズや SHA-256 が検査されます（`terminal/setup.py:3563-3572,3582-3589,3621-3631`）。既に `.done` 判定を通過するファイルはネットワーク要求前にスキップされ、この変数による再取得はありません（`terminal/setup.py:3513-3527`）。

MTP では、切替後の `REPO` は `PINNED` と異なる URL になります。実装は `pinned()` が真のときだけ各テンソルの `SHA256` を照合するので、Hugging Face の pinned 版 404 から `main` に切り替えた経路ではテンソル SHA-256 検査を行いません。ファイル範囲のサイズ整合性は検査します（`terminal/tools/mtp_fetch.py:334-336,347-364,433-475`）。これは同ファイルのコメントにある「every tensor is still checked against the pinned SHA256」という説明と異なる現行実装です。MTP の `verify` も `pinned()` が偽なら何も検証しません（`terminal/tools/mtp_fetch.py:482-489`）。

## ログと測定値

有効時、通常ファイル経路は `warn()` を通じて次の注意を表示します（文頭には `  [!]  ` が付きます）。

```text
STRATA_ALLOW_UNPINNED=1: a model file whose pinned version is gone from Hugging Face is taken from its current files instead, and is NOT checked against a SHA-256. Unset it to get the checked files only
```

続けて対象ファイル名を含む `not at the pinned revision any more; downloading the repository's current file (not checked against a SHA-256)` も表示されます（`terminal/setup.py:1044-1047,152-156,3563-3572`）。無効時の停止理由と終了コード 1 は上記「有効になる条件」のとおりです。

MTP 経路では標準エラーへ次の警告を表示します。無効時は `the pinned version of the checkpoint (...) is no longer on Hugging Face: update Strata` を出して終了します（`terminal/tools/mtp_fetch.py:355-364`）。

```text
STRATA_ALLOW_UNPINNED=1: the checkpoint's pinned revision <revision> is gone: reading its current files (main); every tensor is still checked against the pinned SHA256
```

この MTP 警告文の「every tensor is still checked…」は実際の検査条件と一致しません。切替後は `pinned()` が偽となり SHA-256 比較を省略するため、実動作は「実行時の詳細」に記したコードに従います。測定値は該当しません。

## 根拠

- `terminal/setup.py:112-123,145-156,3513-3573,3621-3631` — pin 定義、値判定、通常ダウンロードでの fallback、警告、検証。
- `terminal/setup.py:1044-1055,1160-1177,11297-11321,12474-12494` — 観測可能な警告・失敗、MTP 子プロセス呼び出し条件。
- `terminal/tools/mtp_fetch.py:43-61,334-364,433-489,515-539` — MTP の URL と値判定、SHA 検査条件、コマンド実行時の経路。
