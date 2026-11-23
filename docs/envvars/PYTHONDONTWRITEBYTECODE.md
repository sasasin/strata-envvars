# `PYTHONDONTWRITEBYTECODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の実行時機能が利用者の同名環境変数を読んで挙動を切り替える実装は見つからなかった。Strata がこの名前を設定するのは、主に配布物の検証・自己診断で起動する子プロセスの環境である。`tools/packaging/package_terminal.py` の `run_probe` は呼び出し元の環境を複製した後、この値を文字列 `"1"` で上書きして同梱 Python の import probe に渡す。同じ probe の起動引数には `-B` も含まれる（`tools/packaging/package_terminal.py:146-156,540-543`）。

Desktop の `--self-test` では `control_runs` と `control_engine_notice` が起動する Python 子プロセスにも `"1"` を設定する（`app/desktop/src-tauri/src/main.rs:688-704,706-728`）。ほかの参照は macOS の署名済み成果物 smoke test、Terminal staging check、開発用 check とテストの子プロセス環境の設定である（下記「根拠」参照）。これらは利用者向けの実行時設定ではなく、Strata が環境値を検査したり、モデル・backend・生成結果を切り替えたりするものではない。

## 値と判定

Strata の該当箇所は値を parse せず、環境マップまたは子プロセス設定へ固定文字列 `"1"` を入れる。したがって、ここに未設定・空文字・`0`・`true` などを Strata が有効／無効と判定する規則はない。

| Strata 経路 | 呼び出し元の値 | 子プロセスに設定する値 | Strata による判定 |
|---|---|---|---|
| Terminal packaging import probe | `os.environ` を複製するが、同名キーは常に上書き | `"1"` | なし。環境マップ構築時に固定値を設定 |
| Desktop self-test の control 子プロセス | `Command` に固定値を設定 | `"1"` | なし。親プロセスの値を参照しない |
| staging/check、smoke test、テスト用 subprocess | 固定値を設定する実装 | `"1"` | なし |

このため、親環境で未設定・空文字・`0`・`true`・大文字小文字違いを指定しても、上記の設定箇所では Strata の実装が子プロセス側へ渡す値を `"1"` にする。Python がその値をどう解釈するかは Strata の環境変数処理ではないため、ここでは説明しない。`run_probe` はさらに `-B` を渡すが、これは CLI 引数であり、この環境変数の値判定ではない（`tools/packaging/package_terminal.py:153-156`）。

## 有効になる条件

- 通常の Strata CLI、サーバー、engine の実行時に、この変数を読む分岐は見つからなかった。OS、CUDA/HIP/SYCL、build macro、モデル状態などで Strata 側の適用条件が変わる根拠もない。
- 値を設定するのは、Terminal の packaging import probe、Desktop の自己診断内の control 子プロセス、署名済み macOS app / Terminal の smoke test、staging/check、開発用またはテスト用 subprocess の各経路に限られる（`tools/packaging/package_terminal.py:146-156,540-543`; `app/desktop/src-tauri/src/main.rs:688-728`; `tools/packaging/mac/sign-and-notarize.sh:392-405,471-482`; `app/desktop/scripts/stage-control.py:145-168`; `tools/check:79-85`）。
- `run_probe` は呼び出し元環境を引き継ぎつつ同名キーを上書きする。他の列挙した設定箇所も固定値を明示しており、Strata が利用者の値を優先する経路はない。
- Python ランタイムがこの環境変数をどう扱うかは外部ランタイムの挙動であり、本調査の説明対象外。

## 実行時の詳細

この変数について Strata 内での読み取り時期・cache はない。Strata は各子プロセス起動時に環境を組み立てる。`run_probe` は `os.environ` を展開した辞書に固定値を設定し、`subprocess.run` に渡す。さらに `PYTHONHOME` と `PYTHONPATH` を辞書から除き、同梱 Python を `-B -c` で実行する（`tools/packaging/package_terminal.py:146-156`）。probe の終了コードが 0 以外で、かつ `--skip-deps` でない場合、packaging は `the bundled interpreter cannot import the runtime packages` で終了する（`tools/packaging/package_terminal.py:540-543`）。

Desktop の二つの control 呼び出しは、Python に `strata.py --version` または `strata.py components engine --backend cuda --output json ...` を渡して起動する。前者は起動失敗時に `could not start ...` を結果文字列にし、後者は起動結果の status / 出力を自己診断用に判定する。いずれも変数の値に応じた Strata 内の分岐ではない（`app/desktop/src-tauri/src/main.rs:688-728`）。

ほかの開発・検証用箇所は、その都度子プロセスの `env` を作成または更新して値を設定する。プロセス起動後に親環境を変更して反映させる処理や、Strata が値を cache する処理は見つからなかった。

## 根拠

- `tools/packaging/package_terminal.py:146-156,540-543` — 呼び出し元環境を複製し、`PYTHONDONTWRITEBYTECODE="1"` と `-B` を付けて probe を起動。probe の失敗条件。
- `app/desktop/src-tauri/src/main.rs:688-704,706-728` — Desktop self-test の二つの Python 子プロセスに固定値を設定し、終了状態・出力を自己診断結果に使う。
- `tools/packaging/mac/sign-and-notarize.sh:392-405,471-482` — 署名済み app と Terminal の smoke test 中に export し、その後の検証コマンドへ渡す。
- `app/desktop/scripts/stage-control.py:145-168` — staging 検証用の隔離環境に固定値を含め、`strata.py` と installer probe を subprocess 起動。
- `tools/check:79-85` — 開発用 check の環境辞書に固定値を設定。
- `app/desktop/scripts/vision-e2e.mjs:29-36`, `app/desktop/scripts/pics-e2e.mjs:31-38`, `app/desktop/scripts/cards-e2e.mjs:26` — Desktop E2E が host 子プロセス向け環境に設定。
- `app/desktop/scripts/ui-flows.mjs:126-134`, `app/desktop/scripts/local-gguf-e2e.mjs:28`, `app/desktop/scripts/installed-flow.mjs:60`, `app/desktop/scripts/app-close-matrix.py:82-91` — Desktop E2E / close-matrix が検証用環境に設定。
- `terminal/serve/test_server_script_mode.py:25-35`, `terminal/serve/test_hy4_serve_e2e.py:49-54`, `terminal/tests/terminal/test_scripts_run_by_path.py:33-42` — テストが子プロセス環境に設定。
- `terminal/tests/terminal/test_bundle_imports.py:117-159` — packaging probe 用テスト。親の値を取り除く場合と空文字にする場合の双方で `run_probe` を呼ぶ。実装が固定値を設定することのテスト上の確認であり、Python 内部の環境変数解釈を Strata の挙動として扱う根拠にはしていない。
