# `LLVM_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata のサーバーは HIP backend の子エンジン用環境を作るとき、`LLVM_PATH` が空でなく、指すパスが存在しない場合にその項目を環境から削除し、stderr に通知します。存在するパスはそのまま子エンジンへ渡します。このコードは値を LLVM の場所の選択や検証に使わず、ファイル種別や中身も調べません。子エンジンや HIP runtime が受け取った値をどう使うかは、この調査の対象外です。

## 値と判定

`child_env()` はまずサーバーの `os.environ` をコピーし、その後設定ファイルの `env` 項目を文字列化して同名キーにも上書きします。HIP backend の場合だけ `hip_env_guard()` が `env.get("LLVM_PATH")` を見ます（`serve/server.py:3747-3760,3782-3783`）。

| 子環境の値 | Strata の処理 |
|---|---|
| キーなし | 何もしない。 |
| 空文字 | 偽として扱われ、パス検査も削除も行わない。空文字のキーは子環境に残る。 |
| 空でない値で、存在するパス | そのまま残し、子エンジンへ渡す。ファイルかディレクトリかは判別しない。 |
| 空でない値で、存在しないパス | キーを削除し、`LLVM_PATH=<値> does not exist: not passed to the engine` と記録する。 |

文字列の parse、大小文字変換、空白除去、正規化、長さや数値の境界判定はありません。パスの有無は `Path(v).exists()` の結果で決まり、存在しない値は警告扱いで除去されます（`serve/server.py:3823-3827`）。

## 有効になる条件

- `child_env()` が呼ばれ、`cfg["backend"] == "hip"` の場合に限り検査します。HIP 以外の backend ではこの guard は呼ばれず、コピー元の環境または設定ファイルで指定された値がそのまま環境辞書に残ります（`serve/server.py:3782-3783`）。
- 通常の `--engine strata` 起動で環境を作り、StrataEngine に渡します（`serve/server.py:9186-9194,1077-1079`）。split serving では prefill/decode の各エンジン、replica serving では各 replica について `child_env()` を呼びます（`serve/server.py:8704-8710,8770-8777`）。
- 同名キーが設定ファイルの `env` にあれば、継承環境をコピーした後で設定値が優先します。したがって設定側が空文字なら継承側の値にかかわらず guard は削除しません（`serve/server.py:3750,3759-3760,3823-3827`）。この guard に CLI 引数との優先順位はありません。

## 実行時の詳細

チェックは子プロセスの環境辞書を作るたびに実行されます。値はモジュール静的変数などには cache されません。作成された辞書は `StrataEngine` の `popen(..., env=env)` に渡されるため、その後に親プロセスの環境が変わっても、すでに起動したエンジンの環境には反映されません（`serve/server.py:3747-3750,3782-3783,1077-1079`）。

存在しない非空パスがあれば、guard はキーを削除して変更内容を返し、`strata serve: AMD: LLVM_PATH=<値> does not exist: not passed to the engine` を stderr に flush します。これは警告と環境値の除去であり、guard 自体は起動を拒否しません（`serve/server.py:3823-3827,3843-3845`）。有効なパスや空文字についてはこの変数に関するログを出しません。

## 根拠

- `serve/server.py:3747-3760,3782-3783` — 継承環境のコピー、設定 `env` の上書き、HIP backend での guard 呼び出し。
- `serve/server.py:3815-3827,3843-3845` — `LLVM_PATH` を含む検査、削除条件、stderr の文面。
- `serve/server.py:8704-8710,8770-8777,9186-9194,1077-1079` — replica / split / 通常起動での環境生成と子エンジンへの引き渡し。
- `docs/TROUBLESHOOTING.md:305-310` — Windows HIP 起動時の説明。実際の処理条件とログ文面の根拠は上記コード。
