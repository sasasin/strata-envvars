# `HF_HUB_OFFLINE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の serve サーバーはこの変数を読み取って動作を切り替えない。`--engine strata` の起動時に engine 子プロセス用環境を組み立て、`--offline` が指定された場合に限り、環境変数 `HF_HUB_OFFLINE` を子プロセスへ文字列 `"1"` として設定する。これは `OFFLINE_ENV` に含まれる値であり、モデル loader 等の子プロセスに strict offline 方針を渡すための設定である。Strata が Hugging Face 側の動作を実行・保証するものではない。通常起動では親プロセスの値を引き継ぎ、設定ファイルの `env` があればその値で上書きする。`terminal/strata_control/offline.py:42-59`、`terminal/serve/server.py:3870-3912`。

この環境値を判定する Strata 内の `getenv` / `os.environ` 読み取り箇所は見つからなかった。Strata サーバーが読むスイッチは CLI の `--offline` であり、`HF_HUB_OFFLINE` 自体は子プロセス環境への設定・転送にのみ使われる。`terminal/serve/server.py:8671-8674,8857-8868`。

## 値と判定

Strata は `HF_HUB_OFFLINE` の値を parse しない。したがって `0` / `1`、`true` / `false`、大文字小文字、空白、空文字、`0anything` といった値の真偽判定や数値変換はない。子プロセスへ渡す値は起動モードと設定元で決まる。

| 起動条件 | 親環境で unset | 親環境が空文字 | 親環境が `0` / `false` 等 | `cfg.env` に同名キーがある場合 |
|---|---|---|---|---|
| `--engine strata`、`--offline` あり | 子には `"1"` を設定 | 子には `"1"` を設定 | 子には `"1"` を設定 | 設定ファイルの値を文字列化した後、子には `"1"` を設定 |
| `--engine strata`、`--offline` なし | unset のまま | 空文字を引き継ぐ | 元の文字列を引き継ぐ | 設定ファイルの値を `str()` で文字列化して親環境値を上書き |
| `--engine mock` | HF 用 engine 子環境を作らない | 同左 | 同左 | 同左 |

`child_env()` は `os.environ` のコピーを作り、`cfg.env` の各値を `str()` にして上書きする。strict offline の値設定はその後に行うため、設定ファイルの指定や親環境値より `--offline` が優先される。`--offline` がない経路ではこの関数は既存値を検査・削除しない。`terminal/serve/server.py:3870-3912`。

`terminal/strata_control/offline.py:120-134` の `child_environment()` は offline 無効時に `OFFLINE_ENV` のキーを取り除く実装だが、全参照を調べた範囲で本番コードからの呼び出しはない（参照はこの定義とテストのみ）。serve の本番経路は `child_env()` を使うため、offline 無効時の同名値は上表のとおり残る。`terminal/strata_control/offline.py:120-134`、`terminal/serve/server.py:3870-3912`。

## 有効になる条件

- Strata の serve を `--engine strata` で起動すること。`--engine` の既定値は `mock` であり、`mock` は Strata engine 用の `child_env()` 経路に入らない。`terminal/serve/server.py:8641-8644,8870-8878`。
- 子へ `"1"` を設定する条件は `HF_HUB_OFFLINE` の値ではなく CLI の `--offline`。このオプションは strict offline の事前条件も検査する。MCP server または `before_load` command があると `--offline requires MCP servers and before_load commands to be disabled in this profile` で拒否し、`images` / `vision` の `remote_sources`、`allowed_hosts`、`url` 等がネットワークを許す場合は `--offline cannot be strict for this profile: ...` で拒否する。`terminal/serve/server.py:8857-8868`、`terminal/strata_control/offline.py:137-164`。
- GPU backend、OS、build macro、モデルのロード状態による `HF_HUB_OFFLINE` 固有の分岐は見つからない。`--offline` 時は選択された通常 engine、replica engine、split engine、および split fallback 用 engine の環境に設定される。`terminal/serve/server.py:8272-8308,8313-8336,8383-8403,8956-8961`。
- `--offline` 時に作った env は `vision_env()` 経由で画像 encoder にも渡される。`vision_env()` は GPU 可視性変数を調整することがあるが、`HF_HUB_OFFLINE` は変更しない。`terminal/serve/server.py:3997-4012,8906-8907`。

## 実行時の詳細

`--offline` は argparse の真偽フラグで、`HF_HUB_OFFLINE` の値を読む入口ではない。Strata engine 起動処理では `child_env(cfg, offline=a.offline)` が環境辞書を組み立て、`StrataEngine` はその辞書を `popen(..., env=env)` に渡す。通常 engine のほか、replica / split / fallback も同じ `offline` 状態を各 engine の `child_env()` に渡す。`terminal/serve/server.py:8671-8674,8875-8878,8272-8308,8313-8336,8383-8403`。

`child_env()` は起動時に親環境のコピーを作り、設定値を適用してから offline 方針を重ねる。Strata は `HF_HUB_OFFLINE` を定期的に読み直したり cache に parse 結果を保存したりしない。すでに作られた env 辞書は engine の spawn 情報に保持され、画像 encoder にも渡るため、親プロセスの環境を後から変えてもその辞書には反映されない。`terminal/serve/server.py:3870-3912,761,827-829,2938-2973,3114-3121,3997-4012`。

`--offline` が事前条件で拒否された場合、argparse のエラーとして標準エラーに上記の文言が出て起動処理を続けない。`HF_HUB_OFFLINE` の値が空・不正・`0` などであることを理由とする Strata の警告、ログ、終了、fallback はない。変数の設定そのものを示す専用ログもない。`terminal/serve/server.py:8857-8868,3900-3912`。

## 根拠

- `terminal/strata_control/offline.py:42-59` — 子プロセス向け `OFFLINE_ENV` の定義。`HF_HUB_OFFLINE` は文字列 `"1"`。
- `terminal/strata_control/offline.py:120-134` — offline 方針を子環境へ適用・除去する helper。本番呼び出し箇所はない。
- `terminal/strata_control/offline.py:137-164` — strict offline を許可しない profile 条件。
- `terminal/serve/server.py:3870-3912` — 親環境の複製、設定ファイル値の適用、offline 方針の最終上書きと import fallback。
- `terminal/serve/server.py:714-829` — engine 起動に環境辞書を `popen` へ渡す箇所。
- `terminal/serve/server.py:8671-8674,8857-8878` — `--offline` 定義、事前検査、engine 環境生成。
- `terminal/serve/server.py:8272-8308,8313-8336,8383-8403,8956-8961` — fallback / replica / split を含む各 engine 起動経路。
- `terminal/serve/server.py:2938-2973,3114-3121,3997-4012,8906-8907` — 画像 encoder に渡る環境と、HF 変数を変更しない可視 GPU 調整。
