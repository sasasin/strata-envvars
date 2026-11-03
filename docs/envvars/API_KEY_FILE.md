# `API_KEY_FILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象リポジトリの作業ツリーは `main` = `origin/main` で clean。

## 役割

Docker コンテナの entrypoint が API キーをファイルから読むための変数です。Docker secrets などでキーをファイルとして渡す用途が、`docs/DOCKER.md` に記載されています。Strata のサーバー本体が `API_KEY_FILE` を読むわけではありません。entrypoint がファイルの内容を `STRATA_LAUNCH_KEY` として `strata launch` に渡し、launch がその名前の環境変数からキーを取得します。

## 値と判定

| 条件 | entrypoint の処理 |
|---|---|
| `API_KEY` が空でない | `API_KEY_FILE` は参照せず、`API_KEY` の値をキーとして使う |
| `API_KEY` が未設定または空で、`API_KEY_FILE` が未設定または空 | ファイルを読まず、明示キーなしで launch を進める |
| 上記に当てはまらず、ファイルが読み取り可能 | 指定ファイルの内容から CR (`\r`) と LF (`\n`) をすべて削除し、結果をキーにする |
| `API_KEY` が空で、指定ファイルが読み取り不可・存在しない | stderr に `API_KEY_FILE=<値> cannot be read.` を出して entrypoint が終了コード 1 で停止する |

ファイルパスの前後空白を除く処理や、キー文字列の長さ・文字種の検査は entrypoint にはありません。読み取った値が空文字になった場合も明示キーとしては渡されません。CR/LF は行末だけでなく内容中にあるものも削除されます。

## 有効になる条件

この変数を読むのは Docker イメージの `/opt/strata/entrypoint.sh` です。`docker/Dockerfile` がこのスクリプトをイメージへ配置し、コンテナの `ENTRYPOINT` に設定しています。通常の Strata サーバー起動や Docker を介さない CLI 実行では、この変数を読む Strata コードは確認できません。

`API_KEY` に空でない値がある場合はそちらが優先されます。ファイルから得たキーが空の場合や、`API_KEY_FILE` 自体が空の場合、entrypoint は `--api-key-env` を追加しません。そのとき Docker 手順書に記載のとおり、launch が初回キーを作成して保存する経路になります。

## 実行時の詳細

entrypoint は `API_KEY` の値を先に `key` に設定し、空の場合に限って `API_KEY_FILE` の有無を調べます。ファイルが読めるかを `[ -r ... ]` で確認し、`tr -d '\r\n'` の出力を `key` に代入します。`key` が空でなければ launch 引数に `--api-key-env STRATA_LAUNCH_KEY` を加え、launch プロセスを起動するときだけ `STRATA_LAUNCH_KEY="$key"` を環境に設定します。このため、キー値自体はコマンドライン引数には載りません。

launch は `--api-key-env` の指定先を `os.environ.get()` で読みます。値が空または未設定なら `The environment variable STRATA_LAUNCH_KEY is empty or not set.` のエラーになり、空のキーを受け付けません。今回の entrypoint は空値ならオプション自体を付けないため、このエラーには進まず、launch のキー自動作成・既存 preset の処理に委ねられます。キーが渡された場合は launch の設定に採用され、生成された実行設定の `api_key` に保存されます。

## 根拠

- `docker/entrypoint.sh:162-167` — `API_KEY` 優先、`API_KEY_FILE` の空判定・読み取り可否・CR/LF 削除。
- `docker/entrypoint.sh:225-226,274-283` — `key` が空でない場合の `--api-key-env STRATA_LAUNCH_KEY` 追加と、launch 起動時の一時的な環境変数設定。
- `strata_cli/launch/cmd.py:138,279-291` — launch の `--api-key-env` 引数、環境値の読み取り、空値エラー、キー設定。
- `strata_cli/launch/runner.py:540-545` — launch が `api_key` を実行設定に反映する箇所。
- `docker/Dockerfile:87-89,133` — entrypoint の配置と Docker `ENTRYPOINT`。
- `docs/DOCKER.md:126,159-166` — Docker 変数表と `API_KEY_FILE` を Docker secrets 用に使う説明、キー未指定時の動作。
