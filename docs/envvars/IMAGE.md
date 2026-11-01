# `IMAGE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`IMAGE` は、同梱の Docker smoke test `docker/smoke-test.sh` が起動するコンテナの image 名（必要なら tag を含む）を指定します。Strata の engine、server、通常の CLI が読む実行時設定ではありません。 smoke test の Docker 起動引数に使われるだけで、コンテナ内の環境変数としては渡されません（`docker/smoke-test.sh:28-30`）。

## 値と判定

| 状態 | 挙動 |
|---|---|
| 未設定 | 起動直後の必須展開でエラーになり、スクリプトは終了する。 |
| 空文字 | 未設定と同じくエラーになり、スクリプトは終了する。 |
| 非空文字列 | 内容を parse・検証・変換せず、そのまま `docker run` の image 引数に渡す。 |

検査は Bash の `${IMAGE:?}` 形式です。既定値や無効値からの fallback はありません。コメントの使用例は `IMAGE=strata:0.1.45-sycl` です（`docker/smoke-test.sh:4-11`）。実際の有効性は Docker 起動の成否に委ねられ、`docker run` が失敗すれば `FAIL: docker run` を出して終了します（同 `:27-30`）。

## 有効になる条件

この値を読むのは `docker/smoke-test.sh` を実行した場合だけです。`docs/DOCKER.md` は同スクリプトを実カード上での smoke checks として案内し、変数の説明はスクリプト冒頭を参照するよう記載しています（`docs/DOCKER.md:301`）。スクリプトは `IMAGE` のほか `NAME`、`BASE`、`OUT` も必須として検査します（`docker/smoke-test.sh:10-11`）。

`.github/workflows/docker-images.yml` では workflow の `env` に `IMAGE: ghcr.io/niko1221/strata` を定義し、publish コマンドへ `--image "$IMAGE"` として渡します（同 `:43-44,98-104`）。これは CI workflow 内の値であり、Strata アプリの環境設定ではありません。

## 実行時の詳細

スクリプト開始時に必須展開で値の存在と非空を確かめ、後続の `docker run` 呼び出しで引用した単一の引数として使います。スクリプト内で値をキャッシュしたり再読込したりはしません。値の優先順位、CLI による上書き、OS/backend による分岐は実装されていません。呼び出し時に `IMAGE=... docker/smoke-test.sh` のように環境へ設定するか、呼び出し元の環境から継承させます（`docker/smoke-test.sh:4-6,10-11,27-30`）。

リポジトリ全体の `IMAGE` 参照も確認しました。ほかに GitHub Actions workflow の publish 用変数、Docker build のコメント、文書中の Docker image という一般名、vision テスト内の Python 定数がありますが、いずれも Strata の runtime が環境変数 `IMAGE` を読む箇所ではありません。

## 根拠

- `docker/smoke-test.sh:1-17,27-30` — 対象ツール、必須展開、ログ設定、Docker image 引数。
- `docker/smoke-test.sh:107-108` — smoke test の最終結果と終了コード。
- `docs/DOCKER.md:301` — smoke test の用途と変数説明の参照先。
- `.github/workflows/docker-images.yml:43-44,98-104` — CI workflow 内での別用途の値定義と publish への受け渡し。
