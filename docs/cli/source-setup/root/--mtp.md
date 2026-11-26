# `setup.py --mtp`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からも委譲） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | `on` または `off`（必須） |

## 役割

モデルの実行設定で MTP draft layer を有効または無効にします。`off` は層の重みを実行時に使わない設定として保存し、利用可能な VRAM と RAM を増やす代わりに生成速度を下げます。`on` は明示的に有効へ戻します。これは推論エンジンに渡す `--mtp <dir>` のパス指定とは別の、セットアップ側の切替です（`terminal/setup.py:11578-11581`、`terminal/strata_control/setup_config.py:539-549`）。

## 使い方

Strata checkout のルートで実行します。次の例はセットアップ処理を行い、最後のモデル起動だけを省きます。

```bash
# MTP を無効にした設定でセットアップする
python terminal/setup.py --mtp off --no-start

# MTP を再び有効にした設定でセットアップする
python terminal/setup.py --mtp on --no-start
```

`setup.sh` は checkout 内の `setup.py` に引数を渡します（`setup.sh:8-17`, `setup.sh:81`）。`--no-start` は最後の起動を省くだけで、モデル等の取得・準備や run config の書き込みを省略しません（`terminal/setup.py:12525-12527`, `terminal/setup.py:12555-12562`）。

## 値と既定値

- 値は小文字の `on` / `off` のみです。`argparse` の `choices` に合わない値や値の省略は parser のエラーになります（`terminal/setup.py:11578`）。
- オプションの省略時は引数値が `None` です。その場合このフラグによる設定変更は行わず、既存 config の `mtp` 選択は carry-over されます。新規設定時の通常選択や drafter の自動選択は別のセットアップ規則に従います（`terminal/strata_control/setup_config.py:539-549`; `terminal/setup.py:7715-7737`, `terminal/setup.py:9047-9060`）。
- 同じフラグを複数回指定した場合は `argparse` の通常の単一値引数として最後の値が残ります（`terminal/setup.py:11578`）。

## 実行時の動作

- `--mtp off` は run config に `"mtp": false` を書きます。既存 config から MTP を有効化する engine 引数が引き継がれる場合も、`draft_layer.apply` が `--mtp`、`--spec-min-p`、`--batch-mtp` を除去します（`terminal/strata_control/setup_config.py:539-546`; `terminal/strata_control/draft_layer.py:25-26`, `:51-56`）。設定は同じモデルの次回 setup にも保持されます（`terminal/setup.py:7715-7737`）。
- Windows/Linux の通常セットアップでは、`off` で MTP ファイルがまだない場合に約 5 GB の取得を見送り、既存の MTP ファイルは削除しません。`on` または指定なしで MTP が必要と判定され、ファイルがなければ取得後に `mtp_pack.py` と `mtp_rt.py` で準備します（`terminal/setup.py:12474-12495`）。
- `--mtp on` は run config に `"mtp": true` を書き、以前の `false` が carry-over で復活するのを防ぎます（`terminal/strata_control/setup_config.py:547-549`）。
- 明示的な `--mtp on` / `off` は、MTP 指定がない場合だけ働く自動 drafter 選択を止めます。省略時は、環境・モデル等に基づく Auto が DFlash2 を選ぶことがあり、その場合 MTP 層が未取得なら MTP の約 5 GB の取得を省いて DFlash2 を用意します（`terminal/setup.py:9047-9060`, `:12332-12339`, `:12481-12495`）。
- 低 RAM 向けモデルの配置見積もりでも、`off` は MTP が使う約 1 GB を VRAM expert cache の計算から除外します（`terminal/setup.py:12242-12247`）。

## 適用条件と副作用

- `--mtp off` は既存の重みファイルを消しません。セットアップが書く run config を無効にし、次回以降もその設定を維持します（`terminal/strata_control/setup_config.py:539-546`; `terminal/setup.py:7715-7747`）。
- MTP が必要でファイルがない場合、Windows/Linux 経路は `tools/mtp_fetch.py` を最大 3 回実行して取得を再試行し、取得後に pack / runtime ファイルを生成します。オフラインを示す終了コード 5 なら MTP なしで続行し、終了コード 4 なら停止、その他の失敗は再試行後に setup のエラーとして終了します（`terminal/setup.py:1160-1189`）。
- Apple Silicon の通常 source setup は parser を読む前に `engine/metal/setup_mac.py` へ引数をそのまま渡します。その経路の `--mtp` 受理・効果はこの `terminal/setup.py` の parser では規定できません。ここで説明する parser の設定動作を macOS 通常 setup に適用しないでください（`terminal/setup.py:9290-9294`, `:11434-11437`）。
- `--drafter dflash2` は別の選択肢です。MTP 層がまだない場合は MTP 重みの取得を省く経路があり、`--mtp` の有効・無効切替と同じ指定ではありません（`terminal/setup.py:11578-11585`, `:12483-12495`）。

## 出力とエラー

- 不正値は `argparse` が usage とエラーを表示し、通常の parser エラー終了となります（`terminal/setup.py:11578`, `:11606`）。
- `off` / `on` の設定時は `[ok]` メッセージが出ます（`terminal/strata_control/setup_config.py:545-549`）。MTP の取得がオフラインなら層なしでセットアップを続けます。取得先に応答がない場合は停止し、他の取得失敗は最大 3 回まで再試行してから停止します（`terminal/setup.py:1170-1189`）。
- `setup.py` の `fail` 経路は `[X]` と説明を出し、終了コード 1 で終了します（`terminal/setup.py:1049-1056`）。

## 根拠

- Parser と許容値: `terminal/setup.py:11578-11581`。
- config 値の保存と無効化時の引数除去: `terminal/strata_control/setup_config.py:539-549`; `terminal/strata_control/draft_layer.py:25-26`, `:51-56`。
- 既存設定の引き継ぎ・バックアップ: `terminal/setup.py:7715-7747`。
- 自動 drafter 選択と容量見積もり: `terminal/setup.py:9047-9060`, `:12332-12343`。
- MTP 取得・生成と失敗分岐: `terminal/setup.py:1160-1189`, `:12474-12501`。
- macOS 委譲: `terminal/setup.py:9290-9294`, `:11434-11437`。
