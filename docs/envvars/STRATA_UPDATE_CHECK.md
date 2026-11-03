# `STRATA_UPDATE_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata launch` が開く Launch Monitor から起動する、エンジン更新フィードの日次バックグラウンド確認を抑止します。確認結果はローカルのキャッシュに保存され、更新可能なエンジンがあれば Monitor に短い通知を表示します。この環境変数は確認処理のゲートであり、手動の `strata update` やエンジンの自動更新を制御しません。

## 値と判定

`refresh_cache()` は `os.environ.get(CHECK_ENV, "").strip().lower()` を文字列比較します。数値変換はせず、空白を除いた文字列全体を小文字化して判定します。

| 値 | 日次確認 |
|---|---|
| 未設定 | 有効（空文字相当） |
| 空文字、または空白だけ | 有効 |
| `0`, `off`, `no`, `false`, `never`（大文字小文字・前後空白は不問） | 無効 |
| 上記以外（例: `1`, `true`, `yes`, `2`, `disabled`） | 有効 |

`0anything` のように無効値の後ろに文字が続く値は一致せず、有効になります。無効値が指定されても環境変数は変更されず、処理が `False` を返して確認を行いません。CLI 引数や設定ファイルによるこの判定の上書きはありません。

## 有効になる条件

- `strata launch` の Monitor 起動経路で、Monitor が mount されること。通常のエンジン起動や `strata monitor` のコード経路だけでは、この日次確認は開始されません。
- Monitor の `daily_check` 情報が真であること。`run_monitor()` はこれを明示的に設定します。
- `acquisition.is_forbidden()` が偽であること。禁止状態なら環境変数を読む前にスレッド起動を中止します。
- 無効値を設定していないこと、かつ直近24時間以内の確認または試行が記録されていないこと。

`STRATA_UPDATE_CHECK` は `refresh_cache()` の各呼び出しで読み直され、プロセス内に判定値を cache しません。既存の `last_check` または試行記録が24時間未満なら、値が有効でもその回の確認は省略されます。CLI の `--feed` などのフィード選択は確認先を指定するもので、この環境変数による停止判定を上書きしません。

## 実行時の詳細

Monitor は mount 時に専用 daemon thread を開始し、その thread 内で `refresh_cache()` を呼びます。環境変数が無効値なら、状態ファイルの確認やネットワーク確認より先に終了します。有効で確認を行う場合は、試行日時を先に記録し、フィード確認を実行します。状態ディレクトリ・試行ファイルを書けない場合は確認せず終了し、フィード確認が例外を送出した場合も通知を出さず終了します。確認は最大5秒の feed timeout を設定します。

この処理は静かに動作し、抑止・ネットワーク失敗・記録失敗について stdout/stderr のログや終了コードを出しません。確認成功時に新しいエンジンが見つかった場合は、完了 callback が Monitor の表示を更新し、ローカルキャッシュの内容から通知を作ります。キャッシュ表示自体はネットワーク確認を行いません。明示的なエンジン更新コマンドの処理には `STRATA_UPDATE_CHECK` の参照がなく、この設定によって手動更新は停止しません。

## 根拠

- `strata_control/engine_update.py:67-69,79-110`: 変数名、文字列判定、日次確認の間隔、記録・失敗時の静かな終了。
- `strata_control/engine_update.py:113-137`: acquisition 禁止時の早期終了、daemon thread、check callback、5秒 timeout 設定。
- `strata_cli/launch/app.py:425-432`: Launch Monitor に `daily_check=True` を渡す起動経路。
- `strata_cli/launch/monitor_ext.py:55-64`: mount 時に `start_daily_check()` を呼ぶ条件。
- `strata_cli/launch/monitor_ext.py:66-79`: キャッシュ通知の更新と、失敗を画面外に抑える処理。
- `strata_control/acquisition.py:53-55`: 確認開始前に使われる別の acquisition 禁止判定。
- `docs/SAFETY.md:63-72`: Monitor の日次確認と本変数の説明。ただし同文書は抑止値を `0` のみと略記しています。実装が認識する値は `0`, `off`, `no`, `false`, `never` です。
