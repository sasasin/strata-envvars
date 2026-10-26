# `--json`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `false` |

## 役割

人が読む進捗・結果表示の代わりに、処理結果やエラーを JSON で出力します。JSON モードでは処理中の phase 進捗は表示されません。parser が `--json` を追加する対象には `install-file` が含まれます（`strata_cli/cli.py:508-515`）。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --json
```

`file` はローカルの engine package の位置引数です。`--json` は値を付けずに指定します（`strata_cli/update_cmd.py:57-62`）。

## 値と既定値

`action="store_true"` のフラグなので、未指定時は無効、指定時は有効です。CLI 起動時に `--json` が有効なら `--output json` に置き換わります。したがって `--json --output human` でも JSON になります。一方、`--json --output jsonl` は one-shot 出力との併用として拒否され、終了コード 2 でエラー JSON が返ります（`strata_cli/cli.py:513`, `2217-2237`）。`--output` 自体は `human`（既定）、`json`、`jsonl` を受け付けます（`strata_cli/update_cmd.py:30-40`）。

## 実行時の動作

`strata components install-file` は共通 update parser の一つで、`strata_cli/cli.py` から `update_cmd.run()` へ委譲されます（`strata_cli/update_cmd.py:42-62`, `strata_cli/cli.py:2133-2137`）。`--json` により `a.output` が `json` となり、install-file の成功時は `{"schema_version":1,"ok":true,...}` と処理結果を標準出力へ出します（`strata_cli/update_cmd.py:174-176,208-217`）。

このフラグはインストールの選択や検証条件を変えません。対象ファイルを展開し、マニフェストと署名・全ファイルを検証し、PC に適合することを確認した後、通常の test-start と切替処理を行います。ローカルファイル経路なので feed やネットワークを使わず、選択した package ファイルは残します（`strata_control/updater.py:1088-1091,1092-1145`）。成功時には engine の active/previous 状態や履歴を更新し、旧 engine を含む不要分を prune する場合があります。選択した archive はこの経路で削除されません（`strata_control/updater.py:1056-1074`, archive の削除は `delete_archive` が真の場合のみ）。

JSON モードでは `_emit_factory` が phase/progress を標準出力へ流さず、完了時の結果 JSON を出します（`strata_cli/update_cmd.py:65-87,208-217`）。実行中 engine がある場合、機械可読モードでは対話的な待機確認を行わず、`--wait` がなければ処理側の busy 判定に進みます（`strata_cli/update_cmd.py:193-195,258-273`; `strata_control/updater.py:306-317`）。`--wait SECONDS` を同時指定すると、その時間を上限に idle を待ちます。

## 適用条件と副作用

`--json` は `install-file` の one-shot 実行時に有効です。CLI の parser が `--json` を受理しても、指定位置が認識されない場合は通常の引数エラーになります（`strata_cli/cli.py:508-515,2223-2235`）。

無効な形式、読めない archive、不正な engine package、署名・ファイル検証の失敗、PC 非適合などはインストールを拒否します。既により新しい engine があり `--force` がない場合は変更せず `status: current` の結果を返します（`strata_control/updater.py:1080-1085,1092-1132,1137-1145`）。成功時の test-start、切替、状態記録、旧版保持・prune は `--json` の有無にかかわらず起きます（`strata_control/updater.py:994-1077`）。

## 出力とエラー

成功時は標準出力に単一の JSON 結果を出し、終了コード 0 です。処理中の人向け progress 行は出ません（`strata_cli/update_cmd.py:65-87,208-217`）。

`UpdateError` は標準出力に `schema_version`、`ok: false`、`error.code`、`error.message` を含む JSON を出し、同じ `error.code` を終了コードとして返します。busy は終了コード 7、package の形式・署名・適合性拒否は通常 5 です（`strata_cli/update_cmd.py:178-183,246-247`; `strata_control/updater.py:60-80,1080-1085,1112-1132`）。ファイルシステムの `OSError` は CLI 共通処理で JSON エラーとなり、終了コード 6 です（`strata_cli/cli.py:2176-2183`）。JSON 出力であっても、引数 parser 自体の不正引数エラーは argparse の usage/error 表示経路です（`strata_cli/cli.py:2223-2235`）。

## 根拠

- `strata_cli/update_cmd.py:30-40,42-62` — 共通 parser と install-file の位置引数。
- `strata_cli/cli.py:508-515,2217-2237` — `--json` の追加、`--output json` への正規化、`jsonl` 併用拒否。
- `strata_cli/cli.py:2133-2137` — update command handler への委譲。
- `strata_cli/update_cmd.py:65-87,174-217,246-255,258-273` — JSON 出力、進捗抑制、失敗・待機経路。
- `strata_control/updater.py:1080-1148,994-1077` — archive 検証、install-file の副作用、test-start と engine 切替。
