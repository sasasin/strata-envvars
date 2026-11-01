# `TRANSFORMERS_OFFLINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata は `TRANSFORMERS_OFFLINE` を自プロセスの設定として読み取らず、値の parse や有効・無効の判定もしません。サーバーの `--offline` が有効なとき、Strata エンジンなどの子プロセスへ渡す環境に `TRANSFORMERS_OFFLINE=1` を設定します。`--offline` が無効なときは、親環境または設定の `env` にこの名前があれば、その値を子プロセスへ引き継ぎます。

## 値と判定

| サーバーの状態 | 子プロセスに渡す値 |
|---|---|
| `--offline` なし | `os.environ` を複製し、設定の `env` が同名キーを含めばその文字列値で上書きした結果。Strata は内容を解釈しない。親・設定のいずれにもなければ未設定。 |
| `--offline` あり、通常経路 | `strata_control.offline.OFFLINE_ENV` に定義された文字列 `"1"`。親環境や設定 `env` の値より優先する。 |
| `--offline` あり、ポリシーモジュールの import に失敗 | fallback として文字列 `"1"` を設定する。 |

空文字、`0`、その他の文字列に対する Strata 独自の変換・拒否・fallback はありません。通常経路では値を比較せず辞書にコピーし、offline 経路では既存値を定数 `"1"` で置き換えます。

## 有効になる条件

- `serve/server.py` の Strata エンジン起動経路で `--offline` を指定したときに適用されます。CLI の `--offline` はフラグ引数です（`serve/server.py:9000-9001`）。
- `--offline` 指定時に MCP サーバーまたは `before_load` コマンドがあると起動前に拒否し、オフライン非対応の profile 条件もポリシー判定後に拒否します。これらの拒否は `TRANSFORMERS_OFFLINE` の値ではなく `--offline` によります（`serve/server.py:9172-9184`）。
- 単一エンジン、replica、split の各 Strata エンジン起動で `offline` 状態を `child_env` に渡します（`serve/server.py:8710,8777,9193,9274-9279`）。backend、OS、GPU、build macro による `TRANSFORMERS_OFFLINE` 固有の分岐はありません。
- サーバーが `--offline` なしで起動した場合、この名前を `--offline` の代わりに使うことはありません。子プロセスへの値の引き継ぎだけが行われます。

## 実行時の詳細

`child_env()` は呼び出し時の `os.environ` を複製し、profile の `env` を文字列化して反映します。その後 `offline=True` ならポリシー辞書を最後に適用するため、profile が `TRANSFORMERS_OFFLINE` を空文字や `0` に指定していても、子プロセスへは `1` が渡ります。ポリシーモジュールを import できない場合も `1` を直接設定します（`serve/server.py:3747-3777`, `strata_control/offline.py:47-60`）。

通常の Strata エンジン起動では、その辞書を `StrataEngine` に渡し、`popen()` の `env` として子プロセスに渡します（`serve/server.py:9191-9194,9278-9279,1017-1019,1076-1079`）。vision encoder も `vision_env(cfg, env)` を通じて同じ環境辞書を受け取り、`Vision` の `popen()` に渡します（`serve/server.py:3921-3946,9202-9224,2844-2850`）。replica / split 経路も各エンジンの起動時に `child_env(..., offline=offline)` を使います（`serve/server.py:8704-8710,8768-8777`）。エンジン再起動用には起動時の環境辞書が `self.spawn` に保存されるため、同じサーバープロセス内で親環境を書き換えても、その既存エンジンの再起動環境は更新されません（`serve/server.py:1017-1019`）。値を読む static cache はありません。

`strata_control.offline.child_environment()` にも同じポリシー辞書を適用する処理がありますが、調査対象 commit の本番コードからの呼び出しは見つかりませんでした（定義 `strata_control/offline.py:122-136`、参照は `tests/tuning/test_offline.py` のテスト）。サーバーの実経路は `serve/server.py:3747-3790` の `child_env()` です。

この変数についての Strata 固有ログ、警告、終了・失敗経路はありません。offline profile の拒否時には `argparse` のエラーとして `--offline requires MCP servers and before_load commands to be disabled in this profile`、または `--offline cannot be strict for this profile: ...` が出ますが、これも変数の値を評価した結果ではありません（`serve/server.py:9173-9184`）。子プロセス側や外部ライブラリが `TRANSFORMERS_OFFLINE` をどう解釈するかは、本調査の対象外です。

## 根拠

- 変数名・値の定義: `strata_control/offline.py:44-60`
- 子環境の作成、profile 値の後勝ち適用、import fallback: `serve/server.py:3747-3790`
- `--offline` 引数、profile preflight、通常エンジン / vision encoder への env 受け渡し: `serve/server.py:9000-9001,9172-9194,9202-9224,9273-9279`
- replica / split の各子プロセスへの env 受け渡し: `serve/server.py:8688-8710,8757-8777`
- エンジン起動と再起動用状態への環境保存、`popen` への受け渡し: `serve/server.py:1017-1019,1076-1079`
- 本番で呼び出されない共通 helper: `strata_control/offline.py:122-136`（呼び出し検索ではテストのみ）
