# `HIP_PATH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリや HIP runtime 自身がこの変数に与える意味は対象外。

## 役割

Strata の AMD/HIP 実行サーバーは、エンジンを起動する前に親プロセスから引き継いだ `HIP_PATH` を検査します。値が空でなく、そのパスが存在しない場合は、エンジンの子プロセスへ渡さないようにします。Strata のトラブルシューティング資料は、削除済み ROCm ディレクトリを指す `HIP_PATH` などが Windows 上の HIP エンジン起動時クラッシュに関係したため、サーバーが修復すると説明しています。

また、Strata の HIP エンジン／HIP 画像エンジンをローカルビルドするとき、`setup.py` は選択した ROCm root を `HIP_PATH` に設定してから CMake を起動します。このビルド経路では、入力された `HIP_PATH` を ROCm root の選択には使いません。

## 値と判定

実行時サーバーの `hip_env_guard()` は `env.get("HIP_PATH")` の値を調べます。環境変数自体の値を parse せず、真偽値と `Path(v).exists()` だけで判定します。

| 状態 | HIP backend のサーバーがエンジンへ渡す値 |
|---|---|
| 未設定 | 未設定のまま（追加しない） |
| 空文字 | 空文字のまま（`if v` が偽なので存在確認しない） |
| 空でない値のパスが存在する | 元の文字列をそのまま渡す |
| 空でない値のパスが存在しない | 子プロセス用環境からキーを削除し、stderr に理由を出す |

ファイルとディレクトリを区別せず、`Path.exists()` の結果を使います。値の前後空白除去、展開、正規化、大小文字比較は行いません。設定ファイルの `env` が `HIP_PATH` を指定した場合は、親環境をコピーした後でその値を上書きし、その上書き後の値が検査対象になります。

## 有効になる条件

- この検査は `child_env()` から `hip_env_guard()` を呼ぶ場合だけ実行されます。`child_env()` は `cfg["backend"] == "hip"` のときに guard を呼びます。CUDA backend などでは値の存在確認も削除も行いません。
- 検査はサーバーがエンジン用環境を作るたびに行われます。通常の起動と、カードグループごとにエンジンを作る replica 経路の両方が `child_env()` を使います。
- 存在するパスは、正しい ROCm インストールかどうかを Strata は検証しません。空でないパスが存在する限りそのまま渡します。
- `HIP_PATH` が未設定、空文字、または存在するパスなら、HIP_PATH に関する警告は出ません。

## 実行時の詳細

`child_env()` はまず `os.environ` のコピーを作り、GPU 可視性の設定と設定ファイル内の `env` 値を反映し、設定済みのライブラリディレクトリを環境へ追加します。その後 HIP backend なら `hip_env_guard()` を呼びます。guard は `HIP_PATH` に加えて `HIP_DEVICE_LIB_PATH` と `LLVM_PATH` も同じ規則で検査します。消した変数ごとに `strata serve: AMD: <変数>=<値> does not exist: not passed to the engine` を stderr に出します。

作成した環境辞書は `StrataEngine` に渡され、`popen(..., env=env)` で `[exe, "--serve", ...]` の子プロセス起動に使われます。したがって、サーバー自身の `os.environ` から値を削除する処理ではなく、エンジンに渡す環境だけの変更です。`StrataEngine` の再起動用データにも同じ env 辞書が保存されます。

ビルド時は `build_engine_hip()` と HIP backend の `build_image_engine()` が `rocm_root()` の返した root を `os.environ["HIP_PATH"]` に設定します。エンジン側は同時に `HIP_PLATFORM=amd`、`HIP_COMPILER=clang`、`HIP_RUNTIME=rocclr`、`ROCM_PATH=<root>` も設定し、画像エンジン側は `HIP_PLATFORM=amd` と `ROCM_PATH=<root>` を設定します。その後 CMake コマンドを実行します。`rocm_root()` が入力環境から選択に使うのは `ROCM_PATH`（未設定または空なら `/opt/rocm`）であり、`HIP_PATH` は読み取っていません。

## 根拠

- `serve/server.py:2788-2805` — 親環境のコピー、config `env` による上書き、HIP backend の guard 呼び出し。
- `serve/server.py:2816-2846` — `HIP_PATH` などの値が空でない場合の存在確認、削除と stderr ログ。
- `serve/server.py:770-773,819-821` — 子プロセス環境を `StrataEngine` に保存し、エンジン起動に渡す箇所。
- `serve/server.py:6550-6551,6697-6702` — replica と通常の serve 起動の双方が `child_env()` を使う箇所。
- `setup.py:2877-2887` — `rocm_root()` が `ROCM_PATH` または `/opt/rocm` を入力 root として選ぶ箇所。
- `setup.py:2989-3007,3155-3159` — HIP エンジンおよび HIP 画像エンジンのビルド環境に `HIP_PATH` を設定する箇所。
- `docs/TROUBLESHOOTING.md:148-153` — Windows の AMD エンジン起動時に、存在しない ROCm パスを指す変数をサーバーが除去する説明。
