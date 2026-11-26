# `TRANSFORMERS_OFFLINE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata 自身はこの名前を環境から読み取らず、`strata serve --offline` の子プロセス環境へ文字列 `"1"` を設定する。Python サーバーから engine へ渡すオフライン方針の一項目であり、通常の `serve` はこの値を設定しない。設定先の外部ランタイムがこの値をどう解釈するかは Strata の挙動として扱わない。設定処理は `terminal/serve/server.py` の `child_env` と `terminal/strata_control/offline.py` の `OFFLINE_ENV` にある（`terminal/serve/server.py:4007-4049`, `terminal/strata_control/offline.py:42-59`）。

`--offline` は画像 URL の取得拒否や MCP / `before_load` の起動拒否も有効にするが、これらは `TRANSFORMERS_OFFLINE` の値を読む処理ではなく、サーバー内の別の分岐である（`terminal/serve/server.py:9189-9190,9373-9384,9497`; `docs/TERMINAL.md:245`）。

## 値と判定

Strata による `TRANSFORMERS_OFFLINE` 自体の読み取り・文字列 parse はない。`child_env` は親環境をコピーし、config の `env` を文字列化して重ね、`offline=True` の場合に最後にオフライン環境一式を上書きする。したがって Strata にとって `0`、`true`、空文字、その他の値に有効・無効の解釈はなく、strict offline 時に限り設定値が必ず `"1"` になる（`terminal/serve/server.py:4010,4027-4028,4037-4049`）。

| `child_env` の条件 | 親の値が未設定 | 親または config の値が `""` / `"0"` / `"true"` / その他 |
|---|---|---|
| `offline=True` | `"1"` を設定 | 元の値を `"1"` で上書き |
| `offline=False` | 親環境由来の値は未設定のまま（ただし config の `env` に指定があればその値を設定） | 親環境または config の値をそのまま引き継ぐ。真偽値判定・正規化なし |

## 有効になる条件

- 有効化の根拠は `TRANSFORMERS_OFFLINE` の設定有無や内容ではなく、サーバーの `offline` 引数である。直接の server CLI では `--offline` が指定された場合に true になる（`terminal/serve/server.py:9189-9190`）。
- Strata CLI はコマンドライン指定、保存済み profile、run config、既定値 `false` の順で `offline` を決め、true の場合に server 引数へ `--offline` を追加する。CLI で省略された `false` は未指定扱いとなり、保存済み profile や run config の値を使う（`terminal/strata_cli/cli.py:783-803,835-843`）。
- `--offline` で MCP server または `before_load` コマンドを構成している場合、起動前に parser error で拒否する。offline policy が remote image source を検出した場合も拒否する（`terminal/serve/server.py:9373-9384`; `terminal/strata_control/offline.py:137-164`）。
- 実際の `child_env` 適用先は `--engine strata` の engine 起動で、単一 engine、replica、split、split fallback の各経路が `offline` 状態を渡す。`--engine mock` はこの Strata engine 子プロセス経路を使わない（`terminal/serve/server.py:8820,8850-8852,8918-8919,9386-9394,9472-9477`）。
- 画像 encoder は通常 engine 環境を引き継ぐが、`vision.env` はその後に重ねられるため、ここで同名のキーを指定すれば encoder 向け値は上書きされる。これは engine の `child_env` で設定した値には影響しない（`terminal/serve/server.py:4134-4156,9422-9423`）。

## 実行時の詳細

`child_env` 呼び出しごとに親プロセスの `os.environ` をコピーして環境辞書を作る。設定を static cache する処理はなく、サーバー起動時に作られた辞書が engine 起動へ渡る。`offline=True` では profile の `env` 指定より後に `OFFLINE_ENV` を適用するため、profile が `TRANSFORMERS_OFFLINE` を別値にしても engine 向け値は `"1"` になる（`terminal/serve/server.py:4007-4028,4037-4049`）。

この値は server 自身の `TRANSFORMERS_OFFLINE` を切り替えず、起動した子の環境だけに設定される。通常起動で親が設定済みの場合は、config の top-level `env` に上書きがなければ値が子へそのまま継承される。実行中に親環境が変わることを再読する箇所はない（`terminal/serve/server.py:4010,4027-4049`）。

## ログと測定値

`TRANSFORMERS_OFFLINE` の設定・上書きだけを示すログはない。offline preflight が構成を拒否する場合、`argparse` の parser error として `--offline requires MCP servers and before_load commands to be disabled in this profile` または `--offline cannot be strict for this profile: ...` を出す（`terminal/serve/server.py:9373-9384`）。画像要求に HTTP(S) URL が含まれる場合は `offline mode cannot download an image URL` または `offline mode cannot download an image URL; send a data: image instead` の拒否経路がある（`terminal/serve/server.py:5501-5502,5562-5573`）。これらのログ・拒否は同名環境変数の値を parse した結果ではない。

## 根拠

- `terminal/serve/server.py:4007-4049` — 子環境の構築、config 環境値の適用順、strict offline 時の上書きと ImportError fallback。
- `terminal/strata_control/offline.py:42-59,120-134` — `OFFLINE_ENV` の値と helper の環境辞書処理。
- `terminal/serve/server.py:9189-9190,9373-9394,9472-9497` — `--offline`、preflight、engine 起動経路と Service への状態設定。
- `terminal/strata_cli/cli.py:783-843` — CLI / saved profile / run config / default の優先順位と server 引数への変換。
- `terminal/serve/server.py:4134-4156,9422-9423` — vision encoder が engine 環境を継承し、専用 `vision.env` を後から重ねる処理。
- `terminal/serve/server.py:5501-5502,5562-5573`; `docs/TERMINAL.md:245` — offline 時のリモート画像 URL 拒否。
