# `setup.py --source`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からの委譲を含む） |
| オプション | `--source` |
| 別名 | なし |
| 値 | `auto`、`huggingface`、`modelscope` のいずれか |

## 役割

モデルファイルを取得する配信元を選びます。`modelscope` を指定すると、対応する Hugging Face リポジトリのファイルを ModelScope から取得します。ModelScope が応答しない場合は警告を出して Hugging Face に戻ります。`auto` は自動的な到達性判定をせず Hugging Face を選ぶ値です（`terminal/setup.py:169-176`, `terminal/setup.py:212-220`, `terminal/setup.py:3546-3552`）。

## 使い方

```sh
# ModelScope から指定モデルをインストールし、モデルは起動しない
./setup.sh --source modelscope --family qwen --model IQ3_XXS --yes --no-start

# Hugging Face を明示する
./setup.sh --source huggingface --family qwen --model IQ3_XXS --yes --no-start
```

Windows では同じ引数を `START-HERE.bat` に渡せます。ラッパーは引数を `setup.py` にそのまま渡します（`setup.sh:6-17`, `setup.sh:81`, `START-HERE.bat:8-13`, `START-HERE.bat:49-64`）。

## 値と既定値

`terminal/setup.py` の parser は `choices=("auto", "modelscope", "huggingface")`、既定値 `None` で定義されています（`terminal/setup.py:11536-11539`）。それ以外の値は argparse が拒否します。標準の argparse の構文エラー経路となり、setup の処理には入りません（parser 定義 `terminal/setup.py:11444`, `terminal/setup.py:11606`）。

`--source` を省略すると、継承した `STRATA_SOURCE` は変更されません。環境変数も未設定または空なら内部値 `auto` が使われます。選択処理は値を空白除去・小文字化したうえで、`ms` または `modelscope` のときだけ ModelScope、それ以外は Hugging Face と解釈します。したがって `STRATA_SOURCE` に設定できる値の扱いは CLI の `choices` より広く、環境変数の未知値も Hugging Face になります（`terminal/setup.py:212-220`）。明示した `--source` は parse 後に `STRATA_SOURCE` へ設定されるため、継承値を上書きします（`terminal/setup.py:11606-11623`）。

## 実行時の動作

- `auto` と `huggingface` は Hugging Face を使います。`HF_ENDPOINT` があればそのホスト（ミラーを含む）を使い、なければ `https://huggingface.co` が使われます（`terminal/setup.py:126-137`）。
- `modelscope` は、ダウンロード URL が Strata が把握する Hugging Face リポジトリのファイル URL に一致するとき、`MODELSCOPE_ENDPOINT`（未設定なら `https://www.modelscope.cn`）の同名リポジトリにある `master` のファイルへ切り替えます（`terminal/setup.py:182-184`, `terminal/setup.py:244-253`, `terminal/setup.py:3546-3550`）。この経路は pinned revision を取得するものではありません（`terminal/setup.py:169-174`）。
- ダウンロード後は、Strata が固定ハッシュを持つファイルならそのハッシュで照合します。固定値がなく、ModelScope が SHA-256 を公開していれば公開値で照合します。ModelScope から取得したファイルに公開ハッシュもなければ警告を出し、ハッシュ検証なしで完了印を付けます（`terminal/setup.py:3555-3556`, `terminal/setup.py:3621-3630`）。
- setup が MTP fetcher を起動するときも、選択結果を子プロセスの `STRATA_SOURCE` に渡します（`terminal/setup.py:1160-1164`）。fetcher は ModelScope の `master` を使いますが、tensor は pinned revision の SHA-256 で検査します（`terminal/tools/mtp_fetch.py:48-58`）。

## 適用条件と副作用

この選択はモデル取得経路に適用されます。URL が Strata の既知リポジトリに対応しない場合は ModelScope URL に変換されず、元の URL の取得処理が続きます（`terminal/setup.py:244-249`, `terminal/setup.py:3546-3553`）。既に完了印のあるファイルは取得を省略するため、再取得が発生しない場合があります（`terminal/setup.py:3513-3519`）。

ModelScope 側の対応 URL が応答しない場合は警告を出して Hugging Face にフォールバックします。`model_source()` 自体はネットワーク到達性を確認せず、`auto` でも自動切替しません（`terminal/setup.py:186-220`, `terminal/setup.py:3546-3552`）。対応ファイルの取得ではネットワークアクセスとモデル保存先へのファイル作成・更新が発生します（`terminal/setup.py:3513-3516`, `terminal/setup.py:3610-3631`）。

ready-made pack の取得経路では、ModelScope はその pack の配信元として使われず、Hugging Face のみと案内されます（`terminal/setup.py:12380-12386`）。また、`--inspect` や `--prepare-pack` は通常のモデルインストール処理より先に別経路へ分岐します（`terminal/setup.py:11622-11627`）。それらのサブ処理がこの値をどこまで利用するかは、本調査では追跡していません。

## 出力とエラー

ModelScope が応答しないと、`[!]` 形式の警告として Hugging Face へ切り替える旨を出力します（`terminal/setup.py:1044-1046`, `terminal/setup.py:3550-3552`）。Hugging Face への取得も失敗すると、接続エラーと再実行の案内を表示し、Hugging Face のURLと判定された場合は ModelScope を明示指定する方法も案内します（`terminal/setup.py:223-228`, `terminal/setup.py:3573-3581`）。setup の `fail()` は `[X]` のエラーと案内を標準出力に出し、終了コード `1` で終了します（`terminal/setup.py:1049-1056`）。MTP fetcher が終了コード `4` を返した場合は setup も終了コード `1` で停止し、その他の失敗は進捗があった場合に限り最大3回まで再試行します（`terminal/setup.py:1160-1188`）。

## 根拠

- `terminal/setup.py:11536-11539` — parser の choices、既定値、環境変数との連携を示すヘルプ。
- `terminal/setup.py:11606-11623` — parse 後の `--source` から `STRATA_SOURCE` への反映。
- `terminal/setup.py:212-220` — 環境変数の正規化と `auto` を Hugging Face として扱う選択処理。
- `terminal/setup.py:244-267`, `terminal/setup.py:3513-3566`, `terminal/setup.py:3621-3630` — URL 対応判定、ModelScope への切替、ハッシュ照合と未検証時の警告。
- `terminal/setup.py:1160-1189`, `terminal/tools/mtp_fetch.py:48-58` — MTP 子プロセスへの選択の引き継ぎと tensor の取得元・照合。
- `terminal/setup.py:12380-12386` — ready-made pack 経路における ModelScope の制限。
- `setup.sh:6-17`, `setup.sh:81`, `START-HERE.bat:8-13`, `START-HERE.bat:49-64` — ラッパーが引数を setup に渡す実装。
