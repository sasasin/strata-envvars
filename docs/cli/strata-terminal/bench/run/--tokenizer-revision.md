# `--tokenizer-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--tokenizer-revision` |
| 別名 | なし |
| 値 | `REV`。値を1つ取る文字列 |

## 役割

`standard-v1` ベンチマークの結果に、利用者が把握している tokenizer の revision を申告し、モデルの provenance metadata として記録します。Strata が tokenizer の実体や revision を照会・検証する機能ではありません。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8080 --tokenizer-revision REV
```

これは既に稼働している Strata server に対して標準ベンチマークを実行する例です。`strata bench run` は `--profile` または `--url` の一方を必須とし、`--suite` の既定値は `standard-v1` です（`strata_cli/cli.py:291-300`）。

## 値と既定値

- 値は `argparse` の通常の文字列引数です。`REV` の形式、長さ、参照先の存在を検証する処理は確認できません（`strata_cli/cli.py:326-329`）。
- 省略時の値は `None` です。引数を指定したときは値が `a.tokenizer_revision` に入り、明示的な空文字列 `""` には個別の拒否処理がありません（`strata_cli/cli.py:328,1274-1278`）。
- 同じ引数を複数回指定した場合は `argparse` の単一値引数として最後の値が残ります。専用の重複指定処理はありません（`strata_cli/cli.py:328`）。

## 実行時の動作

`--suite standard-v1` では CLI が値を `declared` 辞書に載せ、標準ベンチマーク実行関数に渡します（`strata_cli/cli.py:1183-1187,1274-1278,1302-1305`）。レポート組み立て時に `strata_cli/bench_facts.py` がこの値を `model.tokenizer_revision` にそのまま転記します。省略されて `None` の場合は `/model/tokenizer_revision` を `missing` に追加し、理由を `not given: pass --tokenizer-revision` とします（`strata_cli/bench_facts.py:422-442`）。結果の `model` ブロックには `tokenizer_revision` が必須フィールドとして含まれます（`strata_cli/bench_standard.py:818,928-940,999-1003`）。

この値は報告用メタデータであり、tokenizer のロード、モデル設定、リクエスト内容を変更しません。CLI から値を渡すだけで tokenizer revision が正しいことを保証したり、実行中 server の tokenizer と一致するか確かめたりはしません（`strata_cli/cli.py:1274-1278`; `strata_cli/bench_facts.py:422-442`）。

`--suite serving-smoke` や `parallel-*` では `_bench_standard` を経由せず、別の `bench.run` に実行設定を渡します。その呼び出しに `tokenizer_revision` は含まれないため、parser は引数を受理しますが、これらの suite の結果には反映されません（`strata_cli/cli.py:1183-1189,1219-1225`）。

## 適用条件と副作用

- 値が使われるのは `standard-v1` の結果作成経路です。`standard-v1` は既定の suite です（`strata_cli/cli.py:297-300,1183-1187`）。
- 標準ベンチマークの `results.json` と生成される `README.md` に記録される metadata の一部です。ベンチマーク結果は新しい出力ディレクトリに保存され、`--out` を省略すると `./bench/results` または `./bench-results` 配下が出力先になります（`strata_cli/cli.py:1279-1281`; `strata_cli/bench_standard.py:771-780,834-840,958-960`）。
- このフラグ自体はファイルや server を変更しませんが、ベンチマーク全体は server に接続して計測リクエストを送り、結果ファイルを作成します（`strata_cli/bench_standard.py:781-790,840-860,958-960`）。

## 出力とエラー

- revision の書式・妥当性に関する専用エラーはありません。値を省略してオプションだけを書くと、`argparse` が必須引数不足として usage とエラーを出し、終了コード 2 になります（parser 定義 `strata_cli/cli.py:328`、引数解析 `strata_cli/cli.py:2223-2231`）。
- revision の値が未指定ならベンチマークは続行し、`results.json` の `missing` に未申告理由を記録します（`strata_cli/bench_facts.py:433-442`）。
- server が応答しない、モデル未ロード、または `/props` が取得できない場合などは標準ベンチマーク自体が失敗します。これらは tokenizer revision の値に固有の失敗ではありません（`strata_cli/bench_standard.py:781-790`）。

## 根拠

- `strata_cli/cli.py:291-300,315-334` — `bench run` の parser、suite の既定値、`--tokenizer-revision` の引数定義。
- `strata_cli/cli.py:1183-1189,1274-1281,1302-1305` — suite による分岐、値を標準 suite の metadata に渡す処理、出力先。
- `strata_cli/bench_facts.py:422-442` — metadata への転記と、未指定時の理由。
- `strata_cli/bench_standard.py:771-790,818-823,928-960,999-1003` — 標準レポート構築、保存、`model.tokenizer_revision` フィールド。
- `strata_cli/cli.py:2223-2231` — parser の引数不足・未認識引数のエラー処理。
