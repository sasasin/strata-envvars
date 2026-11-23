# `DO_NOT_TRACK`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の `DO_NOT_TRACK` 参照は値を読む処理ではなく、サーバーの `--offline` 実行時にエンジンなどの子プロセスへ `DO_NOT_TRACK=1` を設定して渡す処理である。Strata 自身がこの変数を参照して動作を変える実装は確認できないため、Strata がテレメトリーを停止する等の効果は断定できない。設定箇所は `terminal/strata_control/offline.py` の `OFFLINE_ENV`、適用箇所は `terminal/serve/server.py` の `child_env`。`--offline` はサーバー CLI のフラグである。(`terminal/strata_control/offline.py:42-59`; `terminal/serve/server.py:3870-3906,8673-8674`)

## 値と判定

Strata は `DO_NOT_TRACK` の既存値を真偽値として parse しない。`--offline` が有効なときは既存値が何であっても文字列 `1` で上書きする。`--offline` が無効なときは `child_env` が親環境のコピーを作り、設定の `env` 項目があればその値を文字列化して上書きする。したがって空文字、`0`、`true`、大文字小文字、空白、数値でない文字列を Strata が判定する規則はない。(`terminal/serve/server.py:3873,3890-3906`; `terminal/strata_control/offline.py:45-59`)

| サーバー実行条件 | 親環境の `DO_NOT_TRACK` | 設定 `env` の値 | 子プロセスに渡す値 |
|---|---|---|---|
| `--offline` あり | 未設定・空文字・任意の値 | 未指定・任意の値 | `1`（最後に強制設定） |
| `--offline` なし | 設定済み | 未指定 | 親環境の値を維持 |
| `--offline` なし | 任意 | 設定済み | 設定値を `str` で変換した値 |
| `--offline` なし | 未設定 | 未指定 | 未設定のまま |

## 有効になる条件

- `DO_NOT_TRACK=1` を強制設定するのは `terminal/serve/server.py` でサーバー CLI の `--offline` が真になり、`child_env(..., offline=True)` が呼ばれる経路である。`--offline` は `store_true` のため、指定しなければ偽。OS、GPU backend、build macro による値判定の分岐はない。(`terminal/serve/server.py:3870-3906,8673-8674`)
- `--offline` の通常の Strata エンジン経路では、起動時に `child_env` が生成した環境をエンジンへ渡す。レプリカ、split、fallback 起動でも `offline` を引き継いで `child_env` を呼ぶ。(`terminal/serve/server.py:8304-8308,8313-8336,8383-8403,8875-8878,8956-8961`)
- `--offline` なしの場合、Strata が `DO_NOT_TRACK` によって機能を有効化する条件はない。値の意味は子プロセス側の利用者に委ねられるが、その外部側の挙動は本調査の対象外。

## 実行時の詳細

`child_env` は呼び出しごとに `os.environ` のコピーを作り、設定 `env` の各項目を反映した後、strict offline 用の `OFFLINE_ENV` を適用する。この順序により、`--offline` 時にはプロファイルの `env` や親環境に同名キーがあっても `DO_NOT_TRACK=1` が優先される。子プロセスの起動時に渡される値であり、Strata 内に `DO_NOT_TRACK` 用の static cache や実行中の再読込処理はない。後から作られる子の環境はその時点の親環境を基に再構築されるが、既に起動した子の環境はこのコードでは変更されない。(`terminal/serve/server.py:3870-3906`; `terminal/strata_control/offline.py:42-59,120-134`)

`--offline` の事前検査で条件に合わないプロファイルは子プロセス起動前に拒否される。`hub`、`before_load` または MCP / リモート画像関連のプロファイル設定が該当する場合、CLI の `ap.error` 経由で起動が止まり、環境変数の転送には進まない。これは `DO_NOT_TRACK` の値による判定ではない。(`terminal/serve/server.py:8856-8868`; `terminal/strata_control/offline.py:137-164`)

## ログと測定値

`DO_NOT_TRACK` の設定・値・転送に固有のログ、警告、終了経路はない。`--offline` のプロファイル事前検査で拒否された場合は、たとえば `--offline requires MCP servers and before_load commands to be disabled in this profile` または `--offline cannot be strict for this profile: ` で始まるエラーが出るが、これらはプロファイル条件に関するもので、この変数の値を示すものではない。(`terminal/serve/server.py:8857-8868`)

測定値は該当しない。

## 根拠

- `terminal/strata_control/offline.py:42-59` — 子環境向け `OFFLINE_ENV` に `DO_NOT_TRACK: "1"` を定義。
- `terminal/serve/server.py:3870-3906` — 親環境のコピー、設定値反映、offline policy の最終上書き。
- `terminal/serve/server.py:8673-8674,8856-8868,8875-8878,8956-8961` — CLI フラグ、事前検査、エンジン起動への offline 状態伝播。
- `terminal/serve/server.py:8304-8308,8313-8336,8383-8403` — fallback / replicas / split の子エンジン起動でも offline 状態を `child_env` に渡す。
