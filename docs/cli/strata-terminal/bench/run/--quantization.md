# `--quantization`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--quantization` |
| 別名 | なし |
| 値 | `NAME`。量子化名を表す任意の文字列 |

## 役割

標準ベンチマーク `standard-v1` の結果に記録するモデル量子化名を指定します。モデルの量子化やサーバー設定を変更するオプションではありません。ファイル名やサーバーが報告するモデル名から量子化名を読み取れないとき、結果に記録する値を手動で補います。

## 使い方

```sh
strata bench run --profile my-profile --quantization Q4_K_M
```

`--profile` と `--url` はどちらか一方が必須です。`--suite` の既定値は `standard-v1` です（`strata_cli/cli.py:293-300`）。

## 値と既定値

`argparse` の通常の文字列引数として定義され、値の選択肢、形式、範囲を検査するコードはありません。省略時の値は `None` です。同じオプションを複数指定した場合の特別な処理もなく、Python `argparse` の通常の単一値引数として最後の指定値が残ります（`strata_cli/cli.py:326-330`）。

空文字列は parser では受理されますが、実行時に `declared.get("quantization") or ...` と評価されるため、未指定と同じく自動推定に進みます。空でない明示値は大文字小文字を変換せず結果に記録されます（`strata_cli/bench_facts.py:428-432`）。

## 実行時の動作

`standard-v1` の場合、CLI は値を `declared` に入れて標準ベンチマークへ渡し、結果のモデル情報を組み立てる処理がその値を優先します（`strata_cli/cli.py:1183-1187, 1274-1278, 1302-1305`; `strata_cli/bench_standard.py:818`; `strata_cli/bench_facts.py:422-432`）。

空でない明示値がなければ、推定処理は検出対象のモデルファイル名を順に調べ、その後にサーバーの `model_alias`（なければ `/v1/status` の `model`）を調べます。現在の正規表現は、区切り文字 `-`、`_`、`.` の間にある `Q4_K_M`、`IQ...`、`BF16`、`F16`、`NVFP4` などのパターンを認識し、検出値を大文字化します（`strata_cli/bench_facts.py:389, 414-419, 422-428`）。

値はベンチマーク結果の `model.quantization` と Markdown レポートに表示される量子化名の記録にだけ使われます。指定値からリクエスト内容、実行エンジン、モデルファイルを切り替える処理はありません（`strata_cli/bench_facts.py:428-432`; `strata_cli/bench_standard.py:928-940, 1188-1191`）。

## 適用条件と副作用

この値が利用されるのは `--suite standard-v1` の経路です。`--suite` を `serving-smoke` や `parallel-*` にすると、CLI は別の serving suite 実行へ分岐し、そこでは `--quantization` を渡したり参照したりしません。そのため parser は受け付けますが、これらの suite の結果には反映されません（`strata_cli/cli.py:297-300, 1186-1205`）。

`--skip-model-hash` を併用するとローカルモデルファイル一覧を空にしてハッシュを省きますが、量子化名の推定はサーバー報告名から続行します。明示値があればそれが優先されます（`strata_cli/bench_standard.py:807-818`; `strata_cli/bench_facts.py:422-428`）。ベンチマークはモデル量子化を変更せず、通常の標準ベンチマーク実行と同様にレポートを新規作成します。

## 出力とエラー

明示値がなく、自動推定でも見つからない場合、`model.quantization` は `null` になり、`missing` に `/model/quantization` と理由が記録されます（`strata_cli/bench_facts.py:428-441`; `strata_cli/bench_standard.py:953-960`）。このオプション固有の値検証エラー経路はありません。標準ベンチマークの結果は `results.json` と `README.md` に新規作成されます（`strata_cli/bench_standard.py:958-960`）。

## 根拠

- parser 定義と値: `strata_cli/cli.py:326-330`
- 標準 suite への分岐、値の受け渡し: `strata_cli/cli.py:1183-1187, 1274-1278, 1302-1305`
- parser から結果のモデル欄への値選択・自動推定: `strata_cli/bench_facts.py:389, 414-441`
- ファイル名ハッシュを省く場合の files の扱いと model 欄の生成: `strata_cli/bench_standard.py:807-818`
- 結果ファイルの書き込みと Markdown レポートでの表示: `strata_cli/bench_standard.py:928-960, 1188-1191`

調査範囲は上記 commit の Terminal CLI と標準ベンチマーク実装です。Release 配布物や異なる revision の動作は照合していません。
