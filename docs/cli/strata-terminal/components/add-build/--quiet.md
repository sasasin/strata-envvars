# `strata components add-build --quiet`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False`、指定時 `True` |

## 役割

人向けの通常案内を抑制するフラグです。`add-build` の処理内容は変えず、ローカルビルドをコンポーネント領域へ追加して使用中エンジンに切り替える処理はそのまま行います。成功案内を標準出力に出したくない呼び出しで使えます。

## 使い方

```sh
# ビルド済みエンジンを追加して切り替える。人向けの成功案内は表示しない。
strata components add-build /path/to/engine-build --quiet
```

`/path/to/engine-build` は `strata`（Windows は `strata.exe`）、必要なライブラリ、`BUILD.json` を含むビルド出力フォルダーに置き換えます。

## 値と既定値

`--quiet` は `store_true` の引数で値を取りません。既定値は偽で、指定すると真になります。`--quiet=true` のような値付き指定はこの parser の構文ではありません。複数回指定しても真のままです。引数 parser では `add-build` を含む one-shot コマンド群に共通フラグとして追加されています（`terminal/strata_cli/cli.py:539-546`）。

## 実行時の動作

`--quiet` が真で `--output human` の場合、CLI はコマンド処理中の標準出力を最大 64 KiB まで捕捉し、成功時には表示しません。`add-build` の通常成功案内は標準出力に出す3行（追加・署名状態・戻し方）なので、この人向け案内が抑制されます（`terminal/strata_cli/cli.py:2278-2297, 2339-2351`、`terminal/strata_cli/update_cmd.py:435-442`）。

操作そのものは抑制されません。指定フォルダーのエンジンを検査・コピーし、コンポーネント領域にローカルかつ未署名のパッケージを作成した後、エンジン選択状態を更新します。追加先が既に存在する場合は拒否されます（`terminal/strata_cli/update_cmd.py:425-442`、`terminal/strata_control/local_engine.py:127-177`）。このため、`--quiet` は dry-run や無変更モードではありません。

`--output json` または `--output jsonl` では machine 出力として扱われ、quiet の標準出力捕捉を行いません。したがって JSON の結果は `--quiet` を付けても出力されます。`--json` は `--output json` に切り替える alias です（`terminal/strata_cli/update_cmd.py:47-57, 435-437`、`terminal/strata_cli/cli.py:543-546, 2335-2340`）。

## 適用条件と副作用

人向け標準出力を抑える分岐は `--quiet` が真かつ output が `human` のときです。標準エラー出力は捕捉・抑制されません。失敗時に処理中の標準出力があれば標準エラーへ再出力し、捕捉上限を超えていた場合は省略通知も標準エラーへ出します（`terminal/strata_cli/cli.py:2344-2351`）。`add-build` の失敗は `strata: ...` 形式で標準エラーに出され、エラーコードを返します（`terminal/strata_cli/update_cmd.py:307-312, 430-433, 374-384`）。

このコマンドは実行中のモデルがある場合の待機・拒否条件も引き続き適用します。`--quiet` は `--wait` の値や対話条件を変更しません（`terminal/strata_cli/update_cmd.py:428-433, 500-515`）。また、成功時にはローカル package のファイルと manifest の作成、エンジン選択状態・履歴の保存が発生します。ダウンロードは行われません（`terminal/strata_control/local_engine.py:127-177`、`terminal/strata_control/updater.py:1701-1751`）。

## 出力とエラー

- `--quiet` と human 出力の組み合わせでは、成功時の人向け案内は表示されません。
- 失敗メッセージは標準エラーに残ります。処理中に捕捉した標準出力がある場合も失敗時には標準エラーに再出力されます。
- parser の不正な引数は `argparse` のエラー経路です。`--quiet` は parser 実行後の出力制御なので、引数エラーを抑制しません（`terminal/strata_cli/cli.py:2325-2334`）。
- `add-build` 固有の拒否では、フォルダー・エンジン情報の不備などに対して終了コード 2、実行不能または非対応 backend などに対して終了コード 5 が設定されています（`terminal/strata_control/local_engine.py:35-45, 57-74, 127-157`）。

## 根拠

- `terminal/strata_cli/cli.py:539-547` — one-shot parser 群への `--quiet` の登録。
- `terminal/strata_cli/cli.py:2278-2297, 2335-2351` — machine 出力時の分岐、quiet 時の標準出力捕捉、失敗時の再出力。
- `terminal/strata_cli/update_cmd.py:95-99` — `add-build` の位置引数と共通 option の登録。
- `terminal/strata_cli/update_cmd.py:425-442` — ローカルビルド追加・エンジン切り替えと成功時の出力。
- `terminal/strata_control/local_engine.py:127-177` — 入力検査、パッケージ作成、既存パッケージ時の拒否、コピーと manifest 作成。
- `terminal/strata_control/updater.py:1701-1751` — エンジン選択状態と履歴の保存。
- `terminal/strata_cli/update_cmd.py:307-312, 374-384, 500-515` — エラー出力と待機・対話条件。
