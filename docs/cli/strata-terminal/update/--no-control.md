# `--no-control`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--no-control` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

通常の更新処理から Strata Control バンドルの更新を除外します。エンジン更新は別の `--no-engine` で制御されます。この文書のコマンド階層は [`docs/cli/README.md`](../../README.md) の索引に基づきます。

## 使い方

```sh
strata update --no-control
```

## 値と既定値

値は不要です。指定しない場合は `False` となり、Control 更新を行う既定動作です。`argparse` の `store_true` で定義されているため、値を付ける形式ではありません。トップレベル `update` と `components update` の双方に同じ定義がありますが、この文書は `strata update` のスコープです（`strata_cli/update_cmd.py:42-56`）。

## 実行時の動作

通常更新では CLI が `control=not a.no_control` を更新処理へ渡します。`run_update` は feed を一度開いて保存した後、要求されたコンポーネントのステップを順に実行します。`control=False` なら Control のステップは列に加わらず、Control の更新判定、ダウンロード、展開、テスト起動、`active.json` の切り替えはこの実行では行われません。既定ではエンジンと Control の両ステップが有効で、`--no-engine` はエンジンだけを除外します（`strata_cli/update_cmd.py:42-49, 210-224`、`strata_control/updater.py:1274-1297`）。

このフラグは更新 feed 自体を省略しません。feed の読み込みはステップ一覧を作る前に行われます。また、`--check` を併用すると `run_update` ではなく `updater.check` に進み、レポートには Control の判定も含まれます。このため `--no-control` はチェック結果から Control を隠す指定ではありません（`strata_cli/update_cmd.py:197-213`、`strata_control/updater.py:624-640`）。

## 適用条件と副作用

`strata update` で通常の更新を実行する経路に適用されます。Control の有無や更新可否にかかわらず、フラグを付けたときは Control 更新ステップ自体を実行しません。エンジンや `--app` で指定したアプリインストーラーのステップには影響しません。Control を更新する場合の実装は、新しいバンドルをステージングして `--version` で試験し、成功後に active pointer を切り替えますが、このフラグでその処理を除外できます（`strata_control/updater.py:1145-1192, 1281-1285`）。

フラグを付けても更新全体の feed 取得・署名検証、ロック取得、エンジンなど残りの有効ステップは続きます。feed 等で失敗すれば引き続きエラーになります。`--check` は feed の読み取りを行い、更新用パッケージのダウンロードはしません（`strata_control/updater.py:624-632, 1277-1285`）。

## 出力とエラー

Control を除外すると、更新結果には Control の結果行または結果オブジェクトが追加されません。人間向け出力は実行された結果だけを表示し、JSON 系出力も `run_update` が返す結果配列を出力します（`strata_control/updater.py:1283-1297`、`strata_cli/update_cmd.py:213-224`）。

このフラグは feed 読み込みなどの前提処理を無効にしません。更新エラー・feed エラー・署名エラー・取得拒否は通常どおりエラーとして出力されます。Control ステップを除外するため、そのステップ固有のダウンロードや試験起動の失敗は発生しませんが、他の選択されたステップの失敗は結果・終了コードに反映されます（`strata_cli/update_cmd.py:167-172, 225-234`、`strata_control/updater.py:1287-1297`）。

## 根拠

- `strata_cli/update_cmd.py:42-49` — `strata update` parser における `--no-control` の値なし `store_true` 定義。
- `strata_cli/update_cmd.py:197-224` — `--check` 分岐と `run_update` への引数転送、人間向け・機械向け出力。
- `strata_cli/update_cmd.py:225-234` — UpdateError、FeedError、署名エラー、取得拒否、中断の失敗経路。
- `strata_control/updater.py:624-640` — チェック結果に Control を含める処理。
- `strata_control/updater.py:1145-1192` — Control 更新時の判定、ダウンロード、試験起動、切り替え処理。
- `strata_control/updater.py:1274-1297` — feed の読込後に有効な更新ステップのみ実行し、結果と終了コードを返す処理。
- `packaging/UPDATES.md:82-91` — 利用者向けコマンド表記と更新の補足資料。実行時の意味は上記ソースを根拠とした。

調査範囲は上記 checkout の CLI parser と Python 更新実装、および同 revision の `packaging/UPDATES.md` です。Release 配布物の挙動は個別に照合していません。
