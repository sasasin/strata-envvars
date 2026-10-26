# `HIP_PATH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata の HIP backend では、`strata serve` が engine 用の子プロセス環境を作る際、`HIP_PATH` が指す場所が存在しないときに、その変数を子プロセスへ渡さないようにします。存在する場所を指定している場合は値を保ちます。これは Strata が行う環境の整理であり、HIP runtime が `HIP_PATH` をどう解釈するかは対象外です。

Strata 同梱の Windows packaging tool も、engine の依存 DLL を探す既定検索先の組み立てにこの値を使います。また `setup.py` は HIP engine や HIP image engine の build 前に、見つけた ROCm root を `HIP_PATH` に設定します。

## 値と判定

serve の `hip_env_guard()` は値を数値やパス文字列として parse・正規化しません。Python の辞書値として truthy かを見て、truthy の場合に `Path(value).exists()` を確認します。

| serve 子プロセス用の値 | Strata の処理 |
|---|---|
| 未設定 | 何もしない |
| 空文字 | truthy でないため残す。存在確認や警告はしない |
| 空でない値で、そのパスが存在する | `HIP_PATH` をそのまま子プロセス環境に残す |
| 空でない値で、そのパスが存在しない | 子プロセス環境から削除し、stderr に理由を出す |

パスがディレクトリかファイルかは `exists()` だけでは区別しません。相対パスの解決や存在確認の細部は Python の `Path.exists()` に委ねられます。

packaging tool の `_default_search(target)` は、target が `windows` で始まる場合に限り、`HIP_PATH` が空でなければ `<HIP_PATH>/bin/x64` と `<HIP_PATH>/bin` を検索候補に加え、存在するディレクトリだけを返します。明示的な `--search` が指定されていればそちらが優先されます。

## 有効になる条件

- serve の整理は `child_env()` が `cfg["backend"] == "hip"` の場合に `hip_env_guard()` を呼ぶ経路でだけ行われます。CUDA backend などではこの guard は呼ばれません。
- `child_env()` はまず親プロセスの `os.environ` を複製し、config の `env` を重ねてから guard を呼びます。そのため確認対象は、親環境か config の `env` から得た最終的な子プロセス用の値です。
- replicas も各 engine 起動時に `child_env()` を使います。
- setup の build 時設定は `rocm_root()` が選んだ root を `HIP_PATH` に上書きします。これは利用者が起動前に設定する値の解釈とは別の処理です。
- packaging の検索先として使うのは Windows target の場合だけです。既定検索先にディレクトリが追加されても、依存 DLL が実際に見つかったときだけコピー対象になります。

## 実行時の詳細

HIP backend の child environment を作るとき、Strata は `HIP_PATH`、`HIP_DEVICE_LIB_PATH`、`LLVM_PATH` を順に確認します。`HIP_PATH` が空でないのに `Path(value).exists()` が偽なら、環境辞書からそのキーを削除し、`strata serve: AMD: HIP_PATH=<値> does not exist: not passed to the engine` を stderr に出します。空か有効なパスならログを出さず、値を変更しません。親プロセスの `os.environ` はこの関数では変更されません。

その後 `child_env()` の返却値が `StrataEngine` 起動に渡されます。直接の serve 起動と replica 起動の両方がこの経路を使います。`HIP_PATH` に有効な値があるとき、または空文字のとき、Strata はそれを保持して子に渡します。

## 文書との照合

`docs/STRIX_HALO.md` は ROCm の build 環境例として `HIP_PATH` を設定しています。`docs/DETAILS.md` と `docs/AMD_HIP.md` には、この serve 時の存在確認・削除・警告の挙動は見当たりません。ソースで確認できるのは Strata が子プロセス用環境から削除するところまでで、HIP runtime 側の効果はここでは判断しません。

## 根拠

- `serve/server.py:3499-3537` — 親環境の複製、config `env` の上書き、HIP backend に限る guard 呼び出し。
- `serve/server.py:3548-3578` — 空でない `HIP_PATH` の存在確認、削除、stderr 文言。
- `serve/server.py:7980-7984,8344-8352` — replica engine と通常の Strata engine の起動で `child_env()` を利用。
- `packaging/package_engine.py:236-246,249-255` — Windows target の default search に `HIP_PATH/bin/x64` と `HIP_PATH/bin` を追加し、明示検索先との優先を決める処理。
- `setup.py:4619-4625,4690-4695,4842-4846` — HIP engine / image engine build 前に `HIP_PATH` を ROCm root に設定。
- `docs/STRIX_HALO.md:56` — ROCm build 環境の設定例。
