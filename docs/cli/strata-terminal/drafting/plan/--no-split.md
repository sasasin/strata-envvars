# `strata drafting plan --no-split`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--no-split` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

プランの推定で all-cards split engine が起動する想定を除外します。通常、設定が Auto の場合は split engine の起動予測が真なら、プランは split engine が使う MTP を選び、DFlash2 drafter の取得要否を示しません。このフラグを付けるとその予測分岐を飛ばし、通常の Auto 判定でプランを作ります（`strata_cli/drafting_cmd.py:39-51,69-78`）。

このフラグは `strata drafting plan` の推定にだけ作用し、`strata launch` が split engine を起動するかどうかを切り替える設定ではありません。split engine の起動設定は別の launch 経路にあります（`strata_cli/launch/cmd.py:108,251-252`）。

## 使い方

```sh
strata drafting plan --config ./run.json --no-split
```

`--config` を省略して `--mode` を指定する使い方もできます。`plan` と `fetch` は同じ parser 定義を共有しますが、この文書の対象は `plan` です（`strata_cli/drafting_cmd.py:21-32`）。

## 値と既定値

- 値は不要です。指定すると `a.no_split` が真になり、省略時は偽です（`strata_cli/drafting_cmd.py:28-29`）。
- `--no-split=true` のような値付き指定はこの parser の形式ではありません。追加値や未知引数は CLI の引数解析で拒否されます（`strata_cli/cli.py:2239-2248`）。
- フラグを複数回指定しても `store_true` のままです。別の数値範囲や値 validation はありません。

## 実行時の動作

1. `--mode` が指定されていればそれを使い、なければ設定ファイルの `drafting` を使います。設定が `"mtp": false` で、選択 mode が Auto なら、フラグの有無にかかわらず mode は `off` にされます（`strata_cli/drafting_cmd.py:54-78`）。
2. それ以外で Auto の場合、フラグなしなら `_split_expected` が設定の GPU、user args、replicas、native model、context を使って split engine の起動可能性を問い合わせます。フラグありならこの問い合わせを行わず、split 用の `mtp` への置き換えも行いません（`strata_cli/drafting_cmd.py:39-51,69-78`）。split 予測関数は調査中に確定できない条件がある場合も `False` を返す設計です（`strata_control/split_engine.py:398-431`）。
3. 続いて `drafting.needs_pack` と `drafting.needs_mtp`、`drafting.decide` が、モデル・family・backend・GPU arch・data directory・pack の有無などから必要な drafter を判定します。Auto は対象モデルかつ対応 backend なら DFlash2、それ以外は MTP になります。DFlash2 の pack がない場合、plan は取得要否を報告しますが、`plan` 自体はダウンロードを実行しません（`strata_control/drafting.py:653-691,712-722`; `strata_cli/drafting_cmd.py:81-102`）。
4. 結果には `split` が含まれます。`--no-split` の場合は split 予測による真値への設定がないため false です。人向け出力は plan の説明または判定行、`--output json` / `jsonl` は `schema_version: 1`、`ok: true` と判定データを JSON で出力します（`strata_cli/drafting_cmd.py:88-102`）。

## 適用条件と副作用

- split 回避は mode が正規化後の `auto` のときだけ影響します。明示した `mtp` / `dflash2` / `off` の判定はこのフラグで変わりません（`strata_cli/drafting_cmd.py:70-75`; `strata_control/drafting.py:404-406,653-661`）。
- `_split_expected` 内の split engine モジュール読み込みや予測で例外が起きると、例外を外へ出さず「split 予測なし」として続行します（`strata_cli/drafting_cmd.py:39-51`）。
- `plan` は help/parser の説明でも「何を取得するかを示し、変更しない」コマンドとして定義されています。処理は pack の存在確認、ハードウェア検出、計画・判定の出力で、取得・pack 作成には進みません（`strata_cli/drafting_cmd.py:21-22,81-102`; `strata_control/drafting_fetch.py:32-43`）。
- `--config` のファイルが読めない、または JSON として解釈できない場合、例外は握りつぶされ空設定として続行します。この場合、ファイルの設定に基づく split 予測や mode 選択は行われません（`strata_cli/drafting_cmd.py:54-60`）。

## 出力とエラー

正常な plan は終了コード `0` です。`--no-split` に固有のエラー経路は確認できませんでした（`strata_cli/drafting_cmd.py:88-102`）。値を付けるなど parser が受理しない引数は CLI の引数エラーとなり、未知引数経路では `ap.error` が呼ばれます（`strata_cli/cli.py:2241-2248`）。

## 根拠

- 索引の配置・scope: `docs/cli/README.md:414-424`（`strata drafting plan` の予定リンクと `--no-split`）。
- parser 宣言・共有範囲: `strata_cli/drafting_cmd.py:18-32`。
- split 判定の除外、mode の選択、plan 出力: `strata_cli/drafting_cmd.py:39-102`。
- Auto の drafter 判定と pack 要否: `strata_control/drafting.py:653-691,712-722`。
- split engine 起動予測と失敗時の扱い: `strata_control/split_engine.py:398-431`。
- 調査対象 revision: `git rev-parse HEAD` は `ffa80d73133ea5c548aefe57889a16e8085a938f`、`git status --short --branch` は `## main...origin/main`（変更表示なし）。

実機の GPU/backend ごとに split 起動予測がどうなるかは実行環境に依存します。この調査では CLI を実行せず、ハードウェア別の実測・予測結果は確認していません。
