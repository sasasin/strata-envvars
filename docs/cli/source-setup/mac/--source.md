# `setup.py`（mac）`--source`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` / `setup.sh`（`engine/metal/setup_mac.py`） |
| オプション | `--source` |
| 別名 | なし |
| 値 | `auto`、`huggingface`、`modelscope` のいずれか |

## 役割

モデルファイルの取得元を選びます。`auto` は Hugging Face を使う指定で、ModelScope へ自動的に切り替える指定ではありません。Mac 用 setup はこの値を `STRATA_SOURCE` に設定し、Terminal setup と共通の downloader にモデル取得元を選ばせます。

## 使い方

```sh
# 通常の取得元（Hugging Face）を選んでセットアップ
./setup.sh --source auto

# ModelScope を明示してセットアップ
./setup.sh --source modelscope --yes --no-start

# Hugging Face を明示してセットアップ
./setup.sh --source huggingface --setup
```

`setup.sh` は macOS では `terminal/setup.py` から `engine/metal/setup_mac.py` に引数ごと委譲されます（`terminal/setup.py:9206-9210`, `11198-11219`）。

## 値と既定値

- parser が受理する値は小文字の `auto`、`huggingface`、`modelscope` です。既定値は `None` で、未指定なら既存の `STRATA_SOURCE` を残します。指定した場合は、その値を環境変数へ設定します（`engine/metal/setup_mac.py:392-394`, `406-410`）。
- `auto` は `model_source()` 内で Hugging Face として解決されます。環境変数が未設定または空白の場合も `auto` 相当です。環境変数の値は前後空白を除去し小文字化して判定され、`ms` と `modelscope` だけが ModelScope、それ以外は Hugging Face になります（`terminal/setup.py:212-220`）。
- parser の `choices` にない値は受理されません。大文字表記や空値がどう解釈されるかを独自に補正する処理はなく、argparse の引数エラーになります（`engine/metal/setup_mac.py:392-394`）。

## 実行時の動作

Mac の parser は `--source` を認識し、明示値を `STRATA_SOURCE` に設定します。未指定の場合は環境変数に手を加えません（`engine/metal/setup_mac.py:392-394`, `406-410`）。モデル shard は `S.model_hf(...)` で組み立てた Hugging Face URL を共通 downloader `S.download(...)` に渡します（`engine/metal/setup_mac.py:497-513`）。

共通 downloader は `STRATA_SOURCE=modelscope` の場合に限り、対応する既知リポジトリの URL を ModelScope の `models/<repo>/resolve/master/<path>` に置き換えて取得を試みます（`terminal/setup.py:244-253`, `3471-3473`, `3504-3510`）。ModelScope が応答しない場合は警告を出し、Hugging Face の URL に戻します（`terminal/setup.py:3504-3510`）。それ以外の値、特に `auto` は Hugging Face を選びます（`terminal/setup.py:212-220`）。

共通 downloader は既知ファイルの固定サイズ・SHA-256 を優先して検証します。固定値がない場合は ModelScope の公開メタデータをサイズ・ハッシュの確認に使い、SHA-256 が得られない場合は未検証である旨を警告します（`terminal/setup.py:3513-3515`, `3542-3547`, `3556-3558`, `3579-3588`）。Mac setup が MTP draft layer を取得する子プロセスにも解決済みの取得元を渡します（`engine/metal/setup_mac.py:579-585`）。

## 適用条件と副作用

- 効果があるのは共通 downloader が処理する HTTP(S) モデルファイルのうち、ModelScope 用に対応付けられたリポジトリです。通常の Mac モデル shard はこの downloader に渡ります。既存モデルの単純な起動や `--check` のようにモデルを取得しない実行では、取得元による効果はありません。`--source` は取得先の選択に関わり、Metal engine の build 選択やモデルの配置先を変更しません（`engine/metal/setup_mac.py:416-430`, `497-513`; 共通 downloader の対象判定は `terminal/setup.py:244-249`, `3504-3510`）。
- ModelScope は `master` の現在のファイルを配信し、Hugging Face の固定 revision と同一ではありません。ソースコメントもこの差を明記しています（`terminal/setup.py:169-175`, `212-215`, `252-253`）。取得元切替時にはネットワークアクセスが発生します。
- ダウンロード途中の `.part` ファイルや完了マークを使って再開・スキップする処理は共通 downloader にあります（`terminal/setup.py:3471-3477`, `3511`, `3570-3588`）。
- 選択した ModelScope が応答しない場合は Hugging Face に fallback するため、`modelscope` の指定だけで Hugging Face を一切使わない動作にはなりません（`terminal/setup.py:3504-3510`）。

## 出力とエラー

- ModelScope が応答しない場合は、共通 downloader が「ModelScope does not answer」と Hugging Face から取得する旨を警告します（`terminal/setup.py:3504-3510`）。Mac setup からも同じ downloader を呼び出します（`engine/metal/setup_mac.py:502-506`）。
- 値が `choices` に合わない場合、argparse が usage とエラーを表示して引数解析を止めます（`engine/metal/setup_mac.py:375-405`, `392-403`）。エラー文の具体的な文面は Python argparse が生成します。
- 取得先への接続失敗、固定サイズ不一致、ダウンロード完了サイズ不一致、SHA-256 不一致などでは downloader の失敗処理に進みます（`terminal/setup.py:3521-3539`, `3545-3547`, `3570-3588`）。

## 根拠

- `engine/metal/setup_mac.py:392-410` — Mac parser の値、既定値、`STRATA_SOURCE` への反映。
- `terminal/setup.py:11198-11219`, `9206-9210` — macOS での入口と Mac setup への引数委譲。
- `terminal/setup.py:212-220`, `244-253` — `STRATA_SOURCE` の解決と ModelScope URL の対応付け。
- `engine/metal/setup_mac.py:497-513`, `579-585` — Mac のモデル shard と MTP 取得から共通 downloader / 子プロセスへの接続。
- `terminal/setup.py:3471-3515`, `3521-3588` — downloader の取得元選択、fallback、サイズ・ハッシュ検証、完了処理と失敗経路。
