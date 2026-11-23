# `PUSH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`PUSH` は通常の Strata 実行時設定ではなく、手動起動する GitHub Actions workflow `.github/workflows/docker-images.yml` 内の一時的な環境変数である。workflow は boolean 入力 `inputs.push` を文字列 `--push` または空文字に変換し、シェル展開を介して `tools/docker/publish.sh` の CLI 引数へ渡す。`publish.sh` は環境変数 `PUSH` 自体は読まず、受け取った `--push` オプションでイメージを push するかを切り替える（`.github/workflows/docker-images.yml:12-28,97-104`, `tools/docker/publish.sh:32-47,89-97`）。

## 値と判定

workflow_dispatch の必須 boolean 入力 `push` は既定値 `false`。workflow の式が値を次のとおり正規化するため、`PUSH` に任意の文字列を設定して挙動を選ぶ方式ではない（`.github/workflows/docker-images.yml:24-28,97-104`）。

| 条件 | workflow の入力 | `PUSH` の値 | `publish.sh` の判定 |
|---|---|---|---|
| 通常の workflow 実行 | `false`（既定） | 空文字 | 引数にならず、push しない |
| push を有効化 | `true` | `--push` | `--push` と完全一致するオプションを受け、push する |

この経路で `0`、`1`、`true`、`false`、`0anything` などを `PUSH` の値として直接解釈する処理はない。workflow 入力は boolean であり、シェルへ渡す値は上記二択である。`publish.sh` を直接呼ぶ場合も `PUSH` 環境変数は参照されず、CLI の `--push` が必要である（`.github/workflows/docker-images.yml:24-28,101-104`, `tools/docker/publish.sh:32-47`）。

## 有効になる条件

- `.github/workflows/docker-images.yml` を `workflow_dispatch` で手動実行し、`push` 入力を `true` にする。workflow 自体は自動起動しない（`.github/workflows/docker-images.yml:3-4,12-28`）。
- workflow の「Log in to ghcr.io」step も `inputs.push` が true のときだけ実行される。認証に失敗すれば後続の image step は実行されない（`.github/workflows/docker-images.yml:91-104`）。
- `publish.sh` が各 flavor のイメージを build した後に `--push` を処理する。`--no-latest` が同時に渡された場合、通常タグのイメージは push するが `latest-<flavor>` タグは作成・push しない（`tools/docker/publish.sh:41-43,82-97`; workflow は `latest` 入力に基づいて `LATEST` を設定する: `.github/workflows/docker-images.yml:29-33,99-104`）。

## 実行時の詳細

`PUSH` は workflow の該当 step 起動時に `inputs.push` から設定され、step の `run` シェルが `$PUSH` を展開して `publish.sh` の引数にする。値はその呼び出し時点で CLI 引数へ変換され、`publish.sh` が左から引数を解析して `--push` を見つけると内部変数 `push=1` にする。後続の flavor ごとの build が終わった後、その内部変数が空でなければ `docker push` を実行する。したがって `PUSH` が Strata の engine / Terminal プロセスに継承されて設定を変える経路ではない（`.github/workflows/docker-images.yml:97-104`, `tools/docker/publish.sh:32-47,82-97`）。

スクリプトを直接実行する場合は `PUSH` の設定時期や cache はなく、環境変数を読み取らない。直接実行時に push するには `--push` を明示する（`tools/docker/publish.sh:5-7,24-27,32-47`）。

## ログと測定値

push が無効なら各 flavor について `built <image> (not pushed; add --push)` を出力する。有効なら push 後に `pushed <image>`（latest も push した場合は ` and <image>:latest-<flavor>` を続ける）を出力する。これは publish script の stdout 出力である（`tools/docker/publish.sh:89-97`）。

## 根拠

- `.github/workflows/docker-images.yml:12-28` — 手動起動と boolean `push` 入力、その既定値。
- `.github/workflows/docker-images.yml:91-104` — push 入力による registry login 条件、`PUSH` の生成と CLI への引き渡し。
- `tools/docker/publish.sh:32-47` — CLI 引数の初期値と `--push` の認識。
- `tools/docker/publish.sh:82-97` — build 後の push 分岐と観測可能な出力。
