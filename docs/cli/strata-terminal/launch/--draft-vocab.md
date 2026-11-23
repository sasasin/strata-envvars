# `--draft-vocab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | `cjk`、`en`、`cyrillic`、`fr`、`latin`、`arabic` のいずれか |

## 役割

MTP / DFlash2 の draft head が候補にできるトークン集合を選びます。`strata launch` は指定値を launch 設定に保持し、対応するモデル family の setup に渡します。setup はその選択に応じて draft vocabulary ファイルを用意します。Terminal の parser が受理する family は `qwen`、`swift`、`coder`、`unsloth`、`gyro` です。

## 使い方

```sh
# 英語・コード向けの vocabulary を選んでモデルを起動する
strata launch --model q2_0 --draft-vocab en

# preset を使い、この起動ではロシア語などの Cyrillic 用 subset を指定する
strata launch --preset Office --draft-vocab cyrillic
```

## 値と既定値

値は前後の空白を除去して小文字化した後、`cjk`、`en`、`cyrillic`、`fr`、`latin`、`arabic` と照合されます。そのため大文字や前後に空白のある入力も正規化後に受理されます。その他の値は `ArgumentTypeError` になります。Terminal 側の候補 tuple は `terminal/strata_cli/launch/settings.py:31-35`、正規化・拒否処理は `terminal/strata_cli/launch/cmd.py:35-43`、引数登録は同 `cmd.py:105-107` にあります。

| 値 | 選ばれるファイル | ソース上で確認できる内容 |
| --- | --- | --- |
| `cjk` | `draft_vocab.bin` | 中国語・日本語・韓国語のトークンを含む標準 subset |
| `en` | `draft_vocab_en.bin` | 英語・コード向け subset |
| `cyrillic` | `draft_vocab_cyrillic.bin` | 英語・コードと Cyrillic script 向け |
| `fr` | `draft_vocab_fr.bin` | 英語・コードとフランス語向け |
| `latin` | `draft_vocab_latin.bin` | 英語・コードと Latin script の複数言語向け |
| `arabic` | `draft_vocab_arabic.bin` | Arabic script 向け |

対応ファイル名は `terminal/setup.py:8627-8628`、subset の説明は同 `setup.py:9027-9032` と `terminal/strata_control/drafting.py:1237-1262` にあります。

省略時の Terminal 設定値は `None` です（`terminal/strata_cli/launch/settings.py:105-120`）。preset の値を読み込んだ後、明示値があるときに限り設定を上書きします（`terminal/strata_cli/launch/cmd.py:215-221, 256-259`）。setup にこの引数がなければ、既存モデルでは保存済みの `draft_vocab` が引き継がれ、新しい設定では `cjk` が fallback として使われます（`terminal/setup.py:12275-12280`）。

setup.py の parser は `DRAFT_VOCABS` の6値を候補として登録しています（`terminal/setup.py:8627-8628, 11337-11345`）。Terminal の表示用 `metavar` は5値しか列挙していませんが（`terminal/strata_cli/launch/cmd.py:105`）、実際の parser の候補には `arabic` も含まれます。

## 実行時の動作

設定済み preset を読み込んだ後の起動では、明示した値が preset の `draft_vocab` を上書きします。対象 family に対する setup 引数には `--draft-vocab <値>` が追加され、macOS 用に setup 引数を絞る経路でもこの引数は保持されます（`terminal/strata_cli/launch/cmd.py:215-221, 256-259`; `terminal/strata_cli/launch/runner.py:1284-1320, 1351-1366`）。同じ設定がすでに同じ port で動作中なら、launch は再起動せず既存 server を返します。選択が異なる場合は `--restart` 等の再起動経路に従います（`terminal/strata_cli/launch/runner.py:2478-2509`）。

MTP layer が使われる setup では、選択した subset を MTP 用の `rt/draft_vocab.bin` に反映します。配布済み subset なら選択に合わせてコピーし、手作業で作られた別ファイルは保持します（`terminal/setup.py:9026-9048, 12275-12280`）。DFlash2 専用構成にも選択を反映し、setup が `draft_vocab` をモデル設定に保存します（`terminal/setup.py:12260-12280`; config への保存処理は同 `setup.py:11120-11128`）。

明示選択がなく保存値もない DFlash2 起動では、engine がファイル名で vocabulary を読む形式の場合、コンピューターの UI 言語・地域設定・キーボード言語から subset を選ぶ経路があります。CJK のシグナルがあれば `cjk`、それ以外は認識可能な Arabic / Cyrillic / Latin 言語から選び、判定できない場合や選択ファイルが利用できない場合は既定ファイルに戻ります。この自動選択は起動時に計算され、config には保存されません（`terminal/strata_control/drafting.py:1248-1262, 1299-1313, 1425-1445`）。

## 適用条件と副作用

- この引数は `qwen`、`swift`、`coder`、`unsloth`、`gyro` family に対してのみ setup 引数へ転送されます。それ以外の family では Terminal parser は値を受理しますが、runner は setup に転送しません（`terminal/strata_cli/launch/modelstate.py:82`; `terminal/strata_cli/launch/runner.py:1317-1320`）。
- MTP が利用できる場合、setup は MTP 用 vocabulary ファイルを作成または更新します。既存ファイルが配布済み subset と一致しない手作り subset なら上書きしません（`terminal/setup.py:9033-9048`）。
- DFlash2 用コピーは必要な場合にデータディレクトリ配下へ作成・置換され、既存の手作業 subset は維持されます（`terminal/strata_control/drafting.py:1452-1479`）。
- `--plan` は変更なしで計画を表示して終了する経路であり、実 setup の実行には進みません（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 出力とエラー

候補外の値は Terminal の型変換で `ArgumentTypeError` となり、setup の候補外値も `argparse` の `choices` により拒否されます（`terminal/strata_cli/launch/cmd.py:35-43, 105`; `terminal/setup.py:11337-11345`）。この値に固有の stdout / stderr 文言や終了コードは Strata のソースだけでは確認できないため、ここでは特定しません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:35-43, 105, 215-221, 256-259` — CLI 値の正規化・検証、引数定義、preset 設定への適用。
- `terminal/strata_cli/launch/settings.py:31-35, 105-120` — 選択肢と未指定状態。
- `terminal/strata_cli/launch/modelstate.py:82`、`terminal/strata_cli/launch/runner.py:1284-1320, 1351-1366, 2478-2509` — 対象 family への転送、macOS 引数保持、稼働中 server との相互作用。
- `terminal/setup.py:8627-8638, 9026-9048, 11120-11128, 12260-12280` — setup 側の値一覧、MTP / DFlash2 vocabulary の更新と設定保存。
- `terminal/strata_control/drafting.py:1248-1262, 1299-1313, 1425-1445, 1452-1479` — 言語による DFlash2 の自動選択と DFlash2 用ファイルの管理。
