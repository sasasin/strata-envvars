# `--track`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--track` |
| 別名 | なし |
| 値 | `default` または `custom` |
| 既定値 | `custom` |

## 役割

standard benchmark のレポートに、実行者が設定を「未変更の既定設定」と申告するか、「カスタム設定」と申告するかを記録します。これは実行者の申告であり、runner が設定内容を調べて `default` であることを判定するものではありません。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8080 --track default --track-notes "release の setup-generated settings"
```

この例は既に起動しているローカル Strata server に接続する standard suite の呼び出しです。`--track-notes` には default track なら release と setup の選択、custom track なら変更内容を記録します。`--url` の代わりに `--profile NAME` を指定できます（`--profile` と `--url` は排他的です）。benchmark は固定 workload のリクエストを server に送り、結果ディレクトリへレポートを作成します。

## 値と既定値

- parser は `default` と `custom` のみを受理し、省略時は `custom` です。大文字小文字を変えた値や他の値は選択肢外です。
- 同じオプションを複数回指定した場合、`argparse` の通常の `store` action により最後に指定した値が使われます。
- `default` を指定しても設定が未変更かどうかは検査されません。protocol 文書も、runner は untouched setup を判定できず、`default` は実行者の申告として扱うと説明しています。
- `--track-notes` を省略、または空文字で指定した場合、結果には `no notes given by the operator` が記録されます。

## 実行時の動作

`--suite standard-v1`（既定）では、CLI は `--track` を宣言情報に入れ、`bench_standard.run()` に渡します。report の `configuration.track` に保存され、テキストレポートにも表示されます。値によって workload、sampling、server の起動設定を切り替える処理はありません。`--track-notes` も同じ configuration block の `track_notes` として保存されます。

このオプションは standard suite 用の argument group に定義されていますが、parser 上は別の suite と一緒に指定すること自体は拒否されません。standard 以外の suite では `_bench()` が別の serving benchmark 実装へ進み、`a.track` を参照しないため、この指定は結果に反映されません。

## 適用条件と副作用

- standard suite でのみレポートの track ラベルとして適用されます。server や profile の実効設定を変更せず、track の申告だけを記録します。
- このオプション自体に固有のファイル・ネットワーク・プロセス副作用はありません。ただし `strata bench run` 全体は benchmark リクエストを送信し、新しい結果ディレクトリへ結果を保存します。profile の server が応答しない場合は engine を起動して測定後に停止する経路もあります。
- `--track` と設定内容が一致するかの照合はありません。実際の設定と異なる申告を避けるため、track と notes は実行者が確認して指定してください。

## 出力とエラー

- standard suite の JSON 結果では `configuration.track` に、Markdown / 人間向けレポートでは `Track` 欄に値が記録されます。benchmark 自体が出力する通常の実行結果とレポートパスは `--output` の形式に従います。
- 選択肢外の値は `argparse` の choices validation で拒否されます。通常のCLI usage error となり、benchmark は開始されません。
- `bench_standard.run()` に渡る値にも `default` / `custom` の検査があり、不正値なら `ProfileError`（終了コード 2）になります。通常のCLI parser 経由では choices 検査で先に拒否されます。
- report の既存データを読み込む際も、`configuration.track` がこの2値以外なら report validation に失敗します。

## 根拠

- `strata_cli/cli.py:315-325` — standard suite の parser group と `--track` の choices・既定値・説明、`--track-notes`。
- `strata_cli/cli.py:1183-1189` — `standard-v1` の場合だけ `_bench_standard()` に分岐する箇所。
- `strata_cli/cli.py:1237-1248` — standard suite が固定 workload を使うこと、および非対応の serving-suite options の拒否。
- `strata_cli/cli.py:1274-1278` — `track` と `track_notes` を宣言情報に格納する箇所。
- `strata_cli/cli.py:1292-1305` — profile の既存 server 利用または engine 起動と benchmark 実行への引き渡し。
- `strata_cli/bench_standard.py:773-775` — 既定の宣言値と `default` / `custom` の検査。
- `strata_cli/bench_facts.py:504-509` — `configuration.track` と `configuration.track_notes` の結果への格納。
- `strata_cli/bench_standard.py:1004-1009` — 保存 report を読み込む際の track 値検証。
- `strata_cli/bench_standard.py:1188-1195` — 人間向けレポートの Track 表示。
- `docs/BENCHMARK_PROTOCOL.md:37-51,205-206` — protocol の profile / URL 実行例、track の申告としての説明、その他の実行者申告項目。
