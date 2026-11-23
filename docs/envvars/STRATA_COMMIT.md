# `STRATA_COMMIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_COMMIT` は通常の Strata 実行時機能を切り替える変数ではなく、`tools/packaging/package_terminal.py` が Terminal 配布アーカイブにソースの commit ID を `COMMIT` ファイルとして記録するための候補値です。これは環境変数として実際に読み取られます。CLI `--commit`、`STRATA_BUILD_COMMIT`、ソース checkout の Git commit も候補で、`STRATA_COMMIT` はそのうち CLI の次、`STRATA_BUILD_COMMIT` の前に評価されます（`tools/packaging/package_terminal.py:422-433,465,513-516`）。

## 値と判定

候補値は前後の空白を `strip()` した後、ASCII の 16 進数字 40 桁と文字列全体が一致する場合だけ採用されます。採用値は小文字に正規化されます。したがって未設定・空文字・空白だけ・短縮 SHA・40 桁以外・非 16 進文字を含む値はこの候補として無効で、次の候補へ進みます。大文字の A–F は受け付けます。`0`、`1`、`true`、`false`、`0anything` はいずれも 40 桁の SHA ではないため無効です。部分一致や数値変換はありません（`tools/packaging/package_terminal.py:426-433`）。

| 条件 | `STRATA_COMMIT` の扱い |
|---|---|
| 未設定または空文字 | 次の候補 `STRATA_BUILD_COMMIT`、その後 Git checkout の `HEAD` を調べる |
| 前後空白を除いて 40 桁の 16 進文字列 | CLI `--commit` が有効値でない場合に採用し、小文字化 |
| それ以外（短縮 SHA、余分な文字、空白だけ等） | 無効として次の候補へ進む。無効値だけを理由とした警告は出さない |

`--commit` に有効な SHA が渡されると環境変数より優先されます。未設定・空の `--commit` や無効な `--commit` は採用されず、環境変数の候補に進みます。`STRATA_COMMIT` も無効なら `STRATA_BUILD_COMMIT`、さらに `git -C <source-root> rev-parse HEAD` の順です（`tools/packaging/package_terminal.py:426-433,449-451,465`）。

## 有効になる条件

- `tools/packaging/package_terminal.py` のアーカイブ作成を実行すること。GPU backend、OS、モデル状態、サーバーモードには依存しません（`tools/packaging/package_terminal.py:441-465,513-516`）。
- CLI `--commit` に有効な 40 桁 SHA がある場合はその値が優先され、`STRATA_COMMIT` は結果に使われません。
- Docker のビルド経路では `STRATA_COMMIT` という build arg を Dockerfile が `STRATA_BUILD_COMMIT` 環境変数へ渡し、パッケージャーが後者を候補として読みます。`tools/docker/build.sh` は build arg を指定し、両 Dockerfile は空を既定値として宣言しています（`tools/docker/build.sh:131-134`; `tools/docker/Dockerfile:35-37`; `tools/docker/Dockerfile.src:111-117`）。この Docker の build arg は `package_terminal.py` 内の `STRATA_COMMIT` 環境変数読み取りとは別の受け渡し経路です。
- `tools/packaging/mac/build_engine.sh` は `STRATA_COMMIT` が未設定または空なら `BUILD_ID` を代入して export します。ただし同スクリプトの後続パッケージ処理は `package_engine.py` に `--build-id "$BUILD_ID+metal"` を渡しており、このスクリプト内で `STRATA_COMMIT` を読む後続処理は確認できません（`tools/packaging/mac/build_engine.sh:45-57,89-93`）。

## 実行時の詳細

`package_terminal.py` の `main()` が引数解析後に `build_commit(args.commit)` を一度呼び、候補を順に検証します。環境値の読み取りを行うのはこの関数呼び出し時で、関数内・プロセス内のキャッシュはありません。通常の Terminal 起動時や各リクエスト時にこの変数を読み直して動作を変えるコードは見つかりません（`tools/packaging/package_terminal.py:422-438,441-465`）。

確定した SHA があればアーカイブのルートに `COMMIT` ファイルを書き、末尾に改行を付けます。どの候補も有効でない場合、`--skip-deps` なしでは `SystemExit` となり、`the commit of these sources is unknown (no .git here, no --commit, no STRATA_COMMIT): the archive would carry no COMMIT file, and every \`strata bench run\` on it would be nonconforming` を出します。`--skip-deps` 指定時は同じ内容を `warning: ` 付きで標準出力に出して続行し、`COMMIT` ファイルを作りません（`tools/packaging/package_terminal.py:465-471,513-516`）。

## 根拠

- `tools/packaging/package_terminal.py:422-438` — 候補順、環境変数の取得、形式検証、Git fallback。
- `tools/packaging/package_terminal.py:441-471` — `--commit` 引数と不明時の失敗・警告。
- `tools/packaging/package_terminal.py:513-516` — アーカイブ内 `COMMIT` ファイルの作成。
- `tools/docker/build.sh:61-63,131-134`、`tools/docker/Dockerfile:34-37`、`tools/docker/Dockerfile.src:109-117` — Docker build arg から `STRATA_BUILD_COMMIT` への転送。
- `tools/packaging/mac/build_engine.sh:45-57,89-93` — Mac ビルドスクリプトの既定値設定と後続 package_engine 呼び出し。
