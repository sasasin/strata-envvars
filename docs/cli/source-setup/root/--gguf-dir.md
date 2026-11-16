# `setup.py --gguf-dir`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などからも呼び出される） |
| オプション | `--gguf-dir` |
| 別名 | なし |
| 値 | GGUF ファイルを置いたフォルダーのパス。parser 上の型・選択肢・既定値指定はなく、省略時は `None`。 |

## 役割

選択した family と model の GGUF を指定フォルダーから探し、モデル取得を省いて Strata のセットアップに使います。shard 名と数を読み取り、ファイルの存在と GGUF 構造を確認してから、モデルの準備と設定へ進みます。通常の対応 family では Vision reader も指定フォルダー近傍から探します。`--prepare-pack` と組み合わせる場合は、既存 GGUF から pack だけを作る経路になります（`setup.py:9421-9422, 9436-9438, 9510-9511`）。

## 使い方

```sh
# 既存の Qwen GGUF を使ってセットアップし、モデルの起動は行わない
./setup.sh --family qwen --model Q2_0 --gguf-dir /srv/models/qwen --no-start
```

`setup.sh` は引数を `setup.py` に渡し（`setup.sh:6, 76`）、Windows の `START-HERE.bat` も `setup.py` に渡します（`START-HERE.bat:8, 48, 53`）。この例はインストール処理を行いますが、モデル GGUF 自体のダウンロードは省きます。`--no-start` はセットアップ後に起動せず正常終了する分岐です（`setup.py:9423-9425, 10408-10415`）。

## 値と既定値

- parser は値をそのまま `gguf_dir` に格納し、存在確認や directory 型検査を登録時には行いません（`setup.py:9421-9422, 9499`）。空文字列は truthy 判定に使われるため、実質的に未指定と同じ経路になります（`setup.py:9500-9501, 10161-10164`）。
- 通常の family では、指定値を探索フォルダーとして使います。まず選択モデルの公称名の先頭 shard を探し、なければ `-00001-of-0000N.gguf` 形式の候補からモデル名・量子化名を使って候補を絞ります。見つけた shard 名から総数を読み、同じ stem の全 shard を構成します（`setup.py:3341-3364`）。
- 公称名でない shard 名も、先頭 shard が一意に選べれば利用候補になります。見つからない shard は後段のチェックでエラーになります（`setup.py:3344-3364, 3751-3765`）。
- Qwen3.6 の own-path family では探索 helper を使わず、指定フォルダーに family が定めるモデルファイル名があるものとして扱います。未指定なら `--models-dir/<family tag><model>` を使います（`setup.py:8713-8717, 8785-8787`）。
- Qwen3.6 own-path ではファイルがなければ `--gguf-dir` を外すよう案内して停止し、存在すれば pin の SHA-256 を確認します（`setup.py:8820-8828`）。

## 実行時の動作

parser 通過後、指定フォルダーを「利用者自身のファイルの場所」として登録します。通常のモデル経路では `gguf_dir_shards()` で GGUF 群を確定し、対象ファイルの問題を検出した後、`check_shards()` で各 shard が存在し、ヘッダーと tensor 配置から見て途中で切れていないことを確認します（`setup.py:9500-9501, 10161-10176, 3751-3778`）。選んだモデルに対するファイルがない場合、フォルダー内の他の GGUF から使用可能な family/model を示すことがあります（`setup.py:3396-3422`）。

このオプションが有効な通常経路ではモデル shard のダウンロード処理に入りません（`setup.py:10234-10268`）。SHA-256 pin があるファイルは照合しますが、指定フォルダーのファイルは Strata がダウンロードしたファイルのように削除・修復しません。pin と異なっても完全な GGUF と判定されれば警告してそのまま使い、不完全またはサイズ不一致のファイルは残したまま停止します（`setup.py:3476-3529`）。また、自分のファイルの完了 mark は隣に書かず Strata 側の `marks/` に保存します（`setup.py:1014-1032, 1051-1071`）。

他の引数・モードとの関係:

- `--family` と `--model` が、指定フォルダーから選ぶファイルを決めます。
- `--prepare-pack PACK_DIR` と併用すると、GGUF フォルダーから pack の作成だけを行います。このモードでは `--gguf-dir` と `--model` が必須で、モデルファイルをダウンロード・変更しないと記載されています（`setup.py:8994-9018, 9436-9438`）。
- `--backend sycl` の Control/アプリ経路は、指定したフォルダーまたは標準の models フォルダーからファイルを探します（`setup.py:8342-8369, 9516-9519`）。通常 checkout の SYCL 経路は別スクリプトへ委譲されるため、その委譲先での詳細な受理・効果はこの調査では追っていません（`setup.py:8316-8339`）。
- ready-made pack family ではこのオプションは適用されず、警告を出して値をクリアし、ready-made ファイル取得へ進みます（`setup.py:9893-9899, 10234-10240`）。

## 適用条件と副作用

- `setup.py` の最初の処理では、macOS は `metal/setup_mac.py` へ引数ごと委譲します。その parser にも同名オプションがありますが、索引の `source-setup/mac/` スコープです。この文書は `source-setup/root/` の parser と動作を対象にしています（`setup.py:8308-8314, 9330-9331`; `metal/setup_mac.py:371-390`）。
- 通常のモデルセットアップは GGUF をコピーせず指定場所から読みますが、Python package、エンジン、pack、設定など他のセットアップ処理は通常どおり進み得ます。`--no-start` を付けてもセットアップ自体は行われます（`setup.py:8713-8717, 10207-10214, 10234-10274`）。
- `--gguf-dir` を指定したとき、Strata は指定ファイルの隣に完了 mark を書かず、自身の `marks/` を使います。read-only な場所でも mark を Strata 側へ置けます（`setup.py:1017-1032, 1051-1071`）。

## 出力とエラー

- 欠けた shard、壊れた GGUF header、tensor の必要サイズより短い shard は `fail()` 経由で理由を表示して停止し、終了コード 1 になります。ファイル削除を案内する場合も、`--gguf-dir` の利用者ファイルは自動削除されません（`setup.py:823-828, 3751-3778`）。
- SHA-256 pin 対象で hash が違っても、完全な GGUF なら警告を出して利用します。不完全な場合は hash mismatch を報告し、ファイルを残して停止します（`setup.py:3486-3529`）。
- directory の不在・誤指定に対する専用の parser validation はありません。該当モデルの shard が見つからない場合は欠落エラー経路へ進みます（`setup.py:9421-9422, 3344-3364, 3758-3765`）。

## 根拠

- `setup.py:9421-9422` — root parser の `--gguf-dir` 定義と help。
- `setup.py:3341-3364` — shard 名の形式、候補選択、shard 数の決定。
- `setup.py:9500-9501, 10161-10176` — 利用者ファイル登録と通常経路での指定値使用。
- `setup.py:3751-3778, 3476-3529` — shard 構造検査、pin 照合、失敗時の扱い。
- `setup.py:1014-1071` — 完了 mark の保存先と read-only 時の fallback。
- `setup.py:8994-9018, 9893-9899` — `--prepare-pack` 経路と ready-made pack family での非適用。
- `setup.py:8308-8314, 9330-9331`; `metal/setup_mac.py:371-390` — macOS の別 parser への委譲と同名オプション。
