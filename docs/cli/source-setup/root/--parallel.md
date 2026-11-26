# `--parallel`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などから起動するセットアップ CLI） |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`。parser に数値範囲の指定はない |

## 役割

セットアップで作成・更新するモデルの実行設定に、同時に処理するリクエスト数（エンジンの batch slot 数）を指定する。通常のモデルでは指定値を run config の `parallel` に記録し、Inkling-2-Mini ではモデル配置計画にも slot 数として渡す。省略時は通常のモデルでは自動推奨を表示するだけで指定値を新たに設定せず、Inkling-2-Mini は既定の 1 slot で計画する。いずれも複数リクエストを同時に処理すると各 slot が VRAM を使うため、セットアップはカードやモデルに対する推奨・警告を表示する。 (`terminal/setup.py:11586-11588`, `terminal/strata_control/setup_config.py:550-560`, `terminal/setup.py:10797-10798`)

## 使い方

```bash
# 4 リクエストまで同時にデコードする設定でセットアップ
python3 terminal/setup.py --family qwen --model IQ3_S --parallel 4

# Inkling-2-Mini の配置計画を 8 slot として作成
python3 terminal/setup.py --family inkling-2-mini --model SQ-20 --parallel 8
```

## 値と既定値

- `argparse` の `type=int` で変換される。整数以外、または値の省略は parser の引数エラーになる。独自の `choices` や最小値検査は登録されていない。 (`terminal/setup.py:11586-11588`, `terminal/setup.py:11606`)
- 通常のモデル経路では `N >= 2` を run config の `parallel` に保存し、`N <= 1` は `parallel: 1` として扱う。 (`terminal/strata_control/setup_config.py:552-560`)
- 同経路のセットアップ定数は `PARALLEL_MAX = 8`。8 を超える値は入力時に拒否・丸められず、推奨メッセージでエンジンは最大 8 件までと案内される。 (`terminal/setup.py:8860`, `terminal/setup.py:8942-8945`)
- 独自の Qwen 系モデル経路も `N <= 1` を 1 として保存する。8 超過時は同じく最大 8 件の注意を表示し、指定値自体は「選択どおり」に保持する。 (`terminal/setup.py:9789-9818`, `terminal/setup.py:10035-10044`)
- Inkling-2-Mini 経路では 1〜64 に収めて配置計画へ渡す。0 や負数は 1 に、64 超は 64 に丸める。指定がなければ既定値は 1。 (`terminal/setup.py:10797-10798`, `terminal/strata_control/inkling_fit.py:44-46`)
- 省略時に既存 run config がある場合、セットアップが今回 `parallel` を書かなければ、`SETUP_KEYS` に含まれない設定値として既存の `parallel` が引き継がれる。 (`terminal/setup.py:7540-7545`, `terminal/setup.py:7557-7568`)

## 実行時の動作

通常のモデルでは `setup_config.config_for()` が `--parallel` の指定を判定し、2 以上なら run config の `parallel` に保存して、VRAM・コンテキスト・KV 形式・KV streaming・RAM から計算した推奨との比較を出力する。1 以下なら一件ずつ処理する設定にする。値を指定しない場合は推奨を案内するだけで、明示的な slot 数は追加しない。 (`terminal/setup.py:12521-12526`, `terminal/strata_control/setup_config.py:550-560`, `terminal/setup.py:8904-8952`, `terminal/setup.py:12548-12551`)

独自モデル経路では、同時処理数の推奨や指定値とカード容量の比較を表示し、指定数を config に保存する。Inkling-2-Mini 経路では、slot 数を `inkling_fit.place()` の配置計画に含め、生成する run config の `parallel` に設定する。 (`terminal/setup.py:9789-9818`, `terminal/setup.py:10035-10044`, `terminal/setup.py:10797-10798`, `terminal/setup.py:10910-10922`)

## 適用条件と副作用

- これは `strata launch` の engine CLI 引数ではなく、`source-setup` のセットアップ CLI オプションである。結果は run config の `parallel` として保存される。通常経路では指定値の VRAM 消費や KV streaming 時の RAM 需要を基に注意を表示するが、容量不足を理由にこのオプション自体が値を拒否する処理は確認できない。 (`terminal/setup.py:11586-11588`, `terminal/strata_control/setup_config.py:550-560`, `terminal/setup.py:8925-8952`)
- 複数 GPU の replica profile または AMD 4 GPU profile が適用されるとき、`--parallel` を指定したかどうかが渡されます。指定済みなら自動 profile は並列数を上書きしません。 (`terminal/strata_control/setup_config.py:487-508`, `terminal/strata_control/amd_four_card.py:64-89`)
- 設定を書き換えるとき、従来の run config と異なる内容なら `.bak` を作ってから更新する処理があります。明示した `--parallel` は今回の設定に反映されます。 (`terminal/setup.py:7715-7745`)
- 省略時の自動推奨は「提案」であり、通常経路では自動的に複数 slot に切り替えるものではありません。 (`terminal/setup.py:8925-8941`, `terminal/setup.py:12548-12551`)

## 出力とエラー

- `N` が整数に変換できない場合や値を省略した場合は `argparse` の引数エラー経路です。ソースに `--parallel` 固有の終了コード処理はありません。 (`terminal/setup.py:11586-11588`, `terminal/setup.py:11606`)
- 通常経路と独自モデル経路は、指定値、推奨との差、通常経路では VRAM と KV streaming 時の RAM 見積りを表示します。通常のモデル経路では要求値が 8 を超えると、エンジンの上限が 8 と表示されます。 (`terminal/setup.py:8942-8952`, `terminal/setup.py:9810-9818`)
- ここで確認したセットアップ parser は指定値の独自範囲エラーを出しません。各エンジンの受理範囲や起動時の失敗条件は backend ごとに別実装のため、この文書ではセットアップ側の値処理までを対象とします。

## 根拠

- `terminal/setup.py:11444-11451`, `terminal/setup.py:11586-11606` — `argparse` parser、`--parallel` の整数型・help、引数 parse。
- `terminal/strata_control/setup_config.py:550-560` — 通常モデル経路で config に値を設定し、推奨文を出す分岐。
- `terminal/setup.py:8860-8862`, `terminal/setup.py:8904-8952` — 通常モデルの上限と推奨計算・出力。
- `terminal/setup.py:9789-9818`, `terminal/setup.py:10035-10044` — 独自モデル経路の推奨表示、値保存、上限案内。
- `terminal/setup.py:10797-10798`, `terminal/setup.py:10910-10922`; `terminal/strata_control/inkling_fit.py:44-46` — Inkling の値補正、配置計画、run config の値、上限定義。
- `terminal/strata_control/setup_config.py:487-508`; `terminal/strata_control/amd_four_card.py:64-89` — 複数 GPU profile が明示値を優先する条件。
- `terminal/setup.py:7540-7545`, `terminal/setup.py:7557-7568`, `terminal/setup.py:7715-7745` — 省略時の既存設定引継ぎ、および変更時の backup と config 書き込み。
