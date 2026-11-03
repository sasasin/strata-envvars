# `--feed`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列 1 個。共通 parser の help は URL またはフォルダーを案内するが、このコマンドでは値を使用しない |

## 役割

このコマンドでは `--feed` は parser に受理されますが、一覧表示に影響しません。導入済み engine の一覧取得はローカルの component folder を読み取る処理で、feed の取得・変更は行いません。

## 使い方

```sh
strata components engines --feed ./feed.json
```

この例の `--feed` 値は受理されますが無視されます。engine 一覧の JSON 出力を選ぶ場合は、別 option の `--json` または `--output json` を指定します。

## 値と既定値

`strata_cli/update_cmd.py` の `_common()` は `--feed` を `default=None` の文字列 option として登録します。値の URL・パス検証や空文字列の検査はこの parser 定義にはありません。値を省略すると parser 上の値は `None` です。値を伴わず `--feed` だけを指定した場合は argparse が usage error として扱います（終了コード 2）。

この option の共通 help 文は、署名付き update feed の場所として URL または folder を示し、既定の選択元として `STRATA_UPDATE_FEED`、前回使用した feed、プロジェクトの feed を挙げています。ただし、これらの既定選択は更新処理の `_feed_source()` が行うものであり、`engines` 分岐では呼ばれません。

## 実行時の動作

`strata components engines` の parser は `_common()` を呼ぶため `--feed` を受理します。共通 parser の `--output` は `human` が既定で、`--json` は `--output json` の alias として後付けされます。

実行時は `update_cmd.run()` が `updater.Context` を作った後、`components_command == "engines"` を検出して `_engines_command()` に分岐します。この経路は `_feed_source()` による値解決より前に戻るため、引数 `a.feed`、`STRATA_UPDATE_FEED`、記憶済み feed、既定 feed は参照されません。`_engines_command()` は `engine_library.list_engines(ctx)` を呼び、結果を human または JSON で表示します。

## 適用条件と副作用

`--feed` の有無や値にかかわらず、一覧処理はローカルの engine 情報を読み取ります。`list_engines()` は docstring で読み取り専用・ダウンロードなしと明記し、一覧分岐もその結果を表示して終了します。この option 自体による feed へのネットワークアクセス、ファイル変更、engine 切替はありません。

## 出力とエラー

`--feed VALUE` を指定した場合、`VALUE` の内容に由来する出力やエラーはありません。値なしの `--feed` は parser の引数不足として拒否されます。feed と無関係な engine 一覧処理の障害経路は、この option の調査範囲外です。

## 根拠

- `strata_cli/update_cmd.py:47-56` — `--feed` を含む共通 option 群の parser 定義と既定値。
- `strata_cli/update_cmd.py:123-132` — feed 値・環境変数・記憶値・既定値を選ぶ `_feed_source()`。
- `strata_cli/update_cmd.py:244-256,272-273,284-288` — context 作成、engine 一覧コマンドへの先行分岐、feed source を設定する更新経路。
- `strata_cli/update_cmd.py:358-377` — `engines` 分岐と human/JSON 出力。
- `strata_cli/cli.py:508-515` — update 系 parser への `--json` / `--quiet` 後付け。
- `strata_control/engine_library.py:180-195` — engine 一覧のローカル読み取りと返却値。

