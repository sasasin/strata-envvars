# `STRATA_API_KEY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の Python HTTP サーバーでは、この値が inference API の認証キーになる。キーが設定されると、認証を通らない API リクエストには HTTP 401 を返す。設定しない場合もサーバーは起動できるが、ネットワーク公開時にはキーなしの警告が出る。サーバーのほか、Terminal の接続・benchmark コマンドや同梱 HIP prefill benchmark が、接続先へ送る認証情報として同名を読む経路がある。GPU backend やモデル状態による有効条件はない。サーバーの判定と認証は `terminal/serve/server.py`、キー書式の処理は `terminal/serve/server_parts/http_api.py` にある。`docs/DETAILS.md:710-722` もネットワーク公開時の推奨、キーなし運用、複数キーを説明しており、以下の起動時検証と一致する。

## 値と判定

サーバーは argparse の `--api-key` 既定値として起動時に `os.environ.get("STRATA_API_KEY", "")` を読み、空白だけの環境値が明示されている場合は起動前に拒否する。優先順は `--api-key` 引数、環境変数、設定ファイルの `api_key`、キーなし。CLI 引数で環境値を置き換えられるが、環境変数が空白だけなら CLI 引数を指定しても別の空値検査で終了する。`terminal/serve/server.py:9202-9204,9326-9339`。

| サーバー入力 | 判定と結果 |
|---|---|
| 環境変数 unset | `--api-key` の既定値は空文字。設定ファイルの `api_key` があればそれを使い、なければキーなし。 |
| 空文字または空白だけ | 変数が存在し `.strip()` が空なら、stderr に `[strata] an API key was given but it is empty: set a key, or leave it out` を出して終了コード 2。前後の空白だけでなくタブ等も空扱い。 |
| `none`（大文字小文字不問、前後空白可） | `explicit_no_key` が意図的なキーなしとして扱う。環境変数値全体が ` none ` / `NONE` 等の場合。 |
| 通常の非空文字列 | `api_key_of` が前後空白を除去。カンマ区切りなら `key_list` が各要素を trim し、空要素を落として複数キーとして扱う。例: `alpha, beta` は2キー、`alpha,` は1キー。 |
| カンマ区切りの結果が空 | `,` や空白要素だけなら `[strata] an API key was given but it is empty: set a key, or leave it out` を stderr に出し終了コード 2。 |
| 設定値の `none` 以外の値 | 数値や `true` / `false` として parse せず、文字列キーとして扱う。キー照合は大文字小文字を区別する。文字列中の内部空白は保持される。 |

書式上の区切りはカンマで、キーにカンマを含める用途は設定ファイルの配列形式が案内されている。環境変数からの値は配列には変換されず文字列として処理される。`terminal/serve/server_parts/http_api.py:211-225,238-253`。

サーバーの設定ファイル `api_key` は、環境変数・引数が空のときの fallback であり、`api_keys` による追加キーは設定配列から別途加わる。`STRATA_TELEMETRY_KEY` はテレメトリー用の別キーで、inference キーと重複するとサーバー起動は stderr のエラーと終了コード 2 になる。`--no-api-key` を指定すると `no_key_chosen` が true になり `api_keys` との併用は拒否されるが、現行コードではそれ自体が `preflight_api_key` を空にしない。環境変数または設定ファイルでキーが選ばれていればサービスにはそのキーが設定される。キーなしを明示する値は `api_key: "none"` または `STRATA_API_KEY=none`。`terminal/serve/server.py:9331-9339,9568-9593`。

## 有効になる条件

- サーバー経路では、`terminal/serve/server.py` を起動して API リクエストを受けること。OS、CUDA/HIP/SYCL backend、モデルのロード状態はキー設定自体の条件ではない。キーはモデル読み込み前に検証・サービスへ設定される。`terminal/serve/server.py:9202,9326-9339,9566-9584`。
- CLI の `--api-key` があれば環境値より優先される。さらに設定ファイルの `api_key` は、選択された CLI 引数値が空のときの fallback。ただし環境変数が設定済みの空文字・空白だけの場合はこの fallback に進まず、上記の終了になる。`terminal/serve/server.py:9326-9339`。
- `api_key: "none"` は意図したキーなし運用。`--no-api-key` はヘルプにキーなしと記載されるが、現行実装では環境値や設定のキーを消さないため、キーが有効な状態では認証が残る。キーなし経路ではホスト名とブラウザー Origin の保護分岐が引き続き適用される。`terminal/serve/server.py:9205-9207,9331-9339,9568,7138-7179`。
- Terminal の接続コマンドでは通常 `STRATA_API_KEY` が credential 環境変数の既定値。`--credential-env` または保存済み connection の `credential_env` が別名を指定すればその変数を読み、`--url` はサーバーURLを選ぶだけでキーの既定名を変えない。monitor/status 等は同名キーか指定キーをリクエストに使う。`terminal/strata_cli/connections.py:273-301`、`terminal/strata_cli/monitor_commands.py:195-204`。
- `strata bench run` は `--credential-env` の既定を `STRATA_API_KEY` とし、明示した別名を使える。standard suite では指定環境値が空扱いなら、profile の設定ファイル `api_key` が代わりに使われる。`terminal/strata_cli/cli.py:340-341,1319-1342`。
- `strata launch --api-key-env STRATA_API_KEY` は明示的にこの名前を指定した場合だけ値を読む。空または未設定なら `The environment variable ... is empty or not set.` の `ValueError` 経路となる。`--api-key` と両方を指定した場合は env 読み取りが後なので環境値が採用される。`terminal/strata_cli/launch/cmd.py:137-138,288-299`。
- Docker 内の wrapper は `STRATA_API_KEY` が空の場合に限り、`STRATA_KEY_FILE`（既定 `/data/state/api-key`）の内容を読んで同名環境変数として export してから Terminal を起動する。`tools/docker/strata-wrapper.sh:4-9`。

## 実行時の詳細

サーバーでは argparse parser 作成時に環境値を既定値へ取り込み、その後の空値検査・`api_key_of` 検証を起動時に一度行い、`svc.api_key` に保存する。リクエストごとに環境を再読込する処理はなく、同一サーバープロセス中に環境値を変更しても設定済みキーは変わらない。設定されたキーがある場合、`/v1/*` の認証で `Authorization: Bearer ...`（または `x-api-key`）を照合し、不一致・欠落には HTTP 401 と `missing or wrong API key` を返す。キーなしなら `_authorized` は認証を要求しない。`terminal/serve/server.py:9202,9326-9339,9568,7283-7294`。

キーなしの場合も DNS rebinding 対策として許可されない Host を HTTP 403 にし、別サイト Origin の `/v1` API 要求も HTTP 403 にする（POST の許可 Origin では JSON content type を要求）。これらはキーなし経路に限る。ネットワーク bind でキーがなければ起動時に警告する。`terminal/serve/server.py:7138-7179,9730-9740`。

Terminal の client 側は各コマンド実行時に `os.environ.get(...)` でキーを読み、設定された endpoint に Bearer credential として渡す。status 等では credential の有無を表示情報に含める処理があり、接続先の応答が必要な操作はキー不足・不一致を server 応答として受ける。benchmark の managed profile 起動では `STRATA_API_KEY` を worker に継承させず、生成した `api_key` を run config に入れる経路がある。`terminal/strata_cli/cli.py:1325-1342`、`terminal/strata_control/benchmarking.py:210-220`、`terminal/strata_control/tune_session.py:550-560`。

## ログと測定値

- 空の明示値: stderr `[strata] an API key was given but it is empty: set a key, or leave it out`、終了コード 2。無効な書式のキー: stderr に `api_key_of` の `ValueError` 文言を付け、終了コード 2。`terminal/serve/server.py:9326-9339`。
- キーなしで config に空 `api_key` が明記されていると stderr に `the api_key in the config is empty...` を出す。ネットワーク bind でキーがなければ stdout に `no API key: anyone who can reach port ... can use the model` の警告を出す。`terminal/serve/server.py:9595-9597,9738-9740`、警告文生成 `terminal/serve/server_parts/http_api.py:228-235`。
- 認証失敗は HTTP 401 JSON `missing or wrong API key`。キーなしで不許可 Host または Origin の要求は HTTP 403。`terminal/serve/server.py:7150-7154,7171-7174,7283-7294`。
- この変数による性能測定値は、対象ソースと参照資料に記載がない。

## 根拠

- `terminal/serve/server.py:9202-9207,9326-9339,9568-9597,9726-9740` — サーバーの読取、優先順、検証、設定、観測結果。
- `terminal/serve/server.py:7138-7179,7283-7305` — キーあり・なしで異なるリクエスト認証と保護。
- `terminal/serve/server_parts/http_api.py:211-253` — カンマ分割、`none` 判定、trim と空キー拒否。
- `terminal/strata_cli/connections.py:273-301`, `terminal/strata_cli/monitor_commands.py:195-204` — Terminal の既定・動的 credential 環境変数。
- `terminal/strata_cli/cli.py:340-341,825-831,1319-1342`, `terminal/strata_control/readiness.py:42-52`, `terminal/strata_control/benchmarking.py:210-220` — profile 検証、readiness、benchmark クライアントでの利用。
- `terminal/strata_cli/launch/cmd.py:137-140,288-301`, `terminal/strata_cli/launch/runner.py:725-739` — launch の明示的な環境変数指定と設定ファイル化。
- `terminal/strata_control/tune_session.py:550-560`, `tools/docker/strata-wrapper.sh:4-9`, `terminal/tools/hip/bench_prefill.py:34-40` — worker からの除去、Docker 内の補完・転送、同梱 benchmark の任意 Bearer header。
- `docs/DETAILS.md:710-730,1046-1052` — サーバーの公開・複数キーとクライアント設定例。コードと説明の矛盾は見つからなかった。
