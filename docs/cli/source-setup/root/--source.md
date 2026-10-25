# `--source`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` からも利用） |
| オプション | `--source` |
| 別名 | なし |
| 値 | `auto`、`huggingface`、`modelscope` のいずれか（必須） |

## 役割

モデル関連ファイルの取得元を選びます。`auto` はこの実装では Hugging Face を意味し、接続状況を見て ModelScope に自動で切り替える設定ではありません。ModelScope を使うには明示的に `modelscope` を選びます。

## 使い方

```sh
# Linux: setup.py に委譲する標準 wrapper を使って ModelScope を選ぶ
./setup.sh --source modelscope --setup

# Windows: モデル取得元を明示して setup
START-HERE.bat --source huggingface --setup
```

`update.sh` / `UPDATE.bat` も引数を `setup.py` へ渡します。更新処理の例は `./update.sh --source modelscope` です。ラッパーの引数転送は Strata の `setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` で確認できます（根拠節に行番号を記載）。

## 値と既定値

- `setup.py` の `argparse` 定義は `choices=("auto", "modelscope", "huggingface")`、`default=None` です。CLI で省略した場合は既存の `STRATA_SOURCE` が保持され、環境変数も未設定なら `auto` 相当、すなわち Hugging Face になります（`setup.py:151-154,174-182,8502-8505,8553-8558`）。
- CLI で `auto` を明示すると `STRATA_SOURCE=auto` を設定し、既存環境変数の値を上書きします。`huggingface` も同様に Hugging Face を選びます。`modelscope` は ModelScope を選びます（`setup.py:8557-8558,174-182`）。
- `--source` に値がない場合、または上記以外の値を指定した場合、`argparse` が引数エラーとして拒否します。parser は選択値をそのまま環境変数へ設定します（`setup.py:8502-8505,8553,8557-8558`）。
- `STRATA_SOURCE` の環境変数値は前後空白を除いて小文字化され、`ms` と `modelscope` だけが ModelScope として扱われます。それ以外（空値を含む）は Hugging Face です（`setup.py:174-182`）。

## 実行時の動作

`--source modelscope` を選ぶと、セットアップは取得元選択を子プロセスの `tools/mtp_fetch.py` にも `STRATA_SOURCE` として渡します（`setup.py:902-908`）。通常モデルのダウンロードでは、既知の Hugging Face リポジトリに対応するファイルだけを ModelScope の同名リポジトリ URL に置き換えます。置換先 URL は既定で `https://www.modelscope.cn` ですが、`MODELSCOPE_ENDPOINT` で変更できます。ModelScope 用の URL が応答しない場合は警告を出して Hugging Face に戻ります（`setup.py:160-162,193-202,2781-2803`）。

ModelScope は固定 revision ではなくリポジトリの現行ファイルを提供します。通常の取得経路では ModelScope API からサイズ・SHA-256 を取得できれば照合し、公開 SHA-256 がなければ未検証である旨を警告します。ModelScope から取得したモデルファイルも同じダウンロード処理を通ります（`setup.py:147-152,205-216,2836-2871,9298-9302`）。MTP tensor は ModelScope の現行ファイルを取得先に使いますが、固定 checkpoint の SHA-256 と照合します（`tools/mtp_fetch.py:40-51,55-57,393-429`）。

すでに完了印付きで存在するモデルファイルは再取得しません。また、`--gguf-dir` でローカル GGUF を指定するなど、取得自体を行わない経路では取得元の選択は実質的に使われません（`setup.py:2781-2788,9292-9307`）。単純な既存モデル起動もファイルを取得しない経路です（`setup.py:8602-8609`）。

## 適用条件と副作用

- ModelScope は、通常のモデル取得で `ms_file()` が認識する `HF_REVISIONS` 登録リポジトリのファイルに適用されます。ここに含まれない URL は ModelScope 用 URL に置換されず、元の URL のままです（`setup.py:94-103,193-202,2797-2803`）。
- ready-made pack のファイル取得は `ready_fetch()` が Hugging Face endpoint と pin 済み revision を直接使うため、`--source modelscope` を選んでも Hugging Face から取得されます。該当時はその旨を警告します（`setup.py:3071-3092,9287-9291`）。
- `--source` はセットアップのモデルファイル取得先に関する指定です。エンジンの配布元 `--prebuilt` や `HF_ENDPOINT` は別設定です。Hugging Face を選んだ際の endpoint は `HF_ENDPOINT`、ModelScope の endpoint は `MODELSCOPE_ENDPOINT` から取得します（`setup.py:109-117,160-162,223-234,8502-8505`）。
- `setup.py` は macOS の Control 以外の経路では parser を作る前に `mac_setup(sys.argv[1:])` に委譲します。この経路における `--source` の受理可否・効果は本調査では確認していません（`setup.py:8412-8420`）。Intel SYCL 経路は parser 後に元の引数を別 setup へ転送し、`--source` による環境変数設定後に分岐します（`setup.py:8553-8564`）。

## 出力とエラー

- 不正な値や値の欠落は `argparse` の引数エラーになります。独自の追加 validation や `--source` 専用の終了処理はありません（`setup.py:8420,8502-8505,8553-8558`）。
- ModelScope のファイル URL が応答しない場合は、Hugging Face endpoint から取得する旨の警告を出して続行します（`setup.py:2797-2803`）。ModelScope API から SHA-256 を得られない場合も処理は続き、取得ファイルを未検証とする警告が出ます（`setup.py:2841-2843,2863-2871`）。
- 取得先への接続が繰り返し失敗した場合や、サイズ・SHA-256 が期待値と一致しない場合はダウンロード処理が失敗します。HF 側の接続失敗時には明示的に `--source modelscope` を試す案内があります（`setup.py:2813-2832,2836-2838,2863-2871`）。

## 根拠

- `setup.py:147-182` — `SOURCES`、`model_source()` の既定・環境変数解釈、および自動切り替えをしない設計。
- `setup.py:193-216,2781-2803,2836-2871` — ModelScope URL の対応付け、接続確認、サイズ・hash 検証と失敗経路。
- `setup.py:8420-8420,8502-8505,8553-8558` — parser 定義、選択値の検証、環境変数への反映。
- `setup.py:3071-3092,9285-9307` — ready-made pack が Hugging Face 固定であること、通常モデル取得での選択表示。
- `setup.py:902-918`、`tools/mtp_fetch.py:40-57,393-429` — MTP 取得への伝播と固定 tensor hash 検証。
- `setup.sh:6-13,76`、`START-HERE.bat:8-11,44-54`、`SETUP.bat:1-3`、`update.sh:62`、`UPDATE.bat:1-6` — wrapper の引数委譲。
- 利用者向け資料 [`docs/INSTALL.md`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/INSTALL.md#L414-L421) — ModelScope が明示選択制であることと hash 検証の説明。上記の動作記述は commit のソースを根拠としています。

調査範囲は指定 commit の checkout に含まれるソースと同 commit の `docs/INSTALL.md` です。CLI `--help` は実行せず、parser 定義と wrapper の転送を直接確認しました。Release 配布物や全 OS の実行結果は確認していません。
