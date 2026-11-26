# `HF_ENDPOINT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Hugging Face を使う Strata のモデル・画像関連ファイルの URL のホスト部分を指定する。setup の通常モデル、ready-made pack、画像 reader、MTP draft tensors、DFlash2 drafter は、この値を基に Hugging Face のパスを組み立ててダウンロードする。設定してもファイル名・revision・Strata 側のサイズや SHA-256 検証は切り替わらない。モデル取得元を ModelScope にする設定ではなく、`--source modelscope` / `STRATA_SOURCE=modelscope` が優先される。ただし Hugging Face 専用ファイルや ModelScope が応答しない場合の fallback URL はこの値を使う（`terminal/setup.py:129-137, 169-183, 212-220, 3546-3552, 3927-3948, 12380-12414`、`terminal/tools/mtp_fetch.py:43-57`）。

また、更新用 transfer helper は、`HF_TOKEN` または `HUGGING_FACE_HUB_TOKEN` があるとき、指定ホストを Hugging Face と認識して認証 header の送信を許可する。標準ホストと `HF_ENDPOINT` が指す host の比較にだけ使い、別 host への redirect では Authorization header を除く（`terminal/strata_control/transfer.py:220-251, 254-264, 298-316, 405-420`）。

## 値と判定

設定値を URL として検証する共通処理はない。経路により trim と空文字の扱いが異なる。

| 読み取り経路 | 未設定 | 設定時の変換 | 空文字・例 |
|---|---|---|---|
| setup の `hf_endpoint()`、drafting、pictures、MTP fetch | `https://huggingface.co` | 前後の空白を `strip()` で除き、末尾の `/` をすべて除く | 空文字または空白だけは既定 host。`https://mirror/` は `https://mirror` |
| 画像モデル host (`app/host/server/image-models.mjs`) | `https://huggingface.co` | 前後空白を trim し、末尾 slash を除去 | 空文字または空白だけは既定 host |
| transfer の HF host 判定 | host 比較に追加条件なし（標準 Hugging Face host は常に許可） | trim 後 URL parse、hostname を小文字化して完全一致 | 空文字は追加 host なし |
| `quantscope.py` | `https://huggingface.co` の HUBS 定義を維持 | 値が truthy の場合だけ末尾 `/` を除去。前後空白は除去しない | 空文字は未設定同様。`/` は空の base になる |
| `qwen4_intake.py` | `https://huggingface.co` | 末尾 `/` のみ除去。前後空白は除去しない | 明示的な空文字は空の base のまま。組み立て URL は `/api/...` 等になる |

URL の scheme・host・path の妥当性、大文字小文字、空白以外の文字、数値境界は検査しない。`https://mirror///` は trim する経路では `https://mirror`、`https://mirror///` の末尾 slash 除去だけをする経路でも同じになる。`quantscope.py` は空でない値に限って差し替え、`qwen4_intake.py` は環境変数が存在する空文字を既定値に戻さない（`terminal/setup.py:126-137`、`terminal/strata_control/drafting.py:241-249`、`terminal/strata_control/pictures.py:72-75`、`terminal/tools/mtp_fetch.py:46-57`、`terminal/tools/quantscope.py:34-44`、`terminal/tools/qwen4_intake.py:663-681`、`app/host/server/image-models.mjs:35-46`）。

## 有効になる条件

- setup のモデルファイル取得で Hugging Face URL が使われること。`--source modelscope`（または `STRATA_SOURCE=ms|modelscope`）なら一般の対応モデルは ModelScope URL を選ぶが、ready-made pack は Hugging Face 専用であり `HF_ENDPOINT` から取得する。通常モデルでも ModelScope が応答しない場合は `hf_endpoint()` が fallback 先になる（`terminal/setup.py:212-220, 3546-3552, 12382-12399`）。
- 取得対象ファイルが未取得であること。既存ファイルが検証済みなら download を省略する。モデルごとの pinned revision と検証は引き続き適用される（`terminal/setup.py:3932-3948, 12400-12419`）。
- MTP fetch は setup が起動する `tools/mtp_fetch.py` にも環境を渡す。setup は `STRATA_SOURCE` を明示的に設定して起動するが、`HF_ENDPOINT` はこの環境辞書から除去・上書きされない。MTP fetch は `STRATA_SOURCE` が ModelScope のとき ModelScope URL に切り替える（`terminal/setup.py:1160-1164`、`terminal/tools/mtp_fetch.py:48-57`）。
- DFlash2 fetch では呼び出し元から `endpoint` 引数が明示された場合、その値が環境変数より優先する。引数が `None` の経路で `HF_ENDPOINT` を読み、既存の検証済みファイルがあればネットワーク取得は行わない（`terminal/strata_control/drafting.py:244-249`、`terminal/strata_control/drafting_fetch.py:388-415`）。画像 reader fetch も `endpoint` 引数があれば優先し、なければ環境変数を読む（`terminal/strata_control/pictures.py:72-75, 433-460`）。
- アプリの画像モデルでは URL を library 情報に含める。実 download は `real` モードの場合だけで、選択 variant が未導入で、install が実行されたときにその URL を使用する。simulated モードでは download の代わりに進捗を模擬する（`app/host/server/image-models.mjs:12, 35-46, 64-90`）。
- `quantscope.py` と `qwen4_intake.py` の HF 経路を実行すること。`quantscope` の `ms:` URL やローカルファイル、`qwen4_intake` のローカル入力など、Hugging Face 以外の入力にはこの値は関与しない（`terminal/tools/quantscope.py:34-44, 78-90`、`terminal/tools/qwen4_intake.py:663-681, 1018-1022`）。
- transfer helper の環境変数読み取りは、URL host が Hugging Face と標準判定されない場合に限り `HF_ENDPOINT` host を認証対象に追加する。token が空なら Authorization header は作られない。redirect が別 host に移ると header が削除される（`terminal/strata_control/transfer.py:220-251, 254-264`）。

## 実行時の詳細

- setup の `hf()` は `hf_endpoint()` を使って URL を生成し、family 定義 (`MODELS` 等) に保存する。通常 GGUF shard の `model_hf()` / `download()` はこの保存済み URL を使うため、endpoint は setup モジュールの初期化時に決まり、同一プロセス中に環境値を変えても反映されない（`terminal/setup.py:129-137, 726-793, 2451-2456, 12414`）。一方、ready pack (`ready_fetch()`)、画像ファイルなど `hf_endpoint()` を直接呼ぶ経路は呼び出し時に読む（`terminal/setup.py:3927-3948, 6004-6008`）。`model_source()` は `STRATA_SOURCE`、生の `HF_ENDPOINT`、ModelScope endpoint を key とする辞書に取得元を cache するが、結果は `STRATA_SOURCE` だけで決まり、HF_ENDPOINT が選択する host は別に URL へ反映される（`terminal/setup.py:178-220`）。
- setup の CLI `--source` は `STRATA_SOURCE` に代入され、取得元選択に使われる。`HF_ENDPOINT` を上書きする CLI 引数はこの処理にない（`terminal/setup.py:11536-11539, 11622-11623`）。
- `mtp_fetch.py` は import 時に endpoint、`REPO`、`PINNED` を一度構築するため、同一プロセス内で後から環境変数を変更しても URL には反映されない（`terminal/tools/mtp_fetch.py:46-57`）。一方、`quantscope.py` も import 時に `HUBS` を変更するため同様。`qwen4_intake.py` は `hf_list()` / `read_hf_entry()` の呼び出しごとに読み、画像モデル host は `library()` 呼び出しごと、transfer helper は認証 header を作るたびに読み取る（各箇所は「根拠」参照）。
- `setup.run()` は子プロセス環境を元の環境から複製する。`fetch_mtp()` は `STRATA_SOURCE` だけを追加設定し、`HF_ENDPOINT` を変更しない（`terminal/setup.py:1138-1152, 1160-1164`）。`tools/feed_model_install_gate.py` の隔離実行環境は `HF_` で始まる変数を親環境から除外し、ローカル fixture server の `HF_ENDPOINT` を設定する（`terminal/tools/feed_model_install_gate.py:234-243`）。
- `HF_ENDPOINT` の不正値に対する Strata 共通の fallback や専用エラーはない。生成された URL の接続・HTTP エラーは各 download 呼び出し元の通常の失敗経路に進む。setup の download は失敗を表示して install を止める。MTP fetch は通信失敗を retry し、最後に失敗を標準エラーへ出す。DFlash2 fetch は `DraftingError` に変換し、画像モデル download は `error` state に例外文を入れる（`terminal/setup.py:3557-3570, 1153-1156`、`terminal/tools/mtp_fetch.py:177-186`、`terminal/strata_control/drafting_fetch.py:405-413`、`app/host/server/image-models.mjs:90-118`）。

## ログと測定値

非既定 host で通常の GGUF shards を取得するときは `  Downloading from {host} (HF_ENDPOINT)` を表示する。`ready` pack の取得元が ModelScope になっていた場合は、HF 専用 pack を `hf_endpoint()` から取る旨を warning に出す。setup の他のファイル取得や各同梱ツールに endpoint 専用の成功ログは見当たらない（`terminal/setup.py:12382-12399`）。測定値の記載はない。

## 根拠

- `terminal/setup.py:129-137, 178-220, 3546-3570, 3927-3948, 11536-11539, 1160-1164, 12380-12419`
- `terminal/strata_control/transfer.py:220-264, 298-316, 405-420`
- `terminal/strata_control/drafting.py:241-249`、`terminal/strata_control/drafting_fetch.py:388-415`
- `terminal/strata_control/pictures.py:72-75, 433-460`
- `terminal/tools/mtp_fetch.py:43-57, 177-186`、`terminal/tools/quantscope.py:34-44, 78-90`
- `terminal/tools/qwen4_intake.py:663-681, 1018-1022`
- `app/host/server/image-models.mjs:12-46, 64-118`
- `terminal/tools/feed_model_install_gate.py:234-243`
