# `LATEST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

`LATEST` は Strata engine の実行時設定ではありません。手動実行する GitHub Actions の `Docker images` workflow が、Docker イメージの `latest-<flavor>` タグも更新するかどうかをシェル引数に変換するため、その workflow の一 step にだけ設定する環境変数です。workflow_dispatch の boolean 入力 `latest` が既定で `true` です（`.github/workflows/docker-images.yml:12-37`）。

workflow は `inputs.latest` が false のとき `LATEST=--no-latest`、true のとき空文字を step の環境に設定し、実行行でその値を `docker/publish.sh` へ展開します（`.github/workflows/docker-images.yml:97-104`）。そのため、これは workflow 内で値が作られる一時的な中継であり、利用者が Strata プロセスへ設定する環境変数ではありません。

## 値と判定

`LATEST` 自体を parse するコードはありません。値は workflow の式が生成する次の二通りです。

| workflow 入力 `latest` | step 環境の `LATEST` | publish.sh に渡る結果 |
|---|---|---|
| `true`（既定） | 空文字 | 引数なし。`publish.sh` の `latest=1` が維持される |
| `false` | `--no-latest` | `--no-latest` オプションにより `latest` が空文字になる |

この workflow 以外から任意の値を与えた場合の解釈規則は定義されていません。`docker/publish.sh` は環境変数 `LATEST` を直接参照せず、コマンドライン引数 `--no-latest` だけを認識します（`.github/workflows/docker-images.yml:102-104`, `docker/publish.sh:32-46`）。

## 有効になる条件

- `Docker images` workflow の `workflow_dispatch` を実行した場合に限り、この `LATEST` step 環境値が設定されます。workflow は自動起動しないと説明されています（`.github/workflows/docker-images.yml:3-4,12-13`）。
- `latest` 入力は `push` 入力から独立しています。既定値は `true` です（`.github/workflows/docker-images.yml:24-33`）。
- `publish.sh` は、`--no-latest` がなければ各 flavor の version タグから `latest-<flavor>` タグを作成します。`--push` があるときだけその追加タグも registry に push し、`--push` がないとローカル build のみです（`docker/publish.sh:24-26,32-43,74-88`）。
- 起動時の引数解析で `--no-latest` を受け取ったとき、後続の tag 作成と push の条件が無効になります。未対応の引数は stderr に `publish.sh: unknown option ...` を出して終了コード 2 になります（`docker/publish.sh:33-46,76-85`）。

## 実行時の詳細

workflow の式は `latest: true` なら空の引数、`latest: false` なら `--no-latest` をシェル展開でコマンドへ追加します。`publish.sh` は初期値 `latest=1` の後、引数 `--no-latest` を見た場合に `latest=""` とします。flavor ごとの build 後、`latest` が非空なら `docker tag "$img" "$image:latest-$flavor"` を実行します。さらに `push` が有効な場合、version タグを push し、`latest` が非空の場合に限って latest タグも push します。push 無効時の出力は `built ... (not pushed; add --push)` です（`.github/workflows/docker-images.yml:97-104`, `docker/publish.sh:32-46,74-88`）。

`LATEST` の値は workflow が step 起動時に作り、同じ step の command line に渡されます。engine や Strata のサーバーに渡す処理、起動後の再読み込み、cache はありません。

## 根拠

- workflow の入力、既定値、`LATEST` への変換と引数展開: `.github/workflows/docker-images.yml:12-37,97-104`
- Docker publish script の `latest` 既定値と `--no-latest` の解析: `docker/publish.sh:24-46`
- version/latest タグの作成、push 条件と観測できる出力: `docker/publish.sh:74-88`
- 候補名の全参照: `.github/workflows/docker-images.yml:102,104` が workflow の中継用途、`apps/host/src/lib/live-status.ts:6` と `apps/host/server/agent/status.mjs:4` はコメント中の普通名詞、`tools/test_setup_engine_hash.py:33,58-60,135-139,178-179` は release URL を表すテスト定数・テストです。後者のテスト定数は Strata の環境変数読み取りではありません。
