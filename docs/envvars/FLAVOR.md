# `FLAVOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前は、Strata の通常実行時に読む環境変数ではありません。GitHub Actions の Docker image workflow が matrix の flavor を `FLAVOR` という step 環境変数に設定し、shell で読み取って `docker/publish.sh --flavors` に渡します。公開スクリプトは feed から対応する engine package を選び、`docker/build.sh --flavor` へ Docker イメージ用の backend flavor（`cuda`、`hip`、`sycl`）を渡します。

Dockerfile 側の `FLAVOR` は実行時環境変数ではなく build argument (`ARG`) です。ランタイムイメージに残る値ではなく、追加する OS package の選択とイメージ label に使われます。サーバーや engine の起動条件・推論動作は制御しません。

## 値と判定

| 経路 | 値と判定 |
|---|---|
| GitHub Actions | `FLAVOR` は `matrix.flavor` から設定されます。matrix は release feed に存在する flavor の一覧から作られるため、通常は空値ではありません。|
| `docker/publish.sh` | CLI の `--flavors` をカンマ区切りで処理します。未指定時は `cuda13,cuda12,rocm-gfx120x,rocm-gfx110x,rocm-gfx1151,sycl`。不明名は `fetch-engines.py` が `unknown flavor ...` で引数エラーにします。|
| `docker/build.sh` | `--flavor` が必須で、受け付ける値は `cuda`、`hip`、`sycl`。未指定または別の値は build 前に stderr へエラーを出して終了コード 2 になります。|
| `docker/Dockerfile` へ直接 build arg を渡す場合 | `ARG FLAVOR=cuda` が既定値です。`cuda` は追加 backend package なし、`hip` と `sycl` はそれぞれの OS package 群を選びます。それ以外は `FLAVOR must be cuda, hip or sycl` を出して `RUN` が失敗します。|

GitHub Actions の flavor 名と Dockerfile の値は同じではありません。`docker/fetch-engines.py` の対応表で、たとえば `cuda13` と `cuda12` は `cuda`、`rocm-*` は `hip` に変換されます。

## 有効になる条件

`FLAVOR` が使われるのは Docker image の手動 workflow または Docker image build 経路です。Actions workflow は release package を列挙して matrix を作り、各 matrix 値を `FLAVOR` に設定します。`publish.sh` はその値を package 選択に使い、選んだ package の backend を `build.sh --flavor` として渡します。

`docker/build.sh` を直接使う場合、ホストの `FLAVOR` 環境変数は参照されません。`--flavor` 引数が必要です。このスクリプトがその値を `docker build --build-arg FLAVOR=...` へ渡します。Dockerfile の build argument は runtime の `ENV` 宣言に含まれず、後続の Strata 起動時に `FLAVOR` として読み取られる経路は確認できません。

## 実行時の詳細

Actions workflow の該当 step では `FLAVOR: ${{ matrix.flavor }}` を環境へ設定し、run script 内の `"$FLAVOR"` を `publish.sh --flavors` に渡します。`publish.sh` は fetch 結果の backend flavor を取り出し、`build.sh --flavor` に渡します。`build.sh` は引数値を検証して Docker build argument に明示設定します。したがって、この流れでは環境変数の値は build 時に引数経由で明示的に転送され、コンテナ内で動的に再評価・cache される設定ではありません。

Dockerfile は `cuda` / `hip` / `sycl` に応じて system package を選択し、無効な値なら build を失敗させます。build 後は `${FLAVOR}` の値が `org.opencontainers.image.description` と `com.strata.flavor` label に埋め込まれます。runtime でこの値により Strata のログ、終了、engine 処理が変化するコードは見つかりません。

## 根拠

- `.github/workflows/docker-images.yml:70-81,97-104` — release package に基づく matrix と、matrix 値から設定された `FLAVOR` の shell 展開・引き渡し。
- `docker/publish.sh:63-76` — flavor 一覧の既定値、fetch 結果から backend を取り出して `build.sh --flavor` に渡す流れ。
- `docker/fetch-engines.py:32-40,48-53,99-116` — release flavor と build backend の対応表、CLI 引数の検査。
- `docker/build.sh:26-46,105-109` — `--flavor` の引数読み取り・許容値検証と Docker build argument への明示的な転送。
- `docker/Dockerfile:65-82,116-124` — `ARG FLAVOR=cuda`、package 選択、無効値の build failure、イメージ label への埋め込み。
- `Dockerfile:91-109` — source build 用の別 Dockerfile は `FLAVOR` build argument を使わず、label も固定で `cuda`。
