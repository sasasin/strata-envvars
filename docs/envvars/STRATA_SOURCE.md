# `STRATA_SOURCE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

セットアップ時に、モデル関連ファイルを Hugging Face から取得するか、明示的な指定がある場合に ModelScope から取得するかを選びます。セットアップはネットワーク状況を見て自動で ModelScope へ切り替えません。環境変数に未知の値があってもセットアップ自体は失敗せず、Hugging Face を選びます。

この選択は `setup.py` の `download()` によるダウンロードのうち、`HF_REVISIONS` に登録された Hugging Face のモデルファイル URL を ModelScope URL に対応づけられる場合に限って使われます。llama.cpp や engine 等、登録済みリポジトリのファイル URL でないダウンロードはこの選択で切り替わりません。既存 GGUF を指定する `--gguf-dir` や、既にダウンロード済みのファイルを再利用する場合も、モデルファイルの取得元選択は発生しません。

## 値と判定

| 指定 | `setup.py` の選択 |
|---|---|
| 未設定、または空文字 | `auto` として扱い、Hugging Face |
| `ms` / `modelscope` | ModelScope |
| `auto` / `huggingface` | Hugging Face |
| その他の文字列 | Hugging Face（エラーにはならない） |

環境変数の値は前後の空白を除去し、小文字化してから判定されます。したがって ` MODELSCOPE ` も ModelScope です。全体一致であり、`modelscope-extra` のような値は ModelScope になりません。`auto` は自動選択を意味せず、Hugging Face を選びます。

CLI の `--source` は `auto`、`modelscope`、`huggingface` のいずれかに制限されます。これを指定すると、引数解析後に `STRATA_SOURCE` をその値で上書きするため、CLI が環境変数に優先します。たとえば `STRATA_SOURCE=modelscope` でも `--source auto` を指定すれば Hugging Face です。

## 有効になる条件

ModelScope への切り替えには、次の条件があります。

- `model_source()` が `modelscope` を返すこと（値は `ms` または `modelscope`）。
- `download()` に渡された HTTP(S) URL が既知の Hugging Face ファイル URL で、対応するリポジトリが `HF_REVISIONS` に登録されていること。
- 対応する ModelScope URL への HEAD 要求が成功すること。失敗した場合は Hugging Face の URL で続行します。

ModelScope は固定 revision ではなくリポジトリの現在のファイルを配信します。取得後、セットアップは ModelScope API からファイルのサイズと SHA-256 を取得でき、SHA-256 がある場合はそれで検証します。メタデータを取得できない場合や SHA-256 がない場合は、検証しない旨を警告して完了マークを付けます。MTP tensor は別途、固定チェックポイント由来の SHA-256 で検査されます。これらのハッシュ値の意味や配信サービス内部の動作は Strata の環境変数処理の範囲外です。

`HF_ENDPOINT` は Hugging Face の取得先（ミラーを含む）を設定し、`MODELSCOPE_ENDPOINT` は ModelScope の取得先を設定します。`STRATA_SOURCE` が Hugging Face を選ぶ場合、ModelScope endpoint はモデル取得先の決定に使われません。

## 実行時の詳細

`setup.py` の `model_source()` は呼び出し時に `STRATA_SOURCE` を読み、結果を `(STRATA_SOURCE, HF_ENDPOINT, MODELSCOPE_ENDPOINT)` に基づくプロセス内辞書へ保存します。同じキーで再度呼ばれれば保存値を返します。環境変数が後から変更されても、キーが変われば別の選択として評価されます。セットアップの CLI 処理では `--source` があれば環境変数自体を上書きします。

既知の Hugging Face URL が ModelScope に対応する場合、セットアップは ModelScope の対応 URLに HEAD 要求を送り、成功すればそちらから取得します。取得後は公開メタデータに SHA-256 があれば照合し、なければ未検証の警告を出します。応答しなければ `ModelScope does not answer; downloading it from ...` の警告を出し、Hugging Face endpoint を使います。ダウンロード失敗時の `source_hint()` は、Hugging Face または `hf-mirror` の URL に対して ModelScope を明示指定する方法を案内します。

MTP取得では、セットアップが `tools/mtp_fetch.py` を起動する際に `model_source()` の戻り値（`modelscope` または `huggingface`）を子プロセスの `STRATA_SOURCE` として渡します。同ツールは起動時に値を読み、空白除去と小文字化後に `ms` / `modelscope` なら ModelScope endpoint を使います。それ以外は `HF_ENDPOINT`（空なら Hugging Face 既定 endpoint）を使います。直接 `mtp_fetch.py` を起動した場合も環境変数を読みますが、通常の `setup.py` が `ms` を `modelscope` に正規化して渡す点とは異なり、同ツール側でも `ms` を受け付けます。

## 根拠

- `setup.py:93-128`: ModelScope の位置づけ、許容ソース一覧、環境変数の正規化と選択結果のキャッシュ。
- `setup.py:139-148`: Hugging Face URL と既知リポジトリの対応付け、および ModelScope URL の構築。
- `setup.py:1449-1491,1531-1538`: ローカルコピーと HTTP(S) ダウンロードの分岐、ModelScope 到達確認、Hugging Face fallback、取得後の SHA-256 検証または未検証警告、失敗時の案内。
- `setup.py:4846-4849,4893-4896`: `--source` の選択肢と環境変数への上書き。
- `setup.py:5471-5498,5511`: モデル shard / vision encoder の取得と共通 `download()` 呼び出し。
- `setup.py:5477-5483,5547-5552`: 選択ソースの表示と MTP 子プロセスへの値の引き渡し。
- `tools/mtp_fetch.py:33-43`: MTP取得側の環境変数読み取り、既定値、ModelScope URL の切り替え。
- `docs/INSTALL.md:283-291`: ModelScope の明示指定、固定 revision ではないこと、ハッシュ確認についての説明。記載の測定値は同資料にある中国本土の PC・2026-10-05 の条件によるもので、本調査で再測定していません。
