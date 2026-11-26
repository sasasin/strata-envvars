# `STRATA_SOURCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

セットアップ時にモデルファイルと MTP（speculative decoding 用ドラフト層）の取得元を Hugging Face にするか ModelScope にするか選ぶ。既定の `auto` は常に Hugging Face を選び、疎通失敗を理由に Strata が自動で ModelScope へ切り替えることはない。ModelScope が選ばれても、同サービスに応答がないモデルファイルは Hugging Face へ fallback する。モデルの実行時設定を変える変数ではない。選択処理は `terminal/setup.py` の `model_source()`、MTP 取得側は `terminal/tools/mtp_fetch.py` にある（`terminal/setup.py:212-220, 3546-3552`; `terminal/tools/mtp_fetch.py:43-57`）。

## 値と判定

セットアップの `model_source()` は `os.environ.get("STRATA_SOURCE") or "auto"` の結果を前後空白除去し、小文字化する。`ms` と `modelscope` だけを ModelScope と判定し、それ以外はすべて Hugging Face になる。空文字は `auto` と同じ。空白だけの値は strip 後に空文字となり、Hugging Face になる。無効値をエラーにしたり警告したりしない（`terminal/setup.py:212-220`）。

| 経路 | 未設定・空文字 | ModelScope になる値 | Hugging Face になる値 |
|---|---|---|---|
| `terminal/setup.py` のセットアップ | `auto` → Hugging Face | `modelscope`, `ms`（大文字小文字を区別せず、前後空白を除去） | `auto`, `huggingface`、空白のみ、その他すべて。値全体を enum として検証しない |
| セットアップ CLI `--source` | 指定なしなら既存環境変数を使う | `modelscope` | `auto`, `huggingface`。CLI はこの 3 値だけ受け付ける |
| `terminal/tools/mtp_fetch.py` の直接実行 | Hugging Face | `modelscope`, `ms`（前後空白を除去し小文字化） | 空文字、空白のみ、その他すべて |

CLI の `--source` は `choices=("auto", "modelscope", "huggingface")` で検証され、指定されると既存の `STRATA_SOURCE` を上書きする。`--source ms` は CLI では拒否されるが、環境変数では受理される（`terminal/setup.py:176, 11536-11539, 11606-11623`; Mac セットアップにも同じ選択肢と上書きがある: `engine/metal/setup_mac.py:392-410`）。

## 有効になる条件

- これは `terminal/setup.py` と同梱セットアップ用スクリプトが読む値であり、Strata C++ エンジンやサーバーのモデル実行時には参照されない（全参照の走査結果。直接の読み取りは `terminal/setup.py:216` と `terminal/tools/mtp_fetch.py:55`）。
- `setup.py` の通常のモデル取得で ModelScope を使うのは、選択結果が `modelscope` で、取得 URL が Strata の把握する Hugging Face リポジトリ (`HF_REVISIONS`) のファイルに対応するときだけ。ModelScope は `master` の URL にマップされる。疎通確認が失敗すると警告を出し、元の Hugging Face URL から取得する（`terminal/setup.py:244-253, 3546-3552`）。
- ModelScope 用のモデル URL は `MODELSCOPE_ENDPOINT`（空・空白なら `https://www.modelscope.cn`）から組み立てる。Hugging Face 側の URL は `HF_ENDPOINT` の設定を使う。これらは別の環境変数で、`STRATA_SOURCE` 自体の値判定には使わない（`terminal/setup.py:182-184, 252-253, 3551`）。
- ready-made pack の取得経路は `STRATA_SOURCE=modelscope` でも ModelScope に切り替わらず、Hugging Face のみである旨を警告して通常の ready pack 取得へ進む（`terminal/setup.py:12380-12386`）。ローカルファイルのコピーや、すでに揃ったファイルにも取得元選択は作用しない（`terminal/setup.py:3513-3546, 12387-12414`）。
- MTP の取得はセットアップが MTP 層を必要とし、既存の層がなく、オフ指定や別 drafter による取得抑止がない場合にだけ行われる。Mac 経路でも `use_mtp` が真で成果物がないときに fetch する（`terminal/setup.py:11297-11321, 12474-12494`; `engine/metal/setup_mac.py:567-584`）。セットアップは選択済みの `model_source()` の結果を子 `mtp_fetch.py` に `STRATA_SOURCE` として明示的に渡す（`terminal/setup.py:1160-1173`; Mac: `engine/metal/setup_mac.py:582-584`）。
- `mtp_fetch.py` を直接起動し `--repo` を指定した場合、コマンドライン値が `REPO` を上書きする。これはソース環境変数の選択とは別に取得先 URL を差し替える経路（`terminal/tools/mtp_fetch.py:515-525`）。

## 実行時の詳細

`terminal/setup.py` の `model_source()` は呼び出しごとに現在の環境変数を読み直し、正規化後の値、`HF_ENDPOINT` の生値、正規化した ModelScope endpoint の組を `_sources` のキーにして結果をキャッシュする。同じ組での呼び出しはキャッシュ済み結果を返す。いずれかの値が変われば別キーとして再判定されるため、プロセス内で環境を変更した場合も次の呼び出しで反映される（`terminal/setup.py:178, 182-184, 212-220`）。ただし通常の CLI 実行では `--source` を解析後に環境へ書き込み、その後のセットアップ処理が参照する（`terminal/setup.py:11606-11623`）。

`mtp_fetch.py` は import 時に `STRATA_SOURCE` を一度読み、ModelScope のときは `REPO` と `PINNED` を ModelScope の `master` URL に設定する。以降の環境変更は再 import なしでは反映されない。既定の Hugging Face 経路では固定 `REVISION` を使い、ModelScope 経路ではリポジトリの現行ファイルを使う構成だが、MTP の各テンソルは固定チェックポイントの SHA-256 と照合される（`terminal/tools/mtp_fetch.py:43-57, 334-336, 407-475`）。

通常のモデルファイル取得で ModelScope が応答しない場合は `"<file>: ModelScope does not answer; downloading it from <HF endpoint>"` の警告後に Hugging Face へ戻る。ready-made pack では `"these packs are on Hugging Face only: downloading them from ..."` と警告する。MTP 取得がネットワーク無応答なら子ツールは終了コード 4 を返し、セットアップは停止案内を出して終了する。完全オフライン時の終了コード 5 では MTP を使わずにセットアップを続ける。これらの取得失敗は値の変換エラーではない（`terminal/setup.py:1170-1189, 12382-12386`; `terminal/tools/mtp_fetch.py:536-539`）。

## ログと測定値

通常の Hugging Face 選択時にソース選択だけを示すログは確認できない。ModelScope 選択時のダウンロード案内・警告、および ModelScope 疎通失敗時の fallback 警告は `terminal/setup.py:3551, 12384-12399` にある。MTP の継続失敗では `terminal/tools/mtp_fetch.py:457-460` が取得エラーと接続数を stderr に出し、成功時はテンソルごとに `done` を stderr に出す（`terminal/tools/mtp_fetch.py:452-476`）。

`docs/DETAILS.md` にこの環境変数の追加動作説明は見当たらなかった。`docs/SAFETY.md:45-46` は ModelScope を明示選択した場合のみ使い、自動切替しない点で実装と一致する。MTP の完全オフライン時に層なしでセットアップ継続する条件は同資料の記述だけでは詳述されていないため、ここではコードを根拠に記載した。

## 根拠

- `terminal/setup.py:169-220` — ソース選択肢、判定方法、キャッシュ。
- `terminal/setup.py:244-253, 3513-3556` — 対象 URL のマッピング、ModelScope 接続失敗時の fallback。
- `terminal/setup.py:11315-11321, 1160-1189, 12380-12414` — MTP の取得条件、子プロセスへの値の引き渡し、観測可能な終了経路。
- `terminal/tools/mtp_fetch.py:43-57, 334-336, 407-476, 515-539` — import 時の選択、ModelScope URL、取得・検証・失敗経路。
- `engine/metal/setup_mac.py:392-410, 567-584` — Mac セットアップ CLI の上書きと MTP への引き渡し。
