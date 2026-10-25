# `strata ops plan --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| オプション | `--output` |
| 別名 | `--json`（同じ one-shot parser に追加される JSON 出力ショートカット） |
| 値 | `human` または `json`。既定値は `human` |

## 役割

レシピの実行計画を人間向け既定形式または機械処理向け JSON envelope で出力します。このオプションは計画の対象や検査内容を変えず、出力形式を選びます。

## 使い方

```sh
strata ops plan restart --profile four-gpu --output json
```

`NAME` はレシピ名、`--profile PROFILE` は必須です。`--output` を省略すると `human` になります。

## 値と既定値

- parser は `choices=("human", "json")`、`default="human"` として定義されています。大文字小文字やその他の値は受理されません。
- `--json` は `ops` 配下の one-shot parser に共通追加されるフラグです。`main()` が `--json` 指定時に `output` を `json` に設定します。`--output json` と同じ形式になります。
- 複数回指定した場合の専用処理はありません。通常の argparse の値処理となり、同じ option の後の値が最終値です。

## 実行時の動作

`_ops()` は `output == "json"` かどうかで機械形式を選び、いずれの場合も `recipes.plan(profile, name)` を呼びます。`json` では `schema_version: 1`、`ok`、`plan` を含む1行 JSON を stdout に出します。`human` では「人間向けの文章」ではなく、計画 dict をインデント付き JSON として stdout に出します。

計画生成はレシピ種別ごとに異なります。`runtime.restart` は runtime の restart preflight と実行時効果を含み、`engine.calibrate.measure` は calibration preview と測定時の効果を含みます。その他の `components.verify` はコンポーネント検査結果を含みます。返却 plan は `would_execute: false` を示します。レシピはロードされ、プロファイル revision との整合性も確認されます。revision が preview 中に変わると失敗します。

`--quiet` は成功時の既定 human 出力を抑えますが、`--output json`（または `--json`）では JSON 出力が維持されます。human mode の失敗時に捕捉した出力があれば stderr に出されます。

## 適用条件と副作用

このオプションは `strata ops plan` parser に適用され、必須の `--profile` とレシピ名を使う plan 処理の結果形式を選びます。plan branch は `recipes.run()` ではなく `recipes.plan()` を呼び、計画の実行やレシピ変更は行いません。

ただし preview は単なる保存データの整形ではありません。restart recipe では runtime preflight RPC を行い、calibration recipe では calibration preview を行います。components recipe はプロファイルを解決してコンポーネントを検査し、recipe の `live` 設定が有効ならホスト GPU 情報も照会します。従って確認対象の種別や `live` 設定に応じて、ローカル状態の読み取りやホスト照会が発生します。

## 出力とエラー

- 有効な計画なら終了コード `0`。preflight の `ok` が false の場合も plan は出力され、`operation.exit_code`（省略時 `5`）を終了コードとして返します。
- `--output` に許可されていない値を渡すと argparse が usage/error を出し、終了コード `2` で終了します。
- profile/recipe 読み込み等で捕捉対象の例外が発生した場合、`output=json` では `{schema_version, ok:false, error:{code,message}}` の JSON を stdout に出し、human mode では `strata: ...` を stderr に出します。終了コードは例外の `exit_code`（なければ `ValueError` は `2`、`OSError` は `6`）です。

## 根拠

- `strata_cli/cli.py:255-267` — `ops plan` を含むサブコマンド生成と、必須 `--profile`、`--output` の choices/default。
- `strata_cli/cli.py:508-515` — ops one-shot parser への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:1391-1447` — plan 分岐、JSON/human の具体的な出力、plan 判定と終了コード。
- `strata_cli/cli.py:2166-2183` — ValueError/OSError の出力と終了コード処理。
- `strata_cli/cli.py:2217-2248` — `--json` を `output=json` に変換する処理と quiet の適用条件。
- `strata_control/recipes.py:329-360` — recipe kind ごとの preview、効果記述、`would_execute: false`、revision check。
- `strata_control/runtime.py:734-740` — restart plan が runtime preflight RPC を呼ぶ実装。
- `strata_control/calibration.py:95-111` — calibration preview が計測・設定書き込みを行わず preflight 情報を返す実装。

調査範囲は上記 commit の checkout 内にある Terminal CLI parser と plan 実装です。Release 配布物や各 OS での実行結果は照合していません。
