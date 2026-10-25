# `--source-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--source-revision` |
| 別名 | なし |
| 値 | `REV`。元の Qwen/Qwen3.8-Flash-Next 重みの revision を表す文字列 |

## 役割

標準ベンチマーク結果に、量子化モデルの元となった Qwen/Qwen3.8-Flash-Next 重みの revision を記録するための申告値です。Strata がサーバーやモデルファイルから取得する値ではありません。量子化リポジトリ側の revision を記録する `--model-revision` とは別の項目です（`strata_cli/cli.py:326-328`）。Benchmark Protocol も、エンジンから判別できない値は実行者が指定し、未指定なら null と理由を記録すると説明しています（`docs/BENCHMARK_PROTOCOL.md:49-51,55-59`）。

## 使い方

ローカルで稼働中のサーバーに標準ベンチマークを実行する例です。`REVISION_SHA` は元の重みの revision に置き換えてください。

```sh
strata bench run --url http://127.0.0.1:8080 --source-revision REVISION_SHA
```

`--profile` または `--url` のどちらか一方が必要です。`standard-v1` が既定 suite です（`strata_cli/cli.py:293-300`）。

## 値と既定値

- `REV` は1つの文字列引数です。parser に型変換、choices、必須指定、書式・長さの validation はありません。値が実際のモデル revision を表すか、immutable かも検査されません（`strata_cli/cli.py:327`）。
- 省略時は `None` です。空文字列を明示すると空文字列のまま保持され、未指定の `None` とは異なる値になります。複数回指定した場合の専用処理はありません。
- 値を付けずに指定した場合は argparse の引数解析エラーになります。未知引数は `parse_known_args()` 後に usage/error 経路で拒否されます（`strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`standard-v1` の処理では CLI handler が値を `declared["source_revision"]` として標準 benchmark runner に渡します（`strata_cli/cli.py:1273-1278,1302-1305`）。runner は結果の `model.source_revision` にその値を格納します。値に応じたモデル選択、ダウンロード、revision の照合は行いません（`strata_cli/bench_facts.py:422-432`）。

未指定の場合は `model.source_revision` が null となり、`missing["/model/source_revision"]` に `not given: pass --source-revision` が記録されます（`strata_cli/bench_facts.py:433-441`）。空文字列は null ではないため欠落理由は付きませんが、Markdown レポート表示では空値が未設定表示になります（`strata_cli/bench_standard.py:953-960,1188-1191`）。

このオプションは標準 suite 用として parser の option group に登録されています（`strata_cli/cli.py:315-328`）。ただし parser が `strata bench run` 共通のため、serving suite を選んだ場合も引数として受理されます。serving suite は別の実行経路に進み、`source_revision` を渡す処理がないため結果に反映されません（`strata_cli/cli.py:1183-1198`）。

## 適用条件と副作用

値そのものにネットワーク、ファイル、サーバー設定の副作用はありません。ベンチマーク全体は指定先の server に要求を送り、標準 suite の結果ディレクトリに `results.json` と `README.md` を新規作成します（`strata_cli/bench_standard.py:953-960`）。この申告値は成功した標準 suite の JSON に保存され、Markdown のモデル欄にも表示されます（`strata_cli/bench_standard.py:1188-1191`）。

## 出力とエラー

- 値を指定すると、標準 suite の `results.json` の `model.source_revision` に記録されます。値の書式に対する独自エラーや警告はありません。
- 未指定時は null と欠落理由が記録されます。Protocol ではエンジンが推測しない情報として扱われています（`docs/BENCHMARK_PROTOCOL.md:49-51`）。
- `--output json` の CLI 出力は `ok`、結果パス、status、quality、summaries 等の実行サマリーで、モデル情報そのものは結果ファイルにあります（`strata_cli/cli.py:1321-1328`）。
- 値固有の実行失敗経路は確認できません。一般のベンチマーク実行・結果検証・ファイル書き込みは失敗し得て、標準 suite の結果が complete でない場合や起動した engine の停止に失敗した場合は終了コード `6` になります（`strata_cli/cli.py:1312-1328`）。

## 根拠

- `strata_cli/cli.py:315-328` — 標準 suite option group と parser 定義。
- `strata_cli/cli.py:1183-1198` — 標準 suite と serving suite の分岐。
- `strata_cli/cli.py:1273-1278,1302-1305` — 値の `declared` への格納と runner への引き渡し。
- `strata_cli/bench_facts.py:422-441` — model block の `source_revision` と未指定時の欠落理由。
- `strata_cli/bench_standard.py:953-960,1188-1191` — null 欠落の集約、結果ファイル作成、Markdown 表示。
- `strata_cli/cli.py:1312-1328` — 結果出力と標準 suite の終了コード。
- `docs/BENCHMARK_PROTOCOL.md:49-59,315` — 実行者申告情報と model block の利用者向け定義。
- `tests/terminal/test_bench_standard.py:828-838` — 既存テストで指定値が結果 JSON の `model.source_revision` に保存されることを確認する箇所。テストは今回実行していません。

調査は上記 commit の Terminal CLI parser と標準ベンチマーク実装に限定しました。CLI 実行、build、性能測定、テストは行っていません。
