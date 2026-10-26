# `GPUS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Docker コンテナ用起動スクリプトでの読み取りを対象とする。

## 役割

Docker イメージの起動時に `strata launch` へ使用する GPU 番号を渡します。対象は `docker/entrypoint.sh` が通常のサーバー起動（引数なし、または `run` / `serve`）を処理する経路です。任意のコマンドを起動する経路では設定を組み立てず、`GPUS` を読みません。

## 値と判定

このスクリプト自身は GPU 番号リストを検証しません。シェルのパラメーター展開と `case` で扱いを決め、番号リストの構文検査は後段の `strata launch` が行います。

| `GPUS` の状態 | 処理 |
|---|---|
| 未設定または空文字 | `GPU` の値へフォールバック。`GPU` も未設定または空なら空文字となり、GPU 指定を渡さない |
| `all` または `ALL` | GPU 指定を渡さない。`all` と `ALL` だけを特別扱いし、大小文字を一般的に無視する判定ではない |
| その他の非空文字列 | `strata launch --gpu <値>` として渡す。`GPU` より `GPUS` が優先 |

したがって、たとえば `GPUS=0,1` は `--gpu 0,1` となります。`All` は特別扱いされず、番号リストとして渡されるため整数変換で失敗します。`strata_cli/launch/cmd.py` の `_gpus()` は空白を削除し、カンマで分けた各要素を `int()` に変換します。整数でない要素があれば `ValueError` になります。空要素は除外されるため、`0,,1` は `[0, 1]` として解釈されます。この変換段階では GPU の存在や番号の範囲は検査しません。setup 側は複数番号の指定で、異なる GPU が2個以上あることを確認し、その後指定番号が見つかるか、同時使用できるかを確認します（`setup.py:1663-1677,1680-1696`）。単一番号も `setup.py` で GPU の存在・利用可否を検査します（`setup.py:1777-1786`）。

## 有効になる条件

- Docker entrypoint のサーバー起動経路でのみ適用されます。entrypoint に別コマンドを渡すと、通常起動処理より前にそのコマンドを `exec` するため、この設定変換は通りません（`docker/entrypoint.sh:41-44`）。
- `GPUS` または `GPU` に番号リストを指定すると `--gpu` を渡し、同じ起動設定に `GPU_ROLES` も指定していた場合は起動を中止します。標準エラーに `Set GPU_ROLES or GPU / GPUS, not both.` を出して status 2 で終了します（`docker/entrypoint.sh:190-210`）。
- `GPUS=all` / `ALL`、または両方の変数が空の場合は `--gpu` が渡されません。この場合、選択は保存済み preset / run settings の状態に従い、値が常に新規の自動選択を強制するわけではありません。
- 設定された番号がコンテナから見える GPU と一致するかは、この環境変数の分岐だけでは保証されません。entrypoint は engine が利用可能かを事前確認しますが、その確認は `GPUS` による選択指定を組み立てる前です（`docker/entrypoint.sh:124-148,157-160,190-204`）。

## 実行時の詳細

entrypoint は `gpus="${GPUS:-${GPU:-}}"` として値を決めます。シェルの `:-` 展開なので、`GPUS` が未設定または空文字なら `GPU` にフォールバックします。選択値が空、`all`、`ALL` 以外なら `--gpu` として引数に追加し、プリセットに変更があったことを示す `have` も設定します（`docker/entrypoint.sh:190-194`）。

番号指定があると、起動前に `/data/install/strata-*.json` の保存済み設定を調べます。各設定の `gpu` が要求値と異なる場合、設定ファイルを削除して「設定を作り直す」ログを出します。比較前に要求値から空白文字を削除しますが、この比較用変換は `--gpu` に渡す値自体には適用されません。JSON 設定を削除してもモデルファイルは消しません（`docker/entrypoint.sh:193-203`）。

その後 `strata launch` は preset を引数に受け取り、CLI が `--gpu` の値を GPU 番号リストへ変換して launch 設定に載せます（`strata_cli/launch/cmd.py:112,192-199,246-250`）。launch runner は保存済み設定に対して必要な `setup` 引数を作り、GPU が複数なら `--gpus`、1つなら `--gpu` を使います（`strata_cli/launch/runner.py:865-897`）。環境変数そのものはリクエストごとには読み直されず、entrypoint の起動時に一度処理されます。

## 根拠

- `docker/entrypoint.sh:41-44` — 任意コマンド起動時の早期 `exec`。
- `docker/entrypoint.sh:190-210` — `GPUS` / `GPU` の優先順位、`all` 判定、CLI 引数、GPU roles との排他。
- `docker/entrypoint.sh:193-203` — 保存済み GPU 設定の比較・削除とログ。
- `strata_cli/launch/cmd.py:112,192-199,246-250` — `--gpu` の CLI 定義、値の整数リスト化、launch 設定への反映。
- `strata_cli/launch/runner.py:865-897` — launch から setup へ選択 GPU を渡す処理。
- `setup.py:1663-1696,1777-1786,8691-8697` — 複数 GPU の値検査、番号の存在・利用可否確認、および `--gpu 0,1` を複数指定として扱う処理。
- `docs/DOCKER.md:122-123` — Docker 向けの利用説明。コードに合わせ、空文字は `GPU` へのフォールバックも含む。
