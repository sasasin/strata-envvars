# `strata components rollback`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の状態は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/updater.py` |

## 役割

直前の `strata update` が保持したローカルの engine に戻し、以後の起動でその engine が選ばれるようにします。feed やネットワークから何かをダウンロードする操作ではなく、保存状態の `engine.previous` が指す engine の manifest と全ファイルを検証したうえで、engine 選択状態を切り替えます（`strata_control/updater.py:1033-1078`）。

この操作は推論サーバーを起動・停止しません。engine が使用中なら、停止を待つか busy として終了します。利用者向けインストール手順でも更新後の復帰方法として案内されています（`docs/INSTALL.md:114-116`）。

## 基本的な使い方

```sh
# 直前の更新で保持された engine に戻す
strata components rollback

# engine の終了を最大120秒待ってから戻す
strata components rollback --wait 120

# スクリプト向けに JSON で結果を受け取る
strata components rollback --json
```

戻せる前バージョンが存在しない場合は終了コード 2 で失敗します。rollback を繰り返し、現在すでに前バージョンが選択されている場合も、さらに古い版を探す操作ではなく同じく終了コード 2 です（`strata_control/updater.py:1036-1054`）。

## 実行モード

このコマンドは parser 上、位置引数なしの一回実行コマンドです。`strata_cli/update_cmd.py:57-59` で rollback を `components` の下に登録し、共通オプションを付けています。個別の plan / apply モードはありません。

- **通常実行:** 前バージョンをローカル検証し、pin と active / previous 状態、更新履歴を保存します。成功しても稼働中プロセスを切り替えず、次回起動時に pin が効きます（`strata_control/engine_component.py:62-64`、`strata_control/updater.py:1055-1078`）。
- **待機付き実行:** `--wait SECONDS` を指定すると、稼働中 engine が終了するまで指定時間待ちます。待機期限までに idle にならない場合は busy の失敗です。省略時は対話端末では通常の Strata server に対する待機確認を表示し、機械出力または非対話環境では確認せず busy として扱います（`strata_cli/update_cmd.py:237-252`、`strata_control/updater.py:300-309`）。Strata の `launch` が稼働中の場合は対話確認をせず、`strata launch --stop` を案内する busy 経路です（同: `246-249`、`strata_control/updater.py:65-75`）。
- **機械可読出力:** `--json` は `--output json` の alias、`--output jsonl` も parser で受理されます。rollback の成功分岐はどちらの machine 出力でも JSON object を一行出力します（`strata_cli/cli.py:508-515,2232-2235`、`strata_cli/update_cmd.py:188-195`）。

## 主な動作と副作用

1. `strata_cli/update_cmd.py:174-188` で components directory と hardware 情報から context を作り、rollback の分岐で serving 状態の確認と `updater.rollback_engine()` を呼びます。feed の選択・取得を行う通常の update 経路には進みません。
2. updater の排他 update lock を取り、`.updates/state.json` の `engine.previous` を読みます。前バージョンがなければ変更前に終了コード 2 で失敗します（`strata_control/updater.py:1033-1043`）。
3. 対象 manifest を読み、署名 verifier を用意して全ファイルを検証します。検証失敗は終了コード 5 です。次に対象がすでに現在の engine なら「戻す先がない」として終了コード 2 で失敗します（`strata_control/updater.py:1044-1054`）。
4. 成功経路では前バージョンを `pinned` として保存し、通常の resolver がそのフォルダを選ぶことを再確認します。現在の版は `skipped` に記録される場合があり、`previous` / `active` と履歴も更新します。対象が現 PC に適合せず resolver が選べない場合は pin を消して状態を戻し、終了コード 5 になります（`strata_control/updater.py:1055-1078`）。
5. Engine identity が変わると保存済み tuning preset に再確認マークを付けます。preset 自体を削除・書き換えません。preset の既存マークが rollback により元の identity に戻る場合は再確認不要となることがあります（`strata_control/updater.py:1073-1078`、`strata_control/preset_marks.py:72-96`）。

成功時の human 出力は変更前後の version と tuning preset の扱いを表示します。更新で保持された新しい版を再試行する案内として `strata update --force` も表示します（`strata_cli/update_cmd.py:188-196`）。

## 注意点

- rollback は直前に保持された一つの engine が対象です。任意の過去版を選ぶ引数や、新しい engine の取得機能はありません（`strata_control/updater.py:1033-1049`）。
- `--force` は parser で共通受理されますが、rollback 処理はその値を参照しません。新しい版の再試行に使うのは `strata update --force` です（[`--force`](--force.md)、`strata_control/updater.py:1033-1078`）。
- `--feed` も共通 parser から受理されますが、rollback 分岐では参照されず、feed を読みません（[`--feed`](--feed.md)、`strata_cli/update_cmd.py:182-200`）。
- option の索引は [`docs/cli/README.md`](../../../README.md) を参照してください。`--json` と `--quiet` は `strata_cli/cli.py` が one-shot command parser に追加し、`--help` は argparse の標準 option です（`strata_cli/cli.py:508-515`）。

## 出力と失敗

成功時の human 出力は `Engine rolled back: <from> -> <to>.` に続けて tuning preset の扱いと再試行方法を表示します。machine mode は `ok: true` と rollback 結果を JSON で出力します（`strata_cli/update_cmd.py:188-196`）。

主な失敗は次のとおりです。

- previous engine がない、またはすでにその engine に戻っている: 終了コード 2。
- manifest / 全ファイル検証に失敗、または現 PC で対象を選択できない: 終了コード 5。
- engine が稼働中で待機しない、または `--wait` の期限内に終了しない: `Busy` による終了コード 7。
- 人間向け出力では `strata: ...` を標準エラーへ、`--json` / `--output json` / `--output jsonl` では JSON error object を標準出力へ出し、失敗コードを返します（`strata_cli/update_cmd.py:167-172,225-234`）。

## 根拠

- `strata_cli/cli.py:114-140,508-515,2135-2137` — `components` 階層、update parser 登録、共通 `--json` / `--quiet` と dispatch。
- `strata_cli/update_cmd.py:30-40,57-59` — rollback parser と共通オプション。
- `strata_cli/update_cmd.py:163-234,237-252` — rollback の分岐、出力・例外、稼働中の待機判断。
- `strata_control/updater.py:1033-1078` — previous engine の取得、検証、切替状態、失敗条件、履歴。
- `strata_control/updater.py:65-75,275-309` — serving 判定、busy と待機処理。
- `strata_control/engine_component.py:62-64` — pin が engine 選択に使われる state field。
- `strata_control/preset_marks.py:72-96` — tuning preset の再確認マークと、元 identity に戻った場合の扱い。
- `docs/INSTALL.md:114-116` — 利用者向け更新・rollback 案内。

確認範囲は上記 checkout のソースと既存文書です。同一 revision の実行可能 CLI help および Release artifact は確認していません。ビルド、テスト、rollback の実行は行っていません。
