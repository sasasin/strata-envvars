# `strata bench run --background`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--background` |
| 別名 | なし |
| 値 | `TEXT`（任意の文字列、必須、複数回指定可） |
| 既定値 | 未指定時は空リストとして扱う |

## 役割

ベンチマーク中に動かしていたプログラムを利用者が申告し、その説明を標準ベンチマークのハードウェア情報に記録します。Strata は他のプログラムを列挙・検証せず、ベンチマーク実行を制御するフラグでもありません。

## 使い方

```sh
strata bench run --profile my-profile --background "ブラウザー" --background "画面録画"
```

`--profile` の代わりに `--url` で接続先を指定できます。`--background` は繰り返すたびに値を追加します。

## 値と既定値

- parser は値を `TEXT` として受け取り、`action="append"` により指定順のリストにします。型変換、選択肢、空文字を拒む独自 validation はありません。空文字を渡すと空文字要素として受理されます（`strata_cli/cli.py:331`）。
- 未指定の値 (`None`) は標準ベンチマーク用データを組み立てる時点で `[]` に置き換えられます。文字列のtrim、重複除去、プログラム名の照合は行いません（`strata_cli/cli.py:1274-1278`、`strata_cli/bench_standard.py:813-814`）。

## 実行時の動作

標準ベンチマーク (`--suite standard-v1`。既定の suite) では、値のリストを `bench_facts.hardware` に渡し、レポートの `hardware.background_workloads` に記録します。未指定なら同フィールドは `null` となり、`results.json` の `missing` に「runner は他のプログラムを調べず、`--background` で申告されたものもない」という理由が入ります（`strata_cli/cli.py:1186-1187,1274-1278`、`strata_cli/bench_standard.py:813-814,928-954`、`strata_cli/bench_facts.py:268-310`）。

値は標準ベンチマークの `results.json` に保存され、生成する `README.md` では `Background work` としてセミコロン区切りで表示されます。これは利用者の申告であり、列挙されたプログラムが実際に動作したことや、他の負荷がなかったことを保証しません（`strata_cli/bench_standard.py:935-954,1160-1187`）。

## 適用条件と副作用

- parser 上は `strata bench run` 共通で受理されますが、この値を後続処理へ渡すのは `standard-v1` 経路です。`serving-smoke` や他の serving suite では `bench.run(...)` に渡されず、記録に使われません（`strata_cli/cli.py:1183-1199,1221-1225`）。
- 値はベンチマーク負荷、同時実行数、リクエスト、GPU 選択などを変えません。プロセスの起動・停止やネットワークアクセスも行いません。ハードウェア情報の一項目として記録するだけです（`strata_cli/bench_facts.py:268-310`）。
- 標準ベンチマークのレポート出力先には `results.json` と `README.md` が新規作成されます。出力ディレクトリは既存のものを受け付けず、既存ファイルを上書きしない実装です（`strata_cli/bench_standard.py:835-840,958-960`、`strata_cli/bench.py:668-676`）。

## 出力とエラー

このオプション単独に固有の値検証エラーはありません。標準 suite の実行が成立すれば、申告内容は `results.json` と Markdown の `README.md` に含まれます。標準 suite のレポートが自己検証に失敗した場合は `ProfileError`（終了コード 6）になり、出力先を作れない場合などの実行時エラーも別途発生し得ます（`strata_cli/bench_standard.py:955-960`）。

## 根拠

- `strata_cli/cli.py:291-334` — `bench run` parser、suite と標準 suite 用 option のスコープ、`--background` の宣言。
- `strata_cli/cli.py:1183-1199,1274-1278` — suite の分岐、標準 suite の申告データ組み立て。
- `strata_cli/bench_standard.py:813-814,928-954` — hardware 情報への格納、結果 JSON と未取得理由の作成。
- `strata_cli/bench_facts.py:268-310` — ハードウェア情報の作成と未申告時の理由。runner は他のプログラムを調査しない。
- `strata_cli/bench_standard.py:1160-1187` — Markdown レポートでの表示。
- `strata_cli/bench_standard.py:835-840,955-960`、`strata_cli/bench.py:668-676` — 出力ディレクトリと結果ファイルの新規作成。

調査範囲は上記 commit の checkout に含まれる Terminal CLI の parser と標準ベンチマーク実装です。同一 revision の CLI `--help` や Release 配布物との照合は行っていません。serving suite でこの値が利用されないことは、該当経路から `background` が転送されないソース構造に基づく判断です。
