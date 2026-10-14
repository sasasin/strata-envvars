# `HIP_DEVICE_LIB_PATH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有ソースを対象とし、外部 HIP runtime の内部動作は対象外。

## 役割

Strata の HIP サーバーは、engine 子プロセスへ渡す環境を作る際、この変数が指すパスの存在を確認します。値が空でなく、パスが存在しない場合は子プロセス環境から変数を削除して、stderr に通知します。存在するパスの値はそのまま渡します。これはサーバー起動前の環境補正であり、Strata engine 内の計算設定ではありません。

## 値と判定

数値や真偽値としては parse しません。`child_env()` が作った環境辞書に対して `env.get("HIP_DEVICE_LIB_PATH")` の真偽を判定し、真の場合に `Path(value).exists()` を調べます。

| 子プロセス環境での値 | Strata の処理 |
|---|---|
| 未設定 | 何もしない。未設定のまま渡す |
| 空文字列 | 偽として扱い、存在確認も削除も行わない。空文字列のまま渡す |
| 空でない値でパスが存在する | 変更せず渡す。ファイルかディレクトリかの追加判定はしない |
| 空でない値でパスが存在しない | 子プロセス環境から削除し、stderr に `strata serve: AMD: HIP_DEVICE_LIB_PATH=<値> does not exist: not passed to the engine` と出す |

文字列の大小文字、数値としての妥当性、空白の trim、パスの内容は別途検査されません。たとえば `0` も空でないパス文字列として存在確認の対象になります。

## 有効になる条件

- `child_env(cfg)` で `cfg["backend"] == "hip"` の場合に限り `hip_env_guard()` が実行されます。CUDA その他の backend ではこの変数を検査しません。
- `child_env()` は現在の `os.environ` をコピーした後、設定の `cfg["env"]` があればそのキーと値（文字列化）で上書きします。そのため guard は、元のプロセス環境ではなく、設定反映後の値を検査します。
- `setup.py` の HIP engine / HIP image generator のビルド経路は `HIP_PATH` や `ROCM_PATH` を設定しますが、`HIP_DEVICE_LIB_PATH` を設定する処理は確認できませんでした。

## 実行時の詳細

サーバーは通常の engine 起動時に `child_env(cfg)` を作り、その環境を `StrataEngine` に渡します。`StrataEngine` はその辞書を `subprocess.Popen(..., env=env)` に渡して engine を起動します。replica 起動経路も replica ごとに `child_env()` を呼びます。従って、判定は子プロセス環境を作るたびに行われ、サーバープロセスの環境辞書を書き換える処理ではありません。ログの値は、削除された場合に元の不正な値を含みます。

コードのコメントと `docs/TROUBLESHOOTING.md` は、存在しない `HIP_DEVICE_LIB_PATH` 等を AMD runtime 起動前に取り除く問題対応を説明しています。この調査では、Strata が値を検査・削除して engine に渡す処理までを確認しました。変数が HIP runtime 内でどう使われるかは外部実装の領域なので記述していません。

## 根拠

- `serve/server.py:2788-2805`: 親環境のコピー、`cfg["env"]` の反映、HIP backend の場合の guard 呼び出し。
- `serve/server.py:2816-2846`: 非空値の `Path.exists()` 判定、存在しない場合の削除、stderr 通知。
- `serve/server.py:6547-6552,6700-6702,6750-6754`: replica と通常起動での `child_env()` 利用。
- `serve/server.py:819-820`: 子 engine の `subprocess.Popen()` に環境辞書を渡す箇所。
- `setup.py:2989-2995,3155-3159`: HIP build 時に `HIP_PATH` / `ROCM_PATH` は設定するが、この変数は設定しない箇所。
- `docs/TROUBLESHOOTING.md:148-153`: Windows AMD の起動問題に対する説明。実動作の根拠は上記サーバー実装。
