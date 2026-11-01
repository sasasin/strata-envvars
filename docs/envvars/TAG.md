# `TAG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`TAG` は実行時の Strata engine / server の設定ではありません。手動実行専用の GitHub Actions workflow `Docker images` が、入力 `release_tag` を workflow step 内で受け渡すために設定する環境変数です。その値を、engine package の release を指定する `--release-tag` 引数に渡します。

## 値と判定

`workflow_dispatch` の必須 string 入力 `release_tag` が `TAG` の値になります。workflow は値の形式を検査・正規化しません。最初の step では shell が `TAG` を未引用で `args="--release-tag $TAG --list --skip-missing"` に展開してから `fetch-engines.py` を実行します。値に空白等が含まれる場合は shell の単語分割が起きます。空文字なら `fetch-engines.py` は `--release-tag` と `--source` のどちらか一方が必要という引数検査で失敗します。

次の step では `TAG` を引用して `docker/publish.sh --release-tag "$TAG"` に渡します。`publish.sh` は空の tag かつ source 未指定なら終了コード 2 で `publish.sh: give --release-tag or --source` を stderr に出します。workflow の入力は必須ですが、ソース上に空文字を別途拒否する workflow 側の検証はありません。

## 有効になる条件

- `Docker images` workflow を Actions の `workflow_dispatch` で手動実行したときだけです。自動起動 trigger は定義されていません（`.github/workflows/docker-images.yml:3-4,12-18`）。
- workflow は2つの step にそれぞれ `TAG: ${{ inputs.release_tag }}` を設定します。外部プロセス環境にあらかじめある `TAG` を読む仕組みではなく、step ごとに workflow 入力で上書きされます。
- Strata engine / server の起動時に参照する環境変数ではなく、GPU backend、OS、モデル状態による分岐もありません。

## 実行時の詳細

`plan` job の package-list step は `TAG` を `--release-tag` 引数として `docker/fetch-engines.py --list --skip-missing` に渡します。同スクリプトは tag と `--source` の一方だけを要求し、tag の場合は `https://github.com/{repo}/releases/download/{release_tag}` を feed の取得元として組み立てます（`.github/workflows/docker-images.yml:55-68`, `docker/fetch-engines.py:99-123`）。

`image` job は同じ入力値を `docker/publish.sh` に渡します。`publish.sh` は明示的な `--version` がない場合、先頭の `v` を取り除いた値を image version とし、release tag と flavor を付けて Docker image を build します（`.github/workflows/docker-images.yml:97-104`, `docker/publish.sh:32-53,68-76`）。この用途を超えて `TAG` を子プロセス環境へ渡したり、生成 image 内の Strata 実行時設定にしたりする処理は確認できません。

値は各 workflow step のプロセス起動時に環境から shell へ渡り、その step 内で一度 CLI 引数に展開されます。Strata の常駐プロセスでの cache や後からの環境変更の再読込はありません。

## 根拠

- `.github/workflows/docker-images.yml:12-18` — 手動実行 workflow と必須 `release_tag` 入力。
- `.github/workflows/docker-images.yml:55-68,97-104` — step-local `TAG` の設定と CLI への展開。
- `docker/fetch-engines.py:99-123` — `--release-tag` / `--source` の排他検査と release URL の組み立て。
- `docker/publish.sh:32-53,68-76` — CLI tag の受け取り、既定 version、image build への使用。
- `docs/envvars/000_envvers.md:1666` — 候補一覧の `TAG`。
