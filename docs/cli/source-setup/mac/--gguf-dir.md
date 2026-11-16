# `setup.py`（Mac）`--gguf-dir`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Apple Silicon の通常 CLI では `metal/setup_mac.py` に委譲） |
| オプション | `--gguf-dir` |
| 別名 | なし |
| 値 | GGUF shard を置くディレクトリのパス（文字列） |

## 役割

Mac のモデル導入で、Strata が選んだモデルの GGUF shard を標準の保存先ではなく指定ディレクトリから使うための指定です。Mac 用実装はモデルに対応する既定の shard 名をこのディレクトリに組み立て、ファイルを検査してから Metal 用の準備を続けます。指定ディレクトリは GGUF の読み取り元であり、準備 pack や起動設定までそこへまとめて書く指定ではありません（`metal/setup_mac.py:498-526,592-611`）。

## 使い方

```sh
# 既存の GGUF を使ってモデルを準備し、起動はしない
./setup.sh --setup --family qwen --model IQ3_S --gguf-dir /Volumes/Models/IQ3_S --yes --no-start
```

ディレクトリ内には、選んだモデルに対応する名前の shard を置きます。Mac 実装は shard 名をモデルから決めるため、任意名の shard をこの指定だけで自動認識するわけではありません（`metal/setup_mac.py:66-75,498-505`）。

## 値と既定値

`--gguf-dir` は値を一つ取ります。Mac parser では型・存在確認・候補制約を付けず、未指定時は `None` です（`metal/setup_mac.py:389-402`）。利用時には `Path(a.gguf_dir)` として使われます。`~` をホームディレクトリへ展開する処理はこの経路では確認できないため、例のように絶対パスを指定してください（`metal/setup_mac.py:498-500`）。

## 実行時の動作

- Apple Silicon の通常 CLI は `setup.py` の parser より先に Mac 用スクリプトへ引数を渡します。実際にこの option を解析するのは `metal/setup_mac.py` の parser です（`setup.py:8308-8313,9330-9331`; `metal/setup_mac.py:371-402`）。
- モデルに対応する shard 名を指定ディレクトリに結合します。ディレクトリがなければ `mkdir(parents=True, exist_ok=True)` で作成します。各 shard について既に完了マークがあれば再利用し、そうでなければ `S.download` を呼びます。そのため、指定先に必要な全ファイルがない場合、残りを取得しようとします（`metal/setup_mac.py:498-506`）。
- shard は GGUF として読み取れること、およびテンソルデータを含む全長であることを検査します。不足・不正な shard はファイル名や不足量を示して停止します（`setup.py:3751-3778`）。対象モデルにピン留め SHA-256 がある場合は続けて照合します。Mac の処理では Unsloth または feed family の分岐から `own=bool(a.gguf_dir)` を渡し、別の `shard_sha` 分岐では `own` を渡しません（`metal/setup_mac.py:507-511`; `setup.py:3476-3529`）。
- `--update` と併用した場合は、このパスの shard と準備済み pack の完了状態を確認するだけです。モデルファイルをダウンロードせず、必要なものがなければ警告して戻ります（`metal/setup_mac.py:481-494`）。
- 通常の準備経路では shard を使ってモデル準備を行い、最後に Strata checkout 内へ起動設定 JSON と起動スクリプトを書きます。`--no-start` がなければその後モデルを起動します（`metal/setup_mac.py:524-535,592-620`）。

## 適用条件と副作用

- 対象は `setup.py` から Mac 用 Metal セットアップに委譲される経路です。指定ディレクトリそのものの存在・書き込み可否を事前検証する parser はなく、ディレクトリ作成、ファイル取得、後続の GGUF 検査で成否が決まります（`setup.py:9330-9331`; `metal/setup_mac.py:389-402,498-506`）。
- 不足 shard があれば、指定ディレクトリへダウンロードが行われます。ダウンロード処理は `.part` を使い、完了時に宛先へ置き、`.done` マークも記録します（`setup.py:3188-3203,3276-3306`）。
- `--update` では不足ファイルを取得しません（`metal/setup_mac.py:481-494`）。
- 選んだモデルの family と明示した `--family` が異なると警告し、モデル側の family を使います（`metal/setup_mac.py:461-465`）。
- Mac parser は未知の引数を `parse_known_args` で分離して警告します。これは `--gguf-dir` 自体の値検証ではなく、値に空白がある場合などはシェルで適切に引用してください（`metal/setup_mac.py:402-405`）。

## 出力とエラー

共通の `fail()` は `[X]` と理由・任意のヒントを表示し、「Setup stopped」と案内して終了コード 1 で停止します。GGUF shard の欠落、読み取り不能、短いファイル、規定を超える余分なデータが主な検査エラーです（`setup.py:823-828,3751-3778`）。Mac の `--update` では shard または pack が未完了の場合に警告し、通常のセットアップ方法を表示して終了コード 0 で戻ります（`metal/setup_mac.py:485-494`）。

## 根拠

- `metal/setup_mac.py:371-405` — Mac 側 parser、値の扱い、未知引数の警告。
- `setup.py:8308-8313,9330-9331` — Apple Silicon 通常 CLI の委譲経路。
- `metal/setup_mac.py:66-75,461-512` — モデルと shard 名の対応、指定先の選択、取得・検査・SHA-256 照合。
- `setup.py:3188-3203,3276-3306,3476-3529,3751-3778` — ダウンロード、完了マーク、ハッシュ検査、GGUF shard 検査と失敗。
- `metal/setup_mac.py:481-494,524-535,592-620` — 更新時の扱い、準備処理、起動設定の書き込みと起動。
