# `DRAFT_VOCAB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

`DRAFT_VOCAB` は Strata の Docker entrypoint が読む環境変数です。空でない場合、その値を `strata launch --draft-vocab VALUE` に渡し、ドラフト層（MTP）または DFlash2 のドラフト語彙サブセット選択に使います。Strata の他の起動経路がこの環境変数を直接読む箇所は見つかりませんでした（`tools/docker/entrypoint.sh:246`）。

## 値と判定

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Docker entrypoint 経由 | 引数を追加しません。既存 preset の設定、または通常の launch / setup の選択が使われます。 | `cjk`, `en`, `cyrillic`, `fr`, `latin`, `arabic`。値は文字列として CLI に渡され、`strata launch` の choice 検証を通ります。 | 上記以外。例: `CJK`, `0`, `true`, `en `、空白だけ。 |

entrypoint は `${DRAFT_VOCAB:-}` の文字列長が 0 より大きい場合だけ値を転送します。そのため未設定と空文字は同じ扱いです。値の trim・小文字化・数値変換は entrypoint では行いません。選択肢は launch 側で `DRAFT_VOCAB_MODES` として定義され、大文字小文字を区別して一致させます（`tools/docker/entrypoint.sh:246`、`terminal/strata_cli/launch/settings.py:33-34`、`terminal/strata_cli/launch/cmd.py:105-107`）。

## 有効になる条件

- Docker の既定起動（entrypoint が `strata launch` を呼ぶ経路）でのみ、この環境変数が読み取られます。コンテナで別コマンドを指定した場合、この転送経路は通りません（`tools/docker/entrypoint.sh:2-7,184-186,246`）。
- 空でない値は既存 preset の設定に対する今回の launch 引数となり、launch の引数処理が `s.draft_vocab` に設定します（`terminal/strata_cli/launch/cmd.py:245-259`）。entrypoint は何らかの設定を渡すと preset を保存するため、選んだ値は通常の Docker 起動では保存設定にも反映されます（`tools/docker/entrypoint.sh:246-247,264-268`）。
- runner が `--draft-vocab` を setup に渡すのは `modelstate.HELPER_FAMILIES` のモデルファミリーに限られます（`terminal/strata_cli/launch/runner.py:1317-1320`）。ドラフト語彙ファイルが実際に使われるには MTP または DFlash2 のドラフターと対応ファイルが必要です。setup は MTP 用 `rt/draft_vocab.bin` または既存 DFlash2 データ用の語彙ファイルを選択値に合わせて更新します（`terminal/setup.py:9026-9048,11093-11106,12264-12280`）。
- したがって語彙選択値が通っても、対応するドラフターが使われないモデルや起動では推測語彙を変える結果は生じません。

## 実行時の詳細

この名前を読むのはシェル entrypoint の起動時の一回で、値を `--draft-vocab` の引数へ転送します。プロセス起動後の環境変更を再読する処理や cache はありません。空でない `DRAFT_VOCAB` があると `have=1` となり、entrypoint は `--save-preset` を付けます。既存 preset を使う場合も、同じ起動時に得た引数が preset の設定へ上書きされます（`tools/docker/entrypoint.sh:184-186,246,264-268`、`terminal/strata_cli/launch/cmd.py:245-259`）。

CLI で受け付けた選択は launch 設定に保持され、helper family では setup に渡されます。setup は MTP の `draft_vocab.bin` を、配布済み語彙のいずれか（または旧配布版）と認識した場合に選択に応じて置き換えます。手作りの別内容のファイルは保持します。DFlash2 の語彙もデータディレクトリに対象ファイルがある場合に更新します（`terminal/setup.py:9026-9048,12275-12280`）。

## ログと測定値

未知の値は launch の choice 検証で拒否され、launch は実行されません。Docker entrypoint は非ゼロ終了を受けると `strata launch stopped with code $rc (the lines above say why). The container ends. Fix that and start it again: finished steps are not repeated, and an interrupted download continues where it stopped.` を出して終了します（`terminal/strata_cli/launch/cmd.py:105-107`、`tools/docker/entrypoint.sh:306-312`）。Strata ソース上で `DRAFT_VOCAB` 自体に対する専用ログは確認できませんでした。測定値は記載しません。

## 根拠

- `tools/docker/entrypoint.sh:1-7,184-186,246-268,306-312` — Docker 起動経路、値の転送、preset 保存、失敗時の処理。
- `terminal/strata_cli/launch/settings.py:31-34`、`terminal/strata_cli/launch/cmd.py:105-107,245-259` — 選択肢と launch 設定への反映。
- `terminal/strata_cli/launch/runner.py:1317-1320` — helper family に対する setup 引数。
- `terminal/setup.py:9026-9048,11093-11106,12264-12280` — MTP / DFlash2 の語彙サブセット更新と設定の保持。
