# `strata launch`（Strata Terminal CLI / POSIX）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| POSIX の入口 | `bin/strata`（Terminal CLI の `strata` 実行ファイル） |
| 主な実装 | `strata_cli/launch/cmd.py`、`strata_cli/launch/runner.py` |

## 役割

モデルの選択または既存 preset の読み込みから、必要なファイルの準備、推論エンジンの起動、サーバーの監視までを一つのコマンドで行います。フラグを付けずに実行すると対話式の案内画面を開き、フラグで設定を渡すと案内画面での質問を省いて起動できます。preset は Strata アプリの profiles および tuning presets と共有されます。

このページはコマンド全体の概要です。オプションの値・既定値・個別の挙動は `strata launch --help` と各オプション文書を参照してください。

## 基本的な使い方

```sh
# 対話式の案内画面から設定して起動
strata launch

# 保存済み preset で起動し、監視画面を開く
strata launch --preset "Office"

# フラグで設定して起動し、アドレスを表示して戻る
strata launch --model iq3_xxs --context 128k --access lan --port 8080 --no-tui

# 実際には変更せず、起動時の計画を表示
strata launch --plan --model q2_0
```

フラグによる起動では、モデル名（または `--model-path`）、context、画像対応、並列数、GPU、チューニング、アクセス範囲、port などを指定できます。preset に追加フラグを重ねた場合、その変更は通常その起動だけに適用されます。次回以降も保持する場合は `--save-preset NAME` を指定します。

高度なエンジン引数や環境変数を起動設定に加える `--set` の詳細は [`--set`](--set.md) を参照してください。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 対話式セットアップ | `strata launch` | preset を選ぶか、最初から設定し、起動後は Terminal の monitor で状態を確認します。 |
| preset 起動 | `strata launch --preset NAME` | 保存済みの設定で起動し、monitor を開きます。ほかの起動フラグを重ねて一時変更できます。 |
| 非対話式起動 | `strata launch --model NAME --no-tui` | 画面を開かずに起動し、接続アドレスを表示して戻ります。画面入力がない環境にも向きます。 |
| 起動計画 | `strata launch --plan --model NAME` | 起動内容や必要なダウンロードを表示して終了します。help の説明では変更・ダウンロードは行いません。 |
| preset 管理 | `--list-presets`、`--delete-preset NAME` | 保存済み preset を一覧表示または削除します。サーバー起動とは別の管理操作です。 |
| 稼働状態の管理 | `--status`、`--stop [--preset NAME]`、`--show-key` | このコマンドが起動したサーバーの状態確認、停止、API key の表示を行います。 |

管理モードの利用例:

```sh
strata launch --list-presets
strata launch --status
strata launch --stop
```

`--show-key` は API key を表示します。表示内容は接続資格情報として扱ってください。

## 起動時の主な動作

- 通常の起動では、モデルやエンジンに必要なファイルを確認し、不足分の取得やセットアップを行ってからサーバーを起動します。実際に必要な処理は、選んだモデル、既存ファイル、実行環境によって異なります。
- 起動時の設定から launch 用の run config を組み立てます。`--plan` はコマンドの説明上、変更を加えず計画を表示して終了します。
- 成功すると monitor を開きます。`--no-tui` を指定した場合は画面を開かず、アドレスを表示して戻ります。ブラウザーは既定では開かず、`--open` を指定したときに開きます。
- `--save-preset NAME` を付けると、選択した設定を preset として保存します。既存 preset を指定した起動でフラグを重ねただけなら、その変更は保存されません。
- LAN、Cloudflare、Tailscale など、この PC の外から到達できるアクセス方式を選べます。API key を無効にした共有も可能ですが、CLI は利用可能なクライアントがキーなしでアクセスできる旨の警告を行います。

## すでにサーバーが動いている場合

同じ設定で起動しようとすると、既存サーバーを再起動せず、稼働中のアドレスを表示します。同じ port で異なる設定を起動しようとすると、対話画面では再起動の確認を行います。`--no-tui` では確認できないため、そのままでは拒否されます。`--restart` を指定すると既存サーバーを停止してから新しい設定で起動します。`--yes` だけでは再起動しません。

別の `--port` を使えば既存サーバーと並行して起動できますが、複数モデルが GPU メモリーを使い切る可能性があります。

## オプションの調査・文書

全オプションと使用例は、対象の Terminal CLI に対して `strata launch --help` で確認できます。ソース上で確認した主なグループは、モデルとファイル、推論設定、アクセスと API key、実行・保存、計画表示、preset・server 管理です。リリース済み CLI と checkout のソースが異なる場合、help は実際に使う CLI のオプション一覧、ソースは記載した commit の根拠として区別してください。

このコマンドのオプション個別文書は [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節に一覧します。

## 根拠

- Strata `strata_cli/launch/cmd.py:16-29,76-146` — 使用例、コマンド説明、オプションと管理操作の parser 定義。
- Strata `strata_cli/launch/cmd.py:630-835` — 起動・計画表示・preset 管理・結果表示の分岐。
- Strata `strata_cli/launch/runner.py:371-407,1235-1263` — 起動設定の構築と launch 用 config / profile の準備。
- Strata `strata_cli/launch/runner.py:1507-1536` — 既存 server と同一 port で起動する場合の確認・拒否条件。
- Strata `docs/TERMINAL_LAUNCH.md` — 対話画面、monitor、preset、アクセス、起動例の利用者向け説明。
