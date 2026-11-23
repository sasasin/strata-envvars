# `PYTHONIOENCODING`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

調査した Strata 所有コードには、この名前の値を環境から読み取って Strata 自身の分岐に使う箇所はない。一方、ホスト・CLI・同梱ツールが Python 子プロセスを起動するとき、子プロセス用環境へ `PYTHONIOENCODING` を文字列 `utf-8` として設定する箇所が複数ある。したがって Strata 側で確認できる役割は、起動する子プロセスへ値を設定・転送することまでであり、Python ランタイムがその値をどう扱うかは本書の対象外である。

Node ホストの `sourceServerEnvironment` と `controlEnvironment`、同モジュールの `runCli` / `installerEnvironment` を通る Control CLI、tuning CLI、native-control の自動調整・操作プロセス、Time-skip CLI、Python launch runner、`strata_mcp.py` のインストール・サーバー起動・セットアップ子プロセスで設定する。既存環境を spread / `dict` コピーした後に固定値を指定する箇所では、呼び出し元から受け取った値を `utf-8` で上書きする（例: `app/host/server/control-runtime.mjs:82-85,89-100,114-119,140-146`、`terminal/strata_cli/launch/runner.py:969-974`）。

## 値と判定

Strata は値を真偽値や文字列として判定しない。確認できたすべての本番コード設定箇所で子プロセス環境の値を `utf-8` に固定する。設定値を `0`、`1`、`true`、`false`、空文字などにした場合の Strata 内の分岐はない。

| 経路 | 親環境での状態 | 子プロセスに渡す値 |
|---|---|---|
| `sourceServerEnvironment`、`controlEnvironment`（およびこれを使う `runCli` / `installerEnvironment`）、tuning / Time-skip / native-control の通常 Python 起動、`strata_mcp.py` の各起動 | 未設定・空文字・その他の値 | `utf-8` に設定（Time-skip の detached 起動では後続の `extraEnv` が同名キーを指定すればその値で上書き） |
| Python launch runner の既定環境 `_env()` | 未設定・空文字・その他の値 | `utf-8` に設定。`_spawn(..., env=...)` に明示環境が渡されるとその環境を使用 |

根拠: `app/host/server/control-runtime.mjs:82-100,114-119,140-146`、`app/host/server/index.mjs:890-895`、`app/host/server/native-control.mjs:142,197-202,735-742`、`app/host/server/timeskip.mjs:313-321,457-467`、`terminal/strata_cli/launch/runner.py:969-979`、`terminal/tools/strata_mcp.py:2741-2743,2799-2809,3151-3157`。

## 有効になる条件

- この値の設定は、該当する Python 子プロセスを Strata の該当経路が起動するときに限られる。単に Strata を起動しただけで全プロセスの環境を書き換える処理ではない。
- `sourceServerEnvironment` はソース checkout からホストが起動するサーバー環境を作る。`controlEnvironment` は Control 用環境を作る。native-control の自動調整は packaged と source checkout でそれぞれ異なる環境生成経路を使う（`app/host/server/native-control.mjs:140-145`）。
- Time-skip の detached 起動は `{ ...env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', ...extraEnv, ... }` の順で環境を構成するため、`extraEnv.PYTHONIOENCODING` があれば `utf-8` を上書きできる。通常の `runCli` ではその上書き引数はなく `utf-8` となる（`app/host/server/timeskip.mjs:313-321,457-467`）。
- runner の `_spawn` は `env` 引数が truthy ならそれを子プロセス環境として使い、未指定なら `_env()` を使う（`terminal/strata_cli/launch/runner.py:969-979`）。
- OS・GPU backend・build macro・モデル状態による値の判定はない。これらの条件を Strata が本変数について検査するコードは見つからなかった。

## 実行時の詳細

子プロセス生成時に環境辞書を組み立てて渡す。Strata が親プロセスの `PYTHONIOENCODING` を読み出して保持する処理や、実行中に再評価する処理はない。該当経路では環境辞書の生成時に固定値を設定し、子プロセス起動時に適用する。親プロセスで後から値を変更した場合に既に起動済みの子へ反映する処理もない。

具体例として、`strata_mcp.py` はインストール job、native server、setup 子プロセス用に `dict(os.environ, ..., PYTHONIOENCODING="utf-8")` を作り、その環境を起動関数へ渡す（`terminal/tools/strata_mcp.py:2741-2743,2804-2809,3151-3157`）。CLI runner は `Popen` に `_env()` または明示環境を渡す（`terminal/strata_cli/launch/runner.py:976-980`）。

## ログと測定値

この変数の値を理由に出すログ、警告、終了・失敗経路や測定値は見つからなかった。子プロセスの起動失敗などの処理は各起動経路に存在するが、`PYTHONIOENCODING` の値に応じたものではない。

## 根拠

- `app/host/server/control-runtime.mjs:82-100,114-119,140-146` — サーバー・Control 用環境の生成、installer・Control CLI helper への伝播。
- `app/host/server/index.mjs:886-895` — tuning CLI 起動時に環境へ設定。
- `app/host/server/native-control.mjs:140-145,197-205,735-742` — native-control の起動経路と子プロセス環境。
- `app/host/server/timeskip.mjs:313-321,457-467` — 通常・detached CLI 起動と `extraEnv` の上書き順。
- `terminal/strata_cli/launch/runner.py:969-979` — runner の既定環境と `Popen`。
- `terminal/tools/strata_mcp.py:2741-2743,2799-2809,3151-3157` — installer、server、setup の子プロセス環境。

`rg -n --hidden --glob '!.git/**' 'PYTHONIOENCODING'` で候補名の全参照を調べた。上記の本番コード以外に、`tools/bench/bench_vs_llama.py:96` と `docs/bench-results/...` にあるベンチマーク用設定、および `terminal/tests` / `terminal/tools/test_*` のテスト用設定がある。これらは本番実装の根拠にしていない。Strata 本番コードによる環境値の読み取りは見つからず、子プロセス環境への設定・転送のみ確認した。
