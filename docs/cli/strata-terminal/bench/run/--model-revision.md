# `--model-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--model-revision` |
| 別名 | なし |
| 値 | `REV`。量子化モデルの配布リポジトリにおける immutable revision を表す文字列 |

## 役割

ベンチマーク対象の量子化モデルを取得したリポジトリ revision を、実行者が結果に申告します。推論エンジンから読み取れない来歴情報を記録するための項目です。Strata は revision を自動取得せず、指定値をベンチマーク結果の `model.revision` に記録します。

## 使い方

ローカルの `127.0.0.1:8080` ですでに稼働しているサーバーに標準ベンチマークを実行する例です。`REVISION_SHA` は対象の量子化リポジトリの immutable revision に置き換えてください。

```sh
strata bench run --url http://127.0.0.1:8080 --model-revision REVISION_SHA
```

この例では `--suite` を省略するため、既定の `standard-v1` が実行されます。出力先は作業ディレクトリに `bench/results/` があればその配下、なければ `./bench-results/` です。

## 値と既定値

- `REV` は1つの文字列引数です。parser に `type`、`choices`、必須指定、形式・長さの validation はなく、プロジェクト独自の revision 書式検証もありません。immutable revision を指定することは help と説明文上の要件であり、値が実際に immutable かは検査されません。
- 省略時の値は `None` です。空文字列を明示した場合も空文字列のまま渡され、`None` としては扱われません。
- 別名はありません。複数回指定した場合の専用処理もありません。

## 実行時の動作

`strata bench run` の標準 suite（`standard-v1`）では、CLI handler が parser の値を `declared["model_revision"]` としてベンチマーク runner に渡します。runner はその値を `model.revision` に設定します。これは実行者の申告値であり、サーバー上のモデルやファイルを選択・切り替えたり、リポジトリへ接続したりする指定ではありません。

値を省略すると `model.revision` は `null` になり、`missing` に `/model/revision` と「量子化リポジトリの immutable revision はエンジンから読めないため `--model-revision` を指定する」という理由が記録されます。明示値がある場合、runner は `None` かどうかだけを見てこの理由を追加しません。

このオプションは `standard-v1` のみで利用されます。parser では `strata bench run` の共通 parser に登録されているため他の serving suite でも引数として受理されますが、分岐先の処理は `model_revision` を参照せず、結果への記録効果はありません。`--skip-model-hash` はモデルファイルのハッシュ取得を制御しますが、この申告 revision の記録とは別です。

## 適用条件と副作用

この値自体にネットワークアクセス、モデル取得、サーバー設定変更の副作用はありません。標準ベンチマーク全体はサーバーへ要求を送り、`--profile` でサーバーが未稼働の場合は engine を起動して終了後に停止しますが、その条件は `--model-revision` ではなく実行方式によります。

成功した標準ベンチマークでは、値は `results.json` の `model.revision` と、生成される `README.md` のモデル来歴表示に含まれます。標準結果は新しい出力ディレクトリへ書かれます。revision 値に固有の拒否・警告・終了コードは確認できません。ベンチマーク自体の失敗時は一般の実行エラー経路に従います。

## 出力とエラー

- 省略時: `results.json` の `model.revision` が `null` になり、`missing["/model/revision"]` に理由が入ります。
- 指定時: 文字列が `model.revision` に記録されます。値の書式や実在性は検証されません。
- このオプション固有のエラー経路はありません。標準 suite に関する他の引数検証や結果の書き込み・検証エラーは別途発生し得ます。

## 根拠

- parser 定義と値の説明: `strata_cli/cli.py:326`。
- `standard-v1` と他 serving suite の分岐: `strata_cli/cli.py:1183-1189`。
- 値を `declared` に渡す箇所: `strata_cli/cli.py:1274-1278`、runner 呼び出し: `strata_cli/cli.py:1302-1305`。
- 結果の `model.revision` 設定、未指定時の理由: `strata_cli/bench_facts.py:422-441`。
- 結果の missing 集約と `results.json` / `README.md` の書き出し: `strata_cli/bench_standard.py:953-960`。
- 生成 `README.md` で revision を表示する箇所: `strata_cli/bench_standard.py:1188-1191`。
- Protocol がこの値を実行者申告情報として扱い、省略時は `null` と理由を付ける説明: `docs/BENCHMARK_PROTOCOL.md:49-51`。
- テストで指定値が結果の `model.revision` に保存されることを確認する箇所: `tests/terminal/test_bench_standard.py:831-838`。

調査は上記 commit の parser と実装を対象に行いました。CLI の実行、build、性能測定、テストは行っていません。
