# `--context`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--context` |
| 別名 | なし |
| 値 | 必須。コンテキスト長を表すサイズ文字列。正規化後は token 数の整数 |

## 役割

モデルが一度に扱う会話コンテキストの長さを指定します。モデル選択・GPU/メモリ配置と合わせてセットアップへ渡され、起動するエンジンの最大コンテキスト設定に反映されます。メモリに収まらない値も CLI 共通の上限で拒否するのではなく、launch が警告を出したうえでモデルごとのセットアップ処理へ渡します。

## 使い方

```sh
# 128K tokens でモデルを起動する
strata launch --model iq3_xxs --context 128k --no-tui

# 保存済み preset の他の設定を使い、この起動だけ 64K にする
strata launch --preset "Office" --context 64k --no-tui

# 実行内容を確認する（設定変更や起動は行わない）
strata launch --model q2_0 --context 256k --plan
```

## 値と既定値

- 値の構文は整数または小数に、任意で `k` または `m` を付けます。大文字小文字は区別されません。`k` は 1,024 tokens、`m` は 1,048,576 tokens として計算し、結果を最も近い整数へ丸めます。空白、`_`、`,` は入力文字列から除かれます。たとえば `128k` は `131072` tokens です（`terminal/strata_cli/launch/settings.py:90-100`）。
- 正規化後 1,024 tokens 未満は受け付けません。形式不正または小さすぎる値は parser の型変換エラーになります。parser 自体には共通の最大値検査はありません（`terminal/strata_cli/launch/cmd.py:46-50,91`、`terminal/strata_cli/launch/settings.py:93-100`）。
- 省略時は `--context` 固有の固定値ではなく、preset に保存された値があればそれを使います。値が未設定なら選択モデルのカタログ値で補い、その後の model setup 側にもモデル群ごとの既定値があります（`terminal/strata_cli/launch/cmd.py:216-220,246-247,368-370`）。
- `--preset` と併用すると、指定値が読み込んだ preset の値をこの起動に限って上書きします。`--save-preset` を付けた場合は起動 preset として保存されます（`terminal/strata_cli/launch/cmd.py:216-220,246-247,311-313,962-966`）。

## 実行時の動作

1. parser は `_context` を通じて値を token 数の整数に変換します（`terminal/strata_cli/launch/cmd.py:46-50,91`）。
2. `settings_from_args` は `--preset` があればその設定を読み、それに `--context` の明示値を重ねます。モデル未指定時の既定モデル選定と、context 未設定時の `catalog.max_context` による補完は後続処理で行われます（`terminal/strata_cli/launch/cmd.py:216-220,246-247,349-370`）。
3. `--plan` では決定した context を表示し、「Nothing was changed.」として終了します（Strata ソース `terminal/strata_cli/launch/cmd.py:897-924`）。通常起動では `Runner.setup_args()` が整数値を `setup.py --context <tokens>` として渡します（`terminal/strata_cli/launch/runner.py:1351-1362,1719-1730`）。
4. setup.py はモデル群ごとに context を配置・メモリ計画へ使います。例として標準モデル経路は指定値をそのまま採用し、RAM 見積もりを警告します（`terminal/setup.py:12143-12165`）；Hy4-Flash と Inkling-2-Mini はそれぞれの fit planner に値を渡します（`terminal/setup.py:10301-10325,10777-10802`）。setup.py は各セットアップ経路で選ばれた token 数を engine 引数 `--max-context` として起動設定へ書き込みます（標準経路 `terminal/setup.py:9984-9986`、Hy4-Flash `terminal/setup.py:10373-10375`、Inkling-2-Mini `terminal/setup.py:10890-10892`）。launch 側の既存設定に対する選択値の反映処理もありますが、これはコマンド表示・比較用で、実起動は setup.py を通ります（`terminal/strata_cli/launch/runner.py:305-325`）。

## 適用条件と副作用

- launch の共通チェックは 262,144 tokens を超える値に、モデルの訓練長を超える旨と実験的な rope scaling に関する警告を追加します。これは拒否ではありません。また、fit 上の推奨値を超える場合も警告します（`terminal/strata_cli/launch/settings.py:348-356`）。
- setup.py のモデル別経路が実際の制約処理を担います。たとえば標準経路は 128K を超える RAM 見積もりを警告し値を保持します（`terminal/setup.py:12143-12165`）。一方、独自モデルファイル経路の当該箇所は 256K 超について、その経路では rope scaling がまだないと警告します（`terminal/setup.py:9875-9893`）。したがって、共通警告だけから全モデルでの拡張方法や起動成功を保証することはできません。
- `--context` の指定だけでデータ移動や preset の書き換えは行われません。通常起動ではモデルの準備・設定書き込み・エンジン起動へ進みます。`--plan` は変更せず終了し、`--save-preset` は preset を保存します（`terminal/strata_cli/launch/cmd.py:897-924,949-966`）。

## 出力とエラー

- 不正な形式または 1,024 tokens 未満の場合、`argparse` の型変換エラーとして拒否されます。上限超過は parser エラーではなく、上記の警告とモデル別 setup の経路に委ねられます（`terminal/strata_cli/launch/cmd.py:46-50,91`、`terminal/strata_cli/launch/settings.py:90-100,348-356`）。
- 通常起動時の context やメモリ適合性の警告は launch の notice として集約されます（`terminal/strata_cli/launch/cmd.py:401,882-889`）。setup または engine が値を使えず起動できない場合の具体的な診断・終了コードは、失敗したモデル経路と engine に依存するため、`--context` 共通の単一コードとしては特定できません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:46-50,81-92` — 文字列 parser と `strata launch --context` の登録。
- `terminal/strata_cli/launch/settings.py:90-100` — サイズ表記の変換、最小値検査。
- `terminal/strata_cli/launch/cmd.py:216-220,246-247,349-370,897-924` — preset と値の合成、未指定時補完、plan 出力。
- `terminal/strata_cli/launch/settings.py:348-356` — 256K 超と fit 超過の警告。
- `terminal/strata_cli/launch/runner.py:305-325,1351-1362,1719-1730` — context を engine 設定および `setup.py` に渡す処理。
- `terminal/setup.py:9875-9893,9984-9986,10301-10325,10373-10375,10777-10802,10890-10892,12143-12185` — モデル群別の context 適用・配置計画・警告。
