# `--draft-vocab`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（root） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | `cjk`、`en`、`cyrillic`、`fr`、`latin`、`arabic` のいずれか |

## 役割

MTP draft layer と DFlash2 が使う draft vocabulary の subset を選びます。setup は選択値をモデル設定に記録し、取得済みの MTP または DFlash2 の vocab ファイルを選択に合わせて配置・更新します（`terminal/setup.py:8711-8712, 12496-12502`、`terminal/strata_control/setup_config.py:535-536`）。

## 使い方

Linux の Strata checkout で、例えば次のようにモデル設定時に指定します。`--no-start` は設定後のモデル起動を抑止します。

```sh
./setup.sh --model IQ3_S --draft-vocab en --no-start
```

`setup.sh` は `terminal/setup.py` を起動する入口です。Windows では同じ root parser の入口として `START-HERE.bat` があります（`terminal/setup.py:4-5`）。

## 値と既定値

parser は `choices=list(DRAFT_VOCABS)` で6つの値を許可し、オプション自体の既定値は指定していません（`None`）。選択値と対応ファイルは `terminal/setup.py:8711-8712, 11555-11563` に定義されています。`cjk` は `draft_vocab.bin`、それ以外は各名前に対応する `draft_vocab_<name>.bin` です。

この parser の help 文は `cjk`、`en`、`cyrillic`、`fr`、`latin` の説明を記しますが、`arabic` は文面に列挙していません。それでも `DRAFT_VOCABS` に含まれるため parser は受理します（`terminal/setup.py:8711-8712, 11555-11563`）。ファイル内容自体の token 一覧はこの調査では検査していません。

未指定で再 setup する場合、保存済みモデル設定に有効な `draft_vocab` があればそれを引き継ぎ、なければ setup がファイルを更新する箇所では `cjk` を使います（`terminal/setup.py:8715-8722, 12496-12502`）。

## 実行時の動作

値は `argparse` で検証され、setup の設定生成に渡されます。明示値がある場合はモデル設定の `draft_vocab` として保存されます（`terminal/setup.py:11444, 11555-11563, 11606`、`terminal/strata_control/setup_config.py:120, 535-536`）。setup を再実行すると、明示値を優先し、なければ設定ファイルに以前保存された有効値を選びます（`terminal/setup.py:8715-8722, 12496-12497`）。

すでに設定済みモデルを通常起動する場合にもこの parser option は使えます。明示した値は `start()` に渡され、モデル設定へ保存されて、その設定が指す MTP / DFlash2 vocab ファイルが更新されます（`terminal/setup.py:11761-11775, 8558-8601`）。

MTP draft layer が存在する場合、選択 subset のファイルをその runtime ディレクトリの `draft_vocab.bin` に反映します。選んだ配布 subset が見つからない場合、runtime ディレクトリがない場合はコピーを行いません。既存ファイルがある場合、Strata 配布 subset と確認できる内容なら選択値に更新し、手動作成など配布元と一致しない内容は保持します（`terminal/setup.py:9110-9132, 12498-12500`）。DFlash2 用の既存コピーも、コピー先が存在する場合に選択値に合わせて更新されます（`terminal/setup.py:9100-9107, 12501`）。

MTP が無く DFlash2 を選んでいる経路では、setup は選択値、保存済み値、いずれもなければ `cjk` を渡して vocab を pack の隣に供給します（`terminal/setup.py:9092-9097, 12483-12488`）。DFlash2 起動側では、設定に保存した利用者の値が優先されます。未指定時に言語 signal から自動選択する処理もありますが、engine が file-by-name 形式で受け取り、選ばれた配布ファイルがモデルの vocab に適合すると確認できる場合に限られ、その決定は設定へ保存されません（`terminal/strata_control/drafting.py:1425-1445`）。

## 適用条件と副作用

このオプションは setup によるモデル設定と draft vocab ファイルに作用します。GPU/VRAM の状況によって setup は小さい subset を提案する場合がありますが、提案は設定を変更しません。14 GB 未満の VRAM で、明示選択も保存済み選択もない場合に提案されます（`terminal/setup.py:8750-8766, 12502`）。

root scope の通常 parser は Apple Silicon の通常経路では使われず、`setup.py` から `engine/metal/setup_mac.py` へ引数ごと委譲されます。macOS の個別 option 文書は索引の `source-setup/mac/--draft-vocab.md` です（`terminal/setup.py:11435-11437`）。

## 出力とエラー

許可されていない値は `argparse` の choices 検証で拒否されます。`setup.py` は `parse_args()` を使います（`terminal/setup.py:11555-11563, 11606`）。

DFlash2 用の必要な draft vocabulary ファイルを Strata checkout 内で供給できない場合、setup は「ファイルがないため DFlash2 を起動できない」と警告し、Strata の更新を案内します（`terminal/setup.py:9092-9097`）。

## 根拠

- 索引上の tool ID、入口、parser、scope: `docs/cli/000_cli_tools.md:15`（strata-envvars）。
- オプションの索引リンクと配置: `docs/cli/README.md:1659-1674`（strata-envvars）。
- parser、値検証、通常 parser 呼び出し: `terminal/setup.py:11555-11563, 11606`。
- 値とファイルの対応、保存済み値の読込: `terminal/setup.py:8711-8722`。
- MTP / DFlash2 用ファイル更新および設定反映: `terminal/setup.py:9092-9132, 12483-12502`、`terminal/strata_control/setup_config.py:535-536`。
- DFlash2 起動時の明示選択と未指定時の言語判定: `terminal/strata_control/drafting.py:1299-1313, 1425-1445`。
- macOS の委譲経路: `terminal/setup.py:11435-11437`。
