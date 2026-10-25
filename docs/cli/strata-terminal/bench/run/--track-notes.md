# `--track-notes`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--track-notes` |
| 別名 | なし |
| 値 | 任意の文字列 `TEXT`。parser に文字数・書式の制限は定義されていない |

## 役割

標準ベンチマーク結果に、実行者が申告する構成・変更内容の説明を記録します。`--track default` ならリリースや setup の選択、`--track custom` なら加えた変更の説明に使います。この値はベンチマーク条件を変更せず、結果の記録に使われます（`strata_cli/cli.py:322-325, 1274-1278`、`docs/BENCHMARK_PROTOCOL.md:49-51, 334-337`）。

## 使い方

```sh
strata bench run --profile NAME --track custom --track-notes "int8 KV と MTP を設定"
```

`--profile` の代わりに `--url URL` を使うこともできます。`strata bench run` はどちらか一方を必須とし、suite の既定値は `standard-v1` です（`strata_cli/cli.py:293-300`）。

## 値と既定値

- `TEXT` は `argparse` の通常の文字列引数です。別名、選択肢、長さ制限、独自の validation はありません（`strata_cli/cli.py:324-325`）。
- 省略時は parser の値が `None` になり、標準ベンチマークでは `no notes given by the operator` に置き換わります（`strata_cli/cli.py:324-325, 1274-1275`）。
- 空文字列を渡した場合も、`a.track_notes or ...` の処理により同じ既定文になります（`strata_cli/cli.py:1274-1275`）。
- 同じオプションを複数回指定した場合の専用処理はありません。parser は通常の `store` action を使うため、最後に指定した値が残ります（`strata_cli/cli.py:324-325`）。
- `--track` は別オプションです。既定は `custom` で、`default` または `custom` 以外は受理されません。注記自体の値に応じて `track` が自動変更されることはありません（`strata_cli/cli.py:322-325`、`strata_cli/bench_standard.py:773-775`）。

## 実行時の動作

`standard-v1` の実行経路では、CLI が `track_notes` として値を宣言データへ入れ、ベンチマーク実行関数が `configuration.track_notes` に格納します（`strata_cli/cli.py:1183-1188, 1274-1278`、`strata_cli/bench_standard.py:773-775`、`strata_cli/bench_facts.py:504-509`）。その値は `results.json` の `configuration.track_notes` と、生成される `README.md` の `Track` 行に出力されます（`strata_cli/bench_standard.py:958-960, 1192`）。標準プロトコルでは、この欄に default run の setup 選択または custom run の変更点を記録するものとしています（`docs/BENCHMARK_PROTOCOL.md:334-337`）。

このオプションは共通の `bench run` parser に登録されていますが、効果があるのは `--suite standard-v1`（既定）です。別 suite の実行経路はこの値を `bench.run` に渡さないため、`--suite serving-smoke` などでは受け付けられても記録に使われません（`strata_cli/cli.py:297-300, 1183-1188, 1221-1225`）。

注記は CLI から宣言データとしてそのまま結果へ渡され、機密情報を除去する処理はこの値に対して確認できません。結果ファイルを共有する可能性がある場合、秘密情報や公開したくない個人情報を注記へ含めないでください（`strata_cli/cli.py:1273-1278`、`strata_cli/bench_facts.py:504-509`）。

## 適用条件と副作用

このオプション自体は測定リクエスト、モデル設定、サーバー起動条件を変えません。標準ベンチマーク全体はサーバーへ接続し、結果ディレクトリに `results.json`、`README.md` 等の証跡を新規作成します。`--out` で既存のディレクトリを指定すると失敗します（`strata_cli/bench_standard.py:777-780, 839-840, 958-960`）。これらは `--track-notes` 単独の副作用ではなく、`standard-v1` の実行によるものです。

## 出力とエラー

注記固有の値検証エラーは実装されていません。値がないまま `--track-notes` を指定した場合は `argparse` の引数エラーになります。実行時の標準スイート固有エラーは通常の CLI エラー経路へ渡され、JSON 出力モードでは JSON のエラー、human モードでは stderr の `strata: ...` として出力されます（`strata_cli/cli.py:527-532, 2166-2188`）。正常終了時には human モードでレポートの場所、または JSON モードで結果パス等が出力されます（`strata_cli/cli.py:1321-1328`）。

## 根拠

- Parser 定義・値の初期値: `strata_cli/cli.py:322-325`
- standard suite への分岐と serving suite への非転送: `strata_cli/cli.py:1183-1188, 1221-1225`
- 宣言値の fallback と `standard-v1` 実行時の使用: `strata_cli/cli.py:1273-1278`
- 結果設定への格納・既定値: `strata_cli/bench_standard.py:773-775`、`strata_cli/bench_facts.py:504-509`
- JSON / Markdown レポートへの出力: `strata_cli/bench_standard.py:958-960, 1192`
- プロトコル上の説明: `docs/BENCHMARK_PROTOCOL.md:49-51, 334-337`
- エラー出力経路: `strata_cli/cli.py:527-532, 2166-2188`

