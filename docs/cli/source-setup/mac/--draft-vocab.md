# `--draft-vocab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `./setup.sh`（`metal/setup_mac.py`） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | `cjk`、`en`、`cyrillic`、`fr`、`latin`、`arabic` |

## 役割

MTP draft layer が候補 token として使う語彙 subset を選びます。指定した名前に対応する Strata 同梱の `data/draft_vocab_*.bin` を MTP ディレクトリの `draft_vocab.bin` に反映し、明示指定した名前をモデル設定に記録します。任意のファイルパスを渡すオプションではありません。

## 使い方

既存の Mac セットアップを更新して英語・コード向け subset を選ぶ例です。

```sh
./setup.sh --setup --draft-vocab en
```

通常起動では、既存設定のモデルをそのまま起動します。既存モデルにこの指定を反映させるには `--setup`（またはモデル選択を伴うセットアップ経路）を使います。

## 値と既定値

| 値 | 同梱ファイル |
| --- | --- |
| `cjk` | `draft_vocab.bin` |
| `en` | `draft_vocab_en.bin` |
| `cyrillic` | `draft_vocab_cyrillic.bin` |
| `fr` | `draft_vocab_fr.bin` |
| `latin` | `draft_vocab_latin.bin` |
| `arabic` | `draft_vocab_arabic.bin` |

parser は `choices=list(S.DRAFT_VOCABS)` で値を制限し、既定値は設定していません。したがって不明な値は argparse が引数エラーとして拒否します。省略時、Mac のセットアップで MTP 語彙を更新する処理は `cjk` を使います。明示指定がない場合、設定 JSON に `draft_vocab` は追加されません。

## 実行時の動作

セットアップ時に MTP を使う構成なら、`engine/metal/setup_mac.py` は MTP の `rt` ディレクトリを作り、指定値または `cjk` で `S.refresh_draft_vocab` を呼びます。セットアップ後の起動時も、モデル設定の `draft_vocab`（なければ `cjk`）で同じ更新関数を呼びます。MTP を使わない構成ではセットアップ中の語彙コピーは行われません。

更新関数は対応する同梱ファイルがあり、宛先ディレクトリが存在するときだけ処理します。宛先 `draft_vocab.bin` がない場合はコピーし、既存ファイルが同梱済み subset（または旧版の既知 subset）なら選択値に合わせて置き換えます。既存ファイルが独自作成のものと判定された場合は保持します。同じ subset が既にある場合もコピーしません。

明示値は `strata-<model>.json` の `draft_vocab` に保存されます。既存モデルの通常起動経路は、`--setup`、`--model` などのセットアップ条件がなければ引数処理後すぐ `start()` に進むため、その実行で渡した `--draft-vocab` を新しい設定として保存しません。設定に保存済みの値がある場合は起動時の更新に使われます。

## 適用条件と副作用

- 対象は索引上の macOS 用 parser `metal/setup_mac.py` です。`terminal/setup.py` は Mac の場合にこのスクリプトへ引数を委譲します。
- このオプションが選択するのは同梱 subset の名前です。subset の内容やサイズ自体を編集・生成するものではありません。
- MTP 用語彙ファイルをコピーまたは置換する場合があります。独自作成と判定された既存ファイルは保持されます。
- セットアップで明示した値はモデル設定 JSON に永続化され、後の起動時に参照されます。

## 出力とエラー

選択肢以外の値は argparse の引数エラーになります。指定語彙の同梱ファイルが見つからない場合、または MTP の宛先ディレクトリがない場合、`refresh_draft_vocab` はコピーせずに戻ります。ソースではこの未配置ケース専用の警告やエラー出力は確認できませんでした。

## 根拠

- `docs/cli/README.md:1719-1740` — `source-setup` の mac 用コマンド階層と `--draft-vocab` の索引リンク。
- `engine/metal/setup_mac.py:372-405` — Mac parser の定義、許容値、`parse_known_args`、未知の残余引数の警告。
- `engine/metal/setup_mac.py:416-418` — 既存設定がある通常起動時に `start()` へ早期 return する条件。
- `engine/metal/setup_mac.py:567-589` — MTP 利用条件、選択値または `cjk` による語彙更新。
- `engine/metal/setup_mac.py:593-612` — 明示値をモデル設定 JSON に格納して書き出す処理。
- `engine/metal/setup_mac.py:311-332` — 起動時に設定値（未設定なら `cjk`）で語彙更新を行う処理。
- `terminal/setup.py:8627-8638` — subset 名と同梱ファイルの対応、既存設定から値を読む補助関数。
- `terminal/setup.py:9026-9048` — コピー条件、既知の同梱 subset の置換、独自 subset の保持。
- `terminal/setup.py:9206-9210` — Terminal setup から Mac 用 `metal/setup_mac.py` への委譲。
