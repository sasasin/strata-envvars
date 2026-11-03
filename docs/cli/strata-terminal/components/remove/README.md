# `strata components remove`（Strata Terminal CLI）

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/engine_library.py` |

## 役割

このコマンドは、ローカルの component フォルダに導入済みの Qwen 系または DeepSeek 系 engine package を一つ削除します。ネットワークから何かを取得するコマンドではありません。モデルファイルと設定は削除対象外です。現在使用中の engine と、実行中プログラムが使用している engine は削除できません（`strata_cli/update_cmd.py:88-91,358-359`、`strata_control/engine_library.py:294-309`）。

## 基本的な使い方

まず導入済み engine と使用中のものを確認してから、一覧に表示された版番号またはフォルダ名を指定します。

```sh
# 一覧を確認する（ファイル変更なし）
strata components engines

# 一覧で確認した版番号を削除する
strata components remove 0.1.54

# 同じ版番号が複数あるときは family を指定する
strata components remove 0.1.54 --family deepseek
```

版番号またはフォルダ名で一意に決まらない場合は、エラーに表示されるフォルダ名を指定してください。既定の component フォルダ以外を調べる場合は `--components-dir DIR` を付けられます。削除操作そのものをせずに候補を確認する専用の dry-run モードはありません（`strata_cli/update_cmd.py:47-58,88-91`、`strata_control/engine_library.py:198-211`）。

## 実行モード

`strata components remove ENGINE` が削除モードです。位置引数 `ENGINE` は版番号かインストール先フォルダ名です。`--family` は `qwen` または `deepseek` に限定され、同一指定で複数 engine が見つかった場合の選択に使います。省略時は両 family から検索します（`strata_cli/update_cmd.py:88-91`、`strata_control/engine_library.py:198-211`）。

`--output json` または alias の `--json` は機械可読な結果を標準出力へ出し、`--quiet` は成功時の人向け標準出力を抑えます。これらは削除の可否や対象を変えません（`strata_cli/update_cmd.py:56,395-400`、`strata_cli/cli.py:508-515,2249-2265`）。

共通引数として `--components-dir`、`--backend`、`--feed`、`--wait`、`--force`、`--model-config`、`--output` も parser に登録されています。削除経路は feed を読み込まず、`--wait` による待機処理も呼びません。`--components-dir` は対象の component root を選びます。`--backend` は engine 一覧の適合判定と「使用中」判定に使われますが、対象 engine の family・版番号の検索条件にはなりません。使用中判定にも影響するため、通常は `--backend` を省略して実行してください（`strata_cli/update_cmd.py:47-56,244-255,272-273`、`strata_control/engine_library.py:91-111,167-177,198-211`、`strata_control/engine_component.py:1012-1097`）。

## 主な動作

- parser は `strata components remove` を登録し、必須の位置引数 `engine` と任意の `--family` を受け取ります。`strata_cli/cli.py` はこのサブコマンドを `update_cmd.run()` に渡します（`strata_cli/update_cmd.py:88-91`、`strata_cli/cli.py:139-140,2136-2138`）。
- 実行時に hardware 情報と component root を用意し、engine 一覧から指定に一致する一件を解決します。版番号が複数の folder に一致する場合や該当 engine がない場合は、削除処理に進まず失敗します（`strata_cli/update_cmd.py:244-255,358-359,378`、`strata_control/engine_library.py:198-211`）。
- 削除処理は update lock 内で一覧を再取得し、engine がまだ存在すること、使用中でないこと、稼働中プログラムに使われていないことを確認します（`strata_control/engine_library.py:167-177,294-309`）。
- 対象フォルダを同じ親の `.deleting-<識別子>` へ rename してから再帰削除します。開いたままのファイルがあり削除しきれない場合、残った `.deleting-*` は次回の削除時に掃除を試みます（`strata_control/engine_library.py:310-318,341-348`）。
- Qwen 系では更新 state の `previous` / `pinned` が削除対象を指す場合に解除し、同じ版番号の engine が他に残らない場合は失敗記録も取り除いて、削除履歴を保存します。DeepSeek 系では対象が設定した pin として有効でなく、pin ファイルが残っている場合に stale pin を解除します（`strata_control/engine_library.py:319-334`）。
- 正常終了時、人向け出力には削除した版番号と解放容量を表示します。JSON 出力には `ok: true` と削除結果を含めます（`strata_cli/update_cmd.py:395-400`）。

## 関連状態・他の実行経路

Qwen 系と DeepSeek 系は異なる保存場所・選択状態を使い、片方の削除はもう片方のファイルや状態を変更しません。`strata components engines` は候補・使用中状態を一覧し、`strata components use` は導入済み engine への切り替えを行います（`strata_control/engine_library.py:6-17`）。使用中の engine を消すには、先に [`strata components use`](../use/README.md) で別の engine を選んでください。一覧表示については [`strata components engines`](../engines/README.md) を参照してください。

このコマンド節の option 一覧と個別文書へのリンクは[CLI 索引](../../../README.md)にあります。

## 注意点と失敗

- 現在使用中の engine は「別のものに切り替えてから」として拒否されます。稼働中プログラムが使う engine も停止するまで拒否されます（`strata_control/engine_library.py:167-176,308-309`）。
- engine が未導入、指定が曖昧、または対象名が不正な場合は変更せず失敗します。rename が OS エラーで失敗した場合も「何も変更していない」として終了コード 6 で返します（`strata_control/engine_library.py:198-211,299-316`）。
- 使用中・稼働中による拒否、または導入先の状態変化による拒否は `UpdateError` として CLI のエラー経路に渡ります。テキスト出力では `strata: ...` を標準エラーへ、JSON モードでは `ok: false` と error 情報を標準出力へ出します（`strata_cli/update_cmd.py:237-242,307-311`、`strata_cli/cli.py:2167-2184`）。
- 削除対象のサイズは一覧時に走査したファイルサイズの集計です。ロックされたファイルの削除が保留されても、CLI は `ignore_errors=True` で削除を続けるため、表示上の解放容量と実際に消えた容量が一致しない可能性があります（`strata_control/engine_library.py:35-46,317,333-334`）。

## 根拠

- Strata `strata_cli/update_cmd.py:47-58,82-95` — 共通引数と `remove` parser の定義。
- Strata `strata_cli/cli.py:139-140,508-515,2136-2138,2249-2265` — parser 登録、`--json` / `--quiet` の追加、実行委譲、出力モード。
- Strata `strata_cli/update_cmd.py:233-255,272-273,358-400` — root 選択、コマンド実行、結果表示。
- Strata `strata_control/engine_library.py:91-123,167-211` — engine 一覧、適合状態、削除可否と対象解決。
- Strata `strata_control/engine_component.py:1012-1097` — Qwen 系での backend 指定時の使用 engine 解決。
- Strata `strata_control/engine_library.py:294-348` — 削除検査、フォルダ操作、state 更新、後続掃除。
