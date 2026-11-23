# `LATEST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`LATEST` は Strata の Docker images 手動実行 workflow 内で使う step-level 環境変数で、利用者が選んだ `latest` boolean を `tools/docker/publish.sh` の `--no-latest` 引数へ変換する中継値である。`latest` を有効にすると、各 flavor の `latest-<flavor>` タグを作成し、push が有効ならそのタグも registry へ送る。無効にすると、そのタグ操作を省く。通常のアプリ実行や engine の動作を制御する環境変数ではない（`.github/workflows/docker-images.yml:12-38,97-104`、`tools/docker/publish.sh:32-43,82-94`）。

## 値と判定

workflow_dispatch の入力 `latest` は boolean 型で必須、既定値は `true`。workflow の式 `${{ !inputs.latest && '--no-latest' || '' }}` が `LATEST` に設定する。したがって `inputs.latest: true` なら空文字、`false` なら文字列 `--no-latest` になる。publish step はこれを unquoted の `$LATEST` として展開するため、空文字なら引数なし、`--no-latest` ならその一引数が script に渡る（`.github/workflows/docker-images.yml:29-33,97-104`）。

| workflow 入力 | `LATEST` の値 | script の判定 | 結果 |
|---|---|---|---|
| `latest: true`（既定） | 空文字 | `--no-latest` が渡らず、`latest=1` のまま | latest タグを作成する |
| `latest: false` | `--no-latest` | `latest=""` に設定 | latest タグを作成しない |

この値は workflow が boolean 入力から生成するため、任意文字列、数値、大小文字、空白を使った有効・無効判定は実装されていない。手動実行の入力値そのものが未指定なら、必須入力の定義に加えて既定値 `true` が指定されている（`.github/workflows/docker-images.yml:29-33`）。

## 有効になる条件

- この変数を設定する経路は `.github/workflows/docker-images.yml` の `workflow_dispatch` に限られる。通常の Strata CLI・server・GPU backend の設定ではない（`.github/workflows/docker-images.yml:12-38,97-104`）。
- workflow が対象 flavor の package を見つけて image を build する必要がある。package のない flavor は script が skip し、全 flavor が build されなければ `publish.sh:100` で終了コード 3 になる（`tools/docker/publish.sh:63-73,100`）。
- `latest: true` のとき、`publish.sh` は `--push` の有無に関係なく `docker tag` でローカルの latest タグを作る。registry への `docker push` は別の boolean 入力 `push` が true のときだけ行われる。`push: false` では latest タグはローカルで作られるが、公開されない（`.github/workflows/docker-images.yml:24-28,97-104`、`tools/docker/publish.sh:82-96`）。
- `latest: false` は `push` の値にかかわらず latest の tag/push を抑止する。version 付きタグの build、および `push: true` 時の version 付きタグの push は引き続き行われる（`tools/docker/publish.sh:74-94`）。

## 実行時の詳細

GitHub Actions が `inputs.latest` を `LATEST` 環境変数に設定し、step の shell が `$LATEST` を展開して script の argv に渡す。script は起動時の引数解析で `--no-latest` を受け取った場合だけ内部 shell 変数 `latest` を空にし、それ以降はその値を使う。script 内で `getenv` 相当の再読み取りや cache はないため、実行中に環境変数を書き換えても反映する処理はない（`.github/workflows/docker-images.yml:97-104`、`tools/docker/publish.sh:32-43`）。

`latest` が有効なら各 flavor の build 後に `docker tag "$img" "$image:latest-$flavor"` を実行する。`push` 有効時は version 付き tag を push し、続けて latest tag も push し、出力に `and <image>:latest-<flavor>` を含める。`--no-latest` の場合はこの tag/push/出力追加と latest image の削除を省く。`set -eu` のもとで Docker コマンドが失敗すれば script は後続処理へ進まず終了する（`tools/docker/publish.sh:28,82-100`）。

## ログと測定値

`push: true` かつ latest 有効時は `pushed <image>:<version>-<flavor> and <image>:latest-<flavor>` を出力する。latest 無効時は `and ...` の部分を出さない。`push: false` の場合は `built <image>:<version>-<flavor> (not pushed; add --push)` を出力する。workflow 内の `LATEST` 専用ログや測定値はない（`tools/docker/publish.sh:89-97`）。

## 根拠

- `.github/workflows/docker-images.yml:12-38` — 手動起動 workflow と `latest` boolean 入力（必須、既定 true）。
- `.github/workflows/docker-images.yml:97-104` — `inputs.latest` から `LATEST` を設定し、shell 展開で publish script に渡す。
- `tools/docker/publish.sh:32-43` — `latest=1` の既定値と `--no-latest` の引数処理。
- `tools/docker/publish.sh:82-96` — latest tag/push と出力の分岐。
