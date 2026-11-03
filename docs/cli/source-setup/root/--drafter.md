# `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers `--drafter`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` から委譲） |
| オプション | `--drafter` |
| 別名 | なし |
| 値 | `mtp` または `dflash2`。値を1つ取る |

## 役割

モデルのセットアップ時に、MTP ドラフト層を今回ダウンロードするかどうかを制御します。`dflash2` を選ぶと、MTP 層がまだない場合にその約5 GBの取得・生成を省き、DFlash2 用語彙ファイルを用意します。DFlash2 本体の取得はこのオプションでは行わず、ヘルプが案内する `strata drafting fetch` が別途必要です（`setup.py:9693-9696, 9491-9494, 10575-10585`）。

## 使い方

Strata のソースディレクトリで、例えば次のように指定します。

```sh
./setup.sh --family qwen --model IQ3_S --drafter dflash2 --no-start
```

`setup.sh` は全引数を `setup.py` に渡します（`setup.sh:76`）。Windows の `START-HERE.bat` も `%*` を `setup.py` に渡します（`START-HERE.bat:48,53`）。

## 値と既定値

- parser は `choices=["mtp", "dflash2"]` を指定し、型変換・追加の値域検査はありません（`setup.py:9693`）。それ以外の値は `argparse` が拒否し、usage とエラーを表示して終了します。
- 既定値は `None`（未指定）です。実装上、未指定と `--drafter mtp` はどちらも DFlash2 専用分岐に入らず、MTP が必要で未配置なら従来どおり取得・生成します（`setup.py:9693, 10434-10435, 10575-10586`）。
- `--drafter dflash2` と `--mtp off` を同時指定した場合、MTP を無効にする `--mtp off` の分岐が先に処理されます（`setup.py:10575-10579`）。

## 実行時の動作

通常のセットアップ経路では、ディスク必要量の見積もりから MTP の約5.2 GBを除外し（MTP が未配置で、`--mtp off` でもなく、`--drafter dflash2` でもない場合だけ加算）、セットアップ工程でも MTP 層がないときに DFlash2 用語彙を供給して MTP の取得・生成を飛ばします（`setup.py:10427-10438, 10568-10586`）。MTP が既に存在する場合、この分岐はそれを削除しません。DFlash2 のモデルデータはこの処理では取得されません。

**このオプション値自体は run config の `drafting` キーに書き込まれません。** parser 後の利用箇所は MTP の見積もりと取得分岐であり、生成 config の構築箇所は `drafting` キーを設定しません（`setup.py:10434, 10577-10579, 10613-10616, 10813-10815`）。保存時に setup が書くキーの一覧にも `drafting` は含まれず、既存 config にある setup 管轄外のキーは保持されます（`setup.py:6665-6670, 6680-6713, 6815-6845`）。したがって、ヘルプの「choice is its `drafting` key」という記述（`setup.py:9694-9696`）と異なり、新規 config に `--drafter dflash2` の選択は記録されません。既存 config の `drafting` 値があれば保存処理で保持され得ますが、この CLI 値でその値を変更する実装は確認できませんでした。

## 適用条件と副作用

- `--drafter dflash2` の MTP 抑止分岐は、MTP が未配置の場合にのみ働きます。MTP が既に存在すれば残り、通常の後続処理が既存層と語彙を更新します（`setup.py:10568-10593`）。
- `--mtp off` が指定されている場合はそちらの分岐が優先し、MTP を取得しません。`--drafter` と `--mtp` の組み合わせ自体を拒否する validation はありません（`setup.py:9689-9696, 10575-10586`）。
- Apple Silicon の通常の `setup.py` 実行は parser を作る前に `metal/setup_mac.py` へ委譲します（`setup.py:9566-9567`）。Mac 側 parser は未知の引数を警告して続行する実装であり、`--drafter` は同 parser の索引項目にありません（`metal/setup_mac.py:362-364`、`docs/cli/README.md` の `source-setup/mac/` 節）。このため、Mac の通常委譲経路で本オプションが有効とは確認できません。
- wrapper と `setup.py` はモデルファイル、MTP 関連ファイル、run config を読み書きするセットアップ処理を起動します。DFlash2 用語彙の配置に失敗した場合は警告が出ます（`setup.py:7750-7755, 9491-9494, 10577-10579`）。

## 出力とエラー

- 未対応値は `argparse` の choices 検証で拒否されます（`setup.py:9693, 9717`）。独自の終了コードや専用エラーメッセージは定義されていません。
- MTP 層がなく `--drafter dflash2` が指定されたときは、MTP を取得しない旨をセットアップの通常出力へ表示します（`setup.py:10577-10579`）。この表示は DFlash2 の本体が取得済みであることを保証しません。
- `--drafter dflash2` 専用の終了コードはありません。セットアップ全体のダウンロード、ディスク容量、エンジン準備などの失敗経路は通常の setup 処理に従います。

## 根拠

- parser とヘルプ説明: `setup.py:9693-9696`。
- 値の受理後の参照、MTP 容量見積もりと通常の取得経路: `setup.py:10427-10438, 10568-10586`。
- Apple Silicon の委譲: `setup.py:9566-9567`、Mac parser の未知引数処理: `metal/setup_mac.py:362-364`。
- run config に書くキー、既存キーの保持、config 書き込み: `setup.py:6665-6713, 6815-6845, 10813-10815, 10951-10969`。
- wrapper の引数委譲: `setup.sh:76`、`START-HERE.bat:48,53`。
