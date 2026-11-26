# `LD_LIBRARY_PATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata 自身が値を機能フラグとして解釈する環境変数ではない。Linux など Windows 以外の複数の起動経路で、子プロセス用環境にパッケージや SDK のライブラリディレクトリを先頭追加し、元の `LD_LIBRARY_PATH` を後ろに残す。対象は主にエンジン、HIP/Vulkan のビルド・検査、画像処理エンジンである。実際にライブラリを検索するのは起動されたプログラム側であり、その検索規則はこの文書の対象外である（`terminal/serve/server.py:4007-4053`、`terminal/setup.py:5192-5204`）。

Linux AppImage では別の目的で、Strata の同梱パスを継承した外部プログラムの環境から取り除く。これはアプリ本体のライブラリ環境をシステムのファイル選択・通知・ブラウザー等へ持ち込まないための処理である（`app/host/server/external-env.mjs:5-13,26,43-70`）。

## 値と判定

Strata はこの変数を数値や真偽値として parse しない。パス区切り文字は Python の `os.pathsep`（Linux では `:`）。値の空白、大文字小文字、各要素の妥当性、重複は検査しない。空文字と未設定は、既存値を追加する箇所では同じ扱い（追加元なし）だが、起動時にディレクトリを付けない経路では元の環境をそのまま維持する。

| 条件・経路 | 未設定 / 空文字 | 値がある場合 | 上書き・無効値 |
|---|---|---|---|
| サーバーからエンジンを起動（Windows 以外） | 有効な `cfg.lib_dirs` があればそれらだけを設定 | `cfg.lib_dirs` の既存ディレクトリを先頭にし、元の値を後ろに連結 | Strata は値を無効とは判定しない。`cfg.env` に `LD_LIBRARY_PATH` があれば、この合成値を後から置き換える（`terminal/serve/server.py:4007-4053`） |
| インストール済みエンジンの検査・トークナイザー抽出（Linux/macOS） | 有効なパッケージ lib dir があればそのディレクトリを設定 | パッケージ自身のディレクトリ群を先頭にし、元の値を後ろに連結 | Windows は `PATH`、macOS は `DYLD_LIBRARY_PATH` を使う経路がある（`terminal/strata_control/shape_engine.py:217-228`、`terminal/strata_control/local_engine.py:48-55`、`terminal/setup.py:5192-5204,10233-10241,10715-10724`） |
| HIP / Vulkan セットアップ、HIP 画像ビルド | `os.environ.get(..., "")` で空の末尾要素を作り、最後の区切り文字を除去 | 選択した SDK のディレクトリ群を先頭に追加 | 受理・拒否される値はない。Strata プロセスの環境を書き換え、以降の子プロセスに継承させる（`terminal/setup.py:5681-5688,5754-5759,5860-5864,5934-5939`） |
| Linux AppImage から外部プログラムを起動 | 値がない場合はないまま | 起動時環境の記録があればその値を使う。記録がなく `APPDIR` があるときは `:` で分割して AppImage 内の要素を除去 | 要素が全て除かれた場合は変数自体を削除。AppImage 外で記録もなければ変更しない（`app/host/server/external-env.mjs:43-70`） |

たとえばサーバーの `cfg.lib_dirs=["/pkg/lib"]`、元値が未設定なら子環境値は `/pkg/lib`、元値が `/usr/local/lib` なら `/pkg/lib:/usr/local/lib` となる。`cfg.env` が同じキーを指定すればその文字列が最終値になる。通常の起動経路に「`0`」「`1`」「`true`」などの有効・無効境界はない。

## 有効になる条件

- OS により対象キーが異なる。サーバーの通常エンジン起動は Windows で `PATH`、それ以外で `LD_LIBRARY_PATH` を使う。部品検査・トークナイザー抽出の一部は Windows で `PATH`、macOS で `DYLD_LIBRARY_PATH`、その他で `LD_LIBRARY_PATH` を使う（`terminal/serve/server.py:4050-4053`、`terminal/strata_control/shape_engine.py:223-228`）。
- サーバーでは `cfg.lib_dirs` のうち存在するディレクトリがある場合だけ先頭追加する。エンジン起動時に構成の `env` がキーを含めば追加後の値を上書きする。環境変数自体が有効な値でも、追加対象ディレクトリがなければサーバーは値を変更しない（`terminal/serve/server.py:4050-4053`）。
- セットアップ側の HIP/Vulkan 変更は該当するビルド・SDK 準備関数が実行された場合だけ起きる。HIP ビルドは `rocm_root()` が返すディレクトリ、Vulkan は SDK の `VulkanLoader/lib` を追加する（`terminal/setup.py:5681-5688,5858-5864,5934-5939`）。
- 起動時に元値を読むラッパーに CLI の値判定や専用 CLI フラグはない。サーバーの設定 `env` は `cfg.lib_dirs` より後に適用されるため、同じキーを明示すれば優先する（`terminal/serve/server.py:4027-4028,4050-4053`）。
- AppImage の外部プログラム向け処理は、ランチャーが記録した元環境を優先する。記録がなければ `APPDIR` 内のパスだけを取り除く。記録も `APPDIR` もなければ `LD_LIBRARY_PATH` を変えない（`app/host/server/external-env.mjs:43-70`）。

## 実行時の詳細

この変数の値自体をグローバルに cache する処理は確認できない。Python のサーバーは `child_env()` の呼び出しごとに `dict(os.environ)` を作り、実際にエンジンを起動する際の環境として渡す。通常起動、レプリカ、分割エンジンの各起動経路でこの関数を呼ぶ（`terminal/serve/server.py:4007-4053,8820-8824,8845-8852,8912-8919,9386-9394`）。`.strata` モデルのトークナイザーが見つからない場合は、サーバーが実行ファイルのディレクトリと有効な `lib_dirs` を先頭にした環境で `--export-tokenizer` を起動する（`terminal/serve/server.py:9112-9128`）。画像エンジンも `image_env()` が起動時に環境辞書を作り、`cfg.env` を最後に適用して子プロセスへ渡す（`terminal/serve/images.py:177-196,467-468`）。一方、Hy4 / Inkling の `--info` 結果はプロセス内 `_PROBES` に cache されるため、同じキーの probe が再利用されれば環境を作り直して再起動する処理は通らない。これらの cache キーには `LD_LIBRARY_PATH` は含まれない（`terminal/serve/hy4_kind.py:78-95`、`terminal/serve/inkling_kind.py:82-108`）。

パッケージ検査では `package_lib_dirs()` がパッケージ自身と `BUILD.json` の相対 `lib_dirs` のうち実在するものを返し、検査用の環境に先頭追加する（`terminal/strata_control/engine_component.py:158-174`、`terminal/strata_control/shape_engine.py:217-228`）。エンジン追加時の `--version` 検査やチューニング用 `--help` probe も同じく、毎回の起動環境を作って子プロセスへ渡す（`terminal/strata_control/local_engine.py:48-55`、`terminal/strata_control/tuning.py:208-240`）。HIP の GPU 列挙も `engine_env()` で同様に環境を作って `strata-device --list-devices` を実行するが、パッケージが HIP でない・実行ファイルがない・起動 timeout・非ゼロ終了なら列挙結果を返さない（`terminal/setup.py:5192-5204,5223-5247`）。

開発・診断用の同梱 Python ツールにも子環境を作る箇所がある。例として `par_run.py` と `batch_test.py` は現在値を保持しながら指定 lib dir を先頭に追加してサーバー／エンジンを起動する（`terminal/tools/par_run.py:133-147`、`terminal/tools/batch_test.py:47-62`）。パッケージ収集ツールは `ldd` の実行環境だけに `--search` のパスを先頭追加する（`tools/packaging/collect_libs.py:138-142`）。これらは製品サーバーの設定フラグではない。

## ログと測定値

`LD_LIBRARY_PATH` の値を表示する専用ログ、値の不正を知らせる警告、値に関する測定値は確認できない。子プロセスが起動に失敗した場合の報告は呼び出し元による。たとえばコンポーネントの `--version` 検査では起動不能または非ゼロ終了を `TestStartFailed` として報告し、共有ライブラリ不足を検出した場合はライブラリ名を理由・案内に含める（`terminal/strata_control/updater.py:1031-1074`）。HIP デバイス検査は失敗時に `None` を返し、この箇所では専用エラー文を出さない（`terminal/setup.py:5237-5247`）。

## 根拠

- `terminal/serve/server.py:4007-4053,8820-8824,8845-8852,8912-8919,9112-9128,9386-9394` — サーバーが元の環境、設定ディレクトリ、設定 `env` を組み合わせてエンジン子プロセスへ渡す。
- `terminal/serve/images.py:177-196,467-468`、`terminal/serve/hy4_kind.py:78-95`、`terminal/serve/inkling_kind.py:82-108` — 画像エンジン環境と、結果を cache する `--info` probe。
- `terminal/setup.py:5192-5204,5223-5247,5681-5688,5750-5759,5858-5864,5934-5939,9634-9642,10233-10245,10715-10725` — セットアップの子プローブ、HIP/Vulkan ビルド環境、エンジン情報取得、トークナイザー抽出。
- `terminal/strata_control/engine_component.py:158-174`、`terminal/strata_control/shape_engine.py:217-245`、`terminal/strata_control/local_engine.py:48-74`、`terminal/strata_control/updater.py:1031-1074`、`terminal/strata_control/tuning.py:208-240` — コンポーネントのライブラリディレクトリと、検査・実行時の子環境。
- `app/host/server/external-env.mjs:5-13,26,43-70` と同 helper の利用箇所 `app/host/server/app-ui.mjs:39-59`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/chat-files.mjs:89-94` — AppImage 外部プログラムへの環境引き渡し。
- `terminal/tools/par_run.py:133-147`、`terminal/tools/batch_test.py:47-62`、`tools/packaging/collect_libs.py:138-151` — 同梱ツールが診断・パッケージ処理の子プロセス環境を構築する箇所。
