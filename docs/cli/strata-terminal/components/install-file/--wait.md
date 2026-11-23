# `strata components install-file --wait`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`float` として解析される。 |

## 役割

エンジンのパッケージファイルをインストールするとき、エンジンが稼働中なら、停止するまで最大何秒待つかを指定する。稼働中のエンジンがなければ待たない。

## 使い方

```sh
# 稼働中のエンジンが停止するまで最大300秒待ってから切り替える
strata components install-file ./engine.tar.gz --wait 300
```

## 値と既定値

- 値は必須で、`argparse` の `type=float` で解析される。別名はない（`terminal/strata_cli/update_cmd.py:51-52`）。
- parser 上の既定値は `None`。実行時には `a.wait or 0.0` として context に渡されるため、未指定と `0` はどちらも `0.0` になる（`terminal/strata_cli/update_cmd.py:319-321`）。
- `wait_until_idle` は待ち時間が `0` 以下なら、稼働中のエンジンを検出した時点で `Busy` を送出する。負数を含む値について専用の範囲検証やエラーメッセージはない（`terminal/strata_control/updater.py:381-391`）。
- 有限値であることの検証もない。`inf` や `nan` のような浮動小数点値を渡した場合の扱いを制限するコードは確認できず、待ち時間の上限として使えない可能性があるため、これらを指定しないこと（parser と期限判定: `terminal/strata_cli/update_cmd.py:51-52`、`terminal/strata_control/updater.py:384-391`）。

## 実行時の動作

`install-file` は共通オプション登録関数 `_common` を使うため、このコマンドの parser に `--wait` が追加される（`terminal/strata_cli/update_cmd.py:47-56,92-94`）。処理では値を `updater.Context.wait` に渡し、稼働状況の確認関数を `ctx.serving` に設定する（`terminal/strata_cli/update_cmd.py:319-321,341-345`）。

待機は単純にコマンド開始時に行うのではない。パッケージを展開・検証し、ステージング先からテスト起動した後、稼働状況を再確認して切り替える直前に `idle_gate` が `wait_until_idle` を呼ぶ（`terminal/strata_control/updater.py:1638-1698,1538-1569,395-401`）。稼働が続いていて指定秒数が経過すると `Busy`（終了コード `7`）となり、その回のエンジンは切り替えられない（`terminal/strata_control/updater.py:381-391,72-83`）。待機中は最大3秒間隔で再確認し、待機イベントを出す（`terminal/strata_control/updater.py:381-391`）。

## 適用条件と副作用

- `--wait` に正の値を明示すると、コマンド冒頭の `_maybe_wait` は対話確認を行わず、後段の切り替え前チェックでその秒数だけ待つ（`terminal/strata_cli/update_cmd.py:341-345,500-503`）。
- 値を省略するか `0` を指定し、エンジンが稼働中の場合、対話端末では「停止を待つか」を尋ねる。`y` / `yes` の回答は6時間の待機に設定され、それ以外は待機を設定しない（`terminal/strata_cli/update_cmd.py:500-515`）。非対話または機械出力モードでは質問せず、切り替え前の待機がないため、稼働が続いていれば `Busy` で失敗する（同上、`terminal/strata_control/updater.py:381-391`）。
- Strata 自身の `launch-` プロファイルが稼働中の場合は `_maybe_wait` の確認質問を省略する。テスト起動自体が先に `Busy` で失敗することもあり、その場合も `--wait` の待機処理には進まない。`Busy` は「モデルを先に停止して再実行する」案内を返す（`terminal/strata_cli/update_cmd.py:504-515`、`terminal/strata_control/updater.py:72-83,1546-1556`）。
- `--wait` は稼働中プロセスを停止しない。パッケージファイル自体はその場に残され、処理失敗時にはステージング領域が削除される（`terminal/strata_control/updater.py:1638-1648,1695-1698`）。

## 出力とエラー

- 人間向け出力では、待機中に `An engine is serving; waiting for it to stop before updating.` が標準出力へ表示される。`jsonl` では `waiting` イベントが出力され、`json` では進行イベントは出力されない（`terminal/strata_cli/update_cmd.py:117-139`）。
- 待機時間内にアイドルにならなければ終了コード `7`。人間向けでは `strata: ...` を標準エラーへ、`json` / `jsonl` では `ok: false` とエラーコードを含む JSON を出力する（`terminal/strata_control/updater.py:72-83`、`terminal/strata_cli/update_cmd.py:303-312,374-378`）。
- 数値として解析できない値は parser の `float` 変換で拒否される。Strata 固有の追加検証はない（`terminal/strata_cli/update_cmd.py:51-52`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,92-94` — `install-file` parser への共通オプション登録、`--wait` の型・既定値。
- `terminal/strata_cli/update_cmd.py:303-321,341-350` — 秒数の context への伝達と install-file 実行経路。
- `terminal/strata_cli/update_cmd.py:500-515` — 未指定・ゼロ時の対話確認、および `launch-` プロファイルの扱い。
- `terminal/strata_control/updater.py:381-401,406-417` — 待機期限・再確認間隔・待機値の単位。
- `terminal/strata_control/updater.py:1538-1569,1638-1698` — テスト起動後、切り替え前に待機する位置と失敗時のステージング領域の後始末。
- `terminal/strata_control/updater.py:61-83`、`terminal/strata_cli/update_cmd.py:303-312,374-378` — Busy の終了コードとエラー出力。
