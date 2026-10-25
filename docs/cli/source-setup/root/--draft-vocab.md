# `--draft-vocab`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper からも委譲） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | `cjk`、`en`、`cyrillic`、`fr` のいずれか |

## 役割

MTP draft layer が参照する語彙部分集合を選びます。選択値に対応する同梱ファイルを MTP runtime の `draft_vocab.bin` として配置し、通常の setup 経路ではモデル設定 `draft_vocab` に保存します。これは draft head が提案できる token の集合を選ぶ設定で、メインモデルの tokenizer を変更するオプションではありません。エンジンは MTP の draft head を bind するときにこのファイルを読みます（`src/core/mtp.cpp:692-706`、`include/strata/core/mtp.hpp:220-221`）。

## 使い方

Linux の例:

```sh
./setup.sh --draft-vocab en
```

Windows では `START-HERE.bat --draft-vocab cyrillic` のように指定できます。既存モデルを起動する際にも `./setup.sh --draft-vocab fr` の形で渡すと、そのモデルの設定に選択を保存してから起動します。各 wrapper は引数を `setup.py` に渡します（`setup.sh:9-12,76`、`START-HERE.bat:44-54`）。

## 値と既定値

- `cjk`: 中国語・日本語・韓国語を含む部分集合。対応元ファイルは `data/draft_vocab.bin`。
- `en`: 英語とコード向け。対応元ファイルは `data/draft_vocab_en.bin`。
- `cyrillic`: 英語・コードとキリル文字を含む部分集合。対応元ファイルは `data/draft_vocab_cyrillic.bin`。
- `fr`: 英語・コードとフランス語向け token を含む部分集合。対応元ファイルは `data/draft_vocab_fr.bin`。

parser は `choices=list(DRAFT_VOCABS)` を指定し、明示的な `default` は設定していません。そのため引数値は未指定時 `None` です。通常の Qwen setup 経路では未指定なら同モデルの既存設定値を読み、設定がなければ実効値 `cjk` を使います（`setup.py:6885-6896,8518-8522,9394-9398`）。初回インストールの `cjk` はこの実効 fallback です。

値の検査は `argparse` の choices によります。列挙外の値は parser で拒否されます。空文字も有効な choice ではありません。重複指定時の特別処理はなく、通常の `argparse` の格納動作に従い最後に parse された値が使われます（parser 定義: `setup.py:8518-8522`）。

同 revision の `python3 setup.py --help` でも4値を確認しました。help の性能・VRAM目安（例: `en` は約110 MiB少ない等）は CLI の説明にある値であり、本調査では測定・検証していません。

## 実行時の動作

通常のモデル setup では、MTP runtime に `experts.bin` がある場合に選択に対応する `data/` のファイルを `rt/draft_vocab.bin` へ反映します。`refresh_draft_vocab()` は同梱 subset または旧版の既知 SHA-256 と一致する既存ファイルなら選択値に応じて置換し、選択済みファイルと同じ hash なら何もしません。既知の同梱ファイルでない、手作業のファイルは保持します。選択ファイルが checkout にない場合、または runtime directory がない場合も関数は何もせず戻ります（`setup.py:6881-6886,7149-7168,9394-9398`）。

通常の Qwen setup は選択値（未指定なら既存設定、なければ `cjk`）を `cfg["draft_vocab"]` に記録します。既存モデルの通常起動では、明示値を `keep` として受け取り、変更があれば JSON 設定へ保存し、MTP runtime が有効で own-path config でなければ runtime の subset も更新します（`setup.py:6745-6774,8674-8691,9673-9675`）。したがって設定はそのモデルに記憶されます。

`--update` を付けた場合、`update_install()` はオプションの `a.draft_vocab` を参照せず、各モデル設定に保存済みの値（未設定時 `cjk`）で runtime subset を更新します。よって `setup.py --update --draft-vocab en` は `en` への変更指定としては使われません（`setup.py:6682-6708,7171-7187`）。更新 wrapper は引数を渡しますが、オプションの意味は委譲先のこの分岐に従います（`update.sh:2-6`、`UPDATE.bat:2-6`）。

## 適用条件と副作用

- 主な効果は MTP draft runtime が存在して同機能を使うときに現れます。MTP runtime がなくても setup の通常経路では明示した値がモデル設定に保存される場合がありますが、runtime ファイルがなければコピーされません（`setup.py:9394-9398,9673-9675`）。
- setup は `shutil.copyfile()` で `rt/draft_vocab.bin` を作成または置換します。選択値に応じた subset file の内容を、既知の Strata 配布ファイルと認識できる既存ファイルに限って上書きします。独自ファイルは保持します（`setup.py:7155-7168`）。
- `mac_control_setup()` では MTP を使うとき `a.draft_vocab or "cjk"` で更新し、設定キーは値を明示した場合にのみ記録します。setup を再実行して値を省略した場合に以前の選択を保持する処理は、この分岐には見当たりません（`setup.py:8376-8393`）。
- SYCL の setup は小容量カード条件で明示値がない場合に `en` を argv に追加し、同じ setup の処理へ戻します。利用者が値を明示した場合はその値を保ちます（`sycl/setup_intel.py:541-554`）。
- MTP が無効、またはエンジンが別の語彙ファイルを明示指定する経路など、実際に runtime の標準 `draft_vocab.bin` を読む条件を満たさない場合、このファイル選択はその実行で使われないことがあります。エンジンの標準 path は `<mtp>/draft_vocab.bin` です（`include/strata/core/mtp.hpp:220-221`）。

## 出力とエラー

コピー先ファイルの更新時、ファイルが既存で置換対象と判定されると subset の説明を `ok()` で表示してからコピーします。既存ファイルが要求値と同じ、独自ファイル、元ファイルまたは runtime directory がない場合は、この helper からは通知されずに戻ります（`setup.py:7155-7168`）。

choice 外の値は `argparse` の parser error になります（`setup.py:8518-8522,8553`）。コピー時の I/O 例外を `refresh_draft_vocab()` 内で捕捉する処理はありません（同 `setup.py:7155-7168`）。この調査では各種ファイルシステム障害時の wrapper ごとの表示・終了コードまでは確認していません。

## 根拠

- parser、受理値: `setup.py:8518-8522`。同 revision の `python3 setup.py --help` と照合。
- subset の対応表、既存設定読み込み: `setup.py:6881-6896`。
- 選択ファイルの runtime 反映、上書き条件: `setup.py:7149-7168`。
- 通常 setup の fallback、保存、推奨表示: `setup.py:9394-9400,9673-9675`。
- 既存モデル起動時の保存と runtime 更新: `setup.py:6745-6774,8674-8691`。
- 更新時に設定値から subset を選ぶ処理: `setup.py:6682-6708,7171-7187`。
- macOS の setup 分岐: `setup.py:8376-8393`。
- SYCL の小容量カード向け自動値: `sycl/setup_intel.py:541-554`。
- wrapper の引数委譲: `setup.sh:9-12,76`、`START-HERE.bat:44-54`、`update.sh:2-6`、`UPDATE.bat:2-6`。
- エンジンが標準 runtime subset を読む箇所: `include/strata/core/mtp.hpp:220-221`、`src/core/mtp.cpp:692-706`。

調査時の Strata 作業ツリーは `## main...origin/main` で、status に未コミット変更は表示されませんでした。Release archive や別 platform の配布物は比較していません。
