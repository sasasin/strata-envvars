# `setup.py` `--gguf-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（root。`setup.sh` / `START-HERE.bat` 等からの実行を含む） |
| オプション | `--gguf-dir` |
| 別名 | なし |
| 値 | 1 個のパス文字列。通常の GGUF モデルでは、対象モデルの全 shard が入ったフォルダー |

## 役割

手元にある GGUF を使う場所として指定し、通常の対応モデルでは Strata のモデル保管先からモデル本体を取得する代わりに、そのフォルダー内のファイルを選びます。モデル・family を省略した場合、フォルダー内の認識可能な GGUF 名から候補が一つに定まれば自動選択します。モデル本体をダウンロードしなくても、実行経路によって engine、準備用 pack、画像 encoder、その他の補助ファイルは別に取得・生成されることがあります（`terminal/setup.py:11762-11766,12084-12103,12159-12212`）。

## 使い方

```sh
# 手元の GGUF shard 一式を使ってセットアップし、モデルを起動しない
./setup.sh --family qwen --model Q2_0 --gguf-dir /mnt/models/Q2_0 --yes --no-start

# Intel Arc 用: ローカル GGUF から pack のみを作る
python3 terminal/setup.py --prepare-pack /data/packs/q2_0 --family qwen --model Q2_0 --gguf-dir /mnt/models/Q2_0
```

## 値と既定値

値は必須の文字列で、未指定時は `None` です。parser は `type`、`choices`、独自の存在確認を指定していないため、引数としては任意の文字列を受理し、値の欠落は `argparse` のエラーになります（`terminal/setup.py:11304-11305,11385`）。実際のパス確認はモデルごとの処理で行われます。絶対パスを指定してください。`own_files_in()` は登録時に `expanduser()` しますが、モデル選択側は多くの経路で値を直接 `Path(...)` に渡しており、`~` が実際の入力パスとして展開される保証は確認できません（`terminal/setup.py:1261-1268,12084-12089`）。

## 実行時の動作

通常の GGUF shard 経路では、指定値をモデルフォルダーとして使い、モデル名に合う先頭 shard を探して shard 数をファイル名から組み立てます。指定なしの場合に使う `<models-dir>/<model tag>` とは別の入力先です（`terminal/setup.py:3627-3647,12084-12089`）。`--family` と `--model` の両方が未指定、または一方が未指定でも、フォルダー内の認識可能なモデル候補が一つならその選択を補います。候補が一つに絞れない場合は通常の選択処理へ進みます（`terminal/setup.py:3679-3689,11762-11766`）。

指定フォルダーでは GGUF ヘッダーとテンソル範囲を確認し、欠落・不完全な shard は失敗になります（`terminal/setup.py:4171-4198,12087-12089,12194-12198`）。対応 family に pinned SHA-256 がある場合も `own=True` で照合します。正規サイズと異なっても完全な GGUF と判定できるローカルファイルは警告して使用し、完全性を確認できないサイズ違いは失敗します（`terminal/setup.py:3772-3793`）。利用者所有ファイルの `.done` 印は隣に作らず Strata の `marks/` 側へ記録します（`terminal/setup.py:1261-1317,11393-11394`）。

GGUF 本体のダウンロードはスキップされますが、通常経路では engine の準備、pack 作成、MTP、画像 encoder 等は別工程です。画像を使う場合、encoder は指定フォルダーまたは周辺の既存候補を探し、見つからなければ取得することがあります（`terminal/setup.py:12103-12121,12132-12157,12217-12229,12203-12212`）。

## 適用条件と副作用

- `--prepare-pack` と併用すると、`--gguf-dir` は必須です。指定フォルダーの GGUF から pack を生成し、engine やモデル本体のダウンロードを行わない専用経路です（`terminal/setup.py:11403-11404,10820-10849`）。
- Hy4-Flash は指定フォルダーをモデル・Engram ファイルの場所として使います。指定ありで必要ファイルが欠けている場合は、そのファイルを置くよう案内して失敗し、通常のダウンロードへフォールバックしません（`terminal/setup.py:9958-9962,10226-10232,10027-10058`）。
- Inkling-2-Mini はフォルダーに加えて単一 `.gguf` または `.strata` ファイルも解決対象にします。ファイル指定なら親フォルダーを関連ファイル探索先にします（`terminal/setup.py:10320-10360`）。
- Intel Arc の SYCL 経路では、値がファイルなら親フォルダーに直し、その中からモデルファイルを探します。見つからないと「ダウンロードなし」のエラーで止まります（`terminal/setup.py:9280-9309`）。
- GGUF shard を使わない ready-made pack family ではこの指定は適用されず、警告を出して値をクリアし、ready-made pack 用の処理へ進みます（`terminal/setup.py:11808-11814,12074-12086`）。
- 通常の shard 経路では、指定フォルダーの不足 shard を自動取得しません（`terminal/setup.py:12159-12198`）。ただし engine、pack、画像 encoder 等の別工程にはダウンロードやファイル生成があります。Intel Arc では pack の出力先、通常経路では run 設定や start script も別途作成されます（`terminal/setup.py:9321-9335,12132-12157,12217-12229`）。
- root parser の macOS 分岐では、通常の family は `metal/setup_mac.py` に引数ごと委譲されます。Mac 専用 parser としての値の挙動は [`Mac 用 `--gguf-dir` 文書](../../mac/--gguf-dir.md)を参照してください。Hy4 / Inkling 等は root 側の専用経路があります（`terminal/setup.py:11216-11219,11407-11413`）。

## 出力とエラー

欠落・不正な GGUF、指定先に必要なファイルがない場合など、setup 内の `fail()` はメッセージと可能なら案内を表示し、終了コード 1 で終了します（`terminal/setup.py:1049-1056,4171-4198,10049-10061`）。`--output jsonl` 併用時はエラーイベントも出力されます。parser で必須値が欠けた場合は `argparse` の引数エラーです（`terminal/setup.py:11304-11305,11385-11387`）。

## 根拠

- `terminal/setup.py:11304-11305` — root parser の登録。値は1つのパス文字列で、説明上は全 shard 入りフォルダー。
- `terminal/setup.py:1261-1317,11393-11394` — 利用者所有ファイルの登録と finish mark の保存先。
- `terminal/setup.py:3627-3647,3679-3689,11762-11766` — shard 解決とフォルダー名からの family/model 推定。
- `terminal/setup.py:3772-3793,4171-4198,12084-12103,12159-12198` — shard 検査、ハッシュ確認、モデル本体の取得抑止。
- `terminal/setup.py:12132-12157,12203-12229` — engine、画像 encoder、pack など別工程。
- `terminal/setup.py:9958-9962,10027-10061,10226-10238` — Hy4-Flash での入力先・不足ファイル時の失敗。
- `terminal/setup.py:10320-10360` — Inkling-2-Mini で許されるファイル／フォルダー形式。
- `terminal/setup.py:9280-9309,9321-9335` — Intel Arc のローカル入力確認と pack/config 準備。
- `terminal/setup.py:11808-11814,12074-12086` — ready-made pack family では指定を使わない分岐。
- `terminal/setup.py:11216-11219,11407-11413` — macOS での root parser からの委譲。
