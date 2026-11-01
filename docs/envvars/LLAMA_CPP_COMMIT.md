# `LLAMA_CPP_COMMIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの開始時点の状態は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の通常の `setup.py` にある `LLAMA_CPP_COMMIT` は、環境変数ではなく llama.cpp の依存先を固定する Python 定数です。一方、`.github/workflows/metal-build.yml` は同じ名前の job 環境変数を固定値で設定し、Metal 用 CI の shell step がその値を `git fetch` に渡します。この文書で環境変数として確認できるのは、この CI 経路だけです。Strata の通常実行時や `setup.py` がプロセス環境からこの名前を読む箇所は見つかりませんでした。

## 値と判定

Metal build workflow の `metal-link` job は `LLAMA_CPP_COMMIT` に `3cf03257f219afbe7334045ff7c6a06ac68c627d` を設定します。shell step は `$LLAMA_CPP_COMMIT` を引用符付きで `git fetch -q --depth 1 origin` に渡し、その後 `git checkout -q FETCH_HEAD` を実行します。Strata のコードにこの workflow 値を parse、検証、変換、または fallback する処理はありません。workflow 定義にある値は固定リテラルで、CLI 引数や他の環境変数による優先順位も定義されていません。

| 状況 | Strata 側で確認できる処理 |
|---|---|
| Metal build workflow 実行 | job 環境に固定 SHA を設定し、fetch の引数に展開する |
| 同名の環境変数が setup.py 実行時に設定済み | `setup.py` は環境変数を参照せず、Python 定数の SHA を使う |
| 空文字・不正な値 | setup/runtime 側の判定箇所なし。workflow の固定値を別の値に置換した場合の git の解釈や結果は、この調査対象コードからは断定しない |

## 有効になる条件

この環境変数の読み取りは GitHub Actions の `metal-link` job に限られます。workflow は `macos-26` runner を使い、`pull_request`（指定された `src/**`、`include/**`、`metal/**`、`third_party/**`、`CMakeLists.txt`、workflow ファイルの変更時）または `workflow_dispatch` で起動します。モデル、GPU、Strata CLI、backend 選択による条件分岐はありません。

`setup.py` の固定定数は別経路です。`get_llama_cpp()` はその定数から作ったアーカイブ URL とファイル名を使います。`source_hash()` も同じ定数を fingerprint の初期値に使います。これらは環境変数の上書きではありません。

## 実行時の詳細

Metal workflow の llama.cpp step は作業ディレクトリに `llama.cpp` を作成し、Git repository を初期化して `ggml-org/llama.cpp` を origin に登録します。job 環境の SHA を shallow fetch し、取得した `FETCH_HEAD` を checkout します。直後の Configure step はその checkout を `STRATA_GGML_DIR` として CMake に渡します。したがって、ここでの変数の効果は Metal CI がビルド対象にする llama.cpp checkout の指定です。Strata アプリの起動時設定ではありません。

この値は job の環境設定で与えられ、対象の shell step で展開されます。`setup.py` 側の同名定数は import 時点でコードから決まり、`os.environ` を通した読み取りや実行中の再評価・cache はありません。workflow での fetch 失敗時の git の詳細な挙動は、Strata の環境変数処理としては定義されていません。

## 根拠

- `.github/workflows/metal-build.yml:21-31` — `metal-link` job と固定環境変数値。
- `.github/workflows/metal-build.yml:41-53` — shell での変数展開、fetch、checkout、および取得ソースを使う Configure。
- `setup.py:222-223` — 同名の Python 定数とアーカイブ URL。環境変数参照ではない。
- `setup.py:3464-3470` — 定数由来のアーカイブを使う `get_llama_cpp()`。
- `setup.py:5831-5839` — ソース fingerprint に定数を含める処理。
- `metal/setup_mac.py:430-431,8910-8913`、`setup.py:7742-7743,7777-7778` — 定数由来の commit 短縮表示と llama.cpp の取得呼び出し。
- `tools/test_setup_llama_archive.py:23-35`、`tools/iq_fixture.py:42-46`、`packaging/build_hip_linux.sh:5-11` — 定数・アーカイブに関するテスト、説明、同梱ビルドスクリプトの参照。これらは当該環境変数を読み取る実装ではありません。
