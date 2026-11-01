# `INPUT_TAG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

これは Strata の実行バイナリや Python サーバーが読む環境変数ではありません。Strata リポジトリの手動起動専用 GitHub Actions workflow `.github/workflows/docker-images.yml` が、Docker image job の Summary step に `release_tag` input を `INPUT_TAG` として渡し、Summary に表示する image tag の文字列を作るために使います。

## 値と判定

workflow は `INPUT_TAG` を数値や真偽値として parse せず、別の環境変数や CLI 引数から上書きもしません。Summary step の `env:` で `${{ inputs.release_tag }}` をそのまま設定し、Bash の `${INPUT_TAG#v}` で先頭に `v` があれば一つ取り除いて image 名の表示に使います。

| 状態 | Summary に使われる値 |
|---|---|
| `release_tag` が `v0.2.7` | `0.2.7`（先頭の `v` を除去） |
| `release_tag` が `0.2.7` | `0.2.7`（変更なし） |
| `release_tag` が空、または `INPUT_TAG` が未設定 | 空文字。workflow 側で補完・検証する処理はない |
| その他の文字列 | 先頭が `v` の場合だけその一文字を除き、残りをそのまま使う |

`release_tag` input は `required: true` ですが、workflow 内にタグ書式の検証や空値用 fallback はありません。値の許容形式や空値時に GitHub Actions がどう入力を扱うかは、この workflow の実装だけからは定められません。

## 有効になる条件

この処理は通常の Strata 起動では実行されず、`workflow_dispatch` による `Docker images` workflow の `image` job で実行されます。job は検出した flavor ごとの matrix で動き、Summary step は `if: ${{ always() }}` により先行 step の成否にかかわらず実行対象です。

`INPUT_TAG` は Docker image の取得・build・push の引数には使われません。それらの処理には別名 `TAG` が `release_tag` から設定されています。従って `INPUT_TAG` の値は Summary 表示だけに作用し、push の有無や image の build 結果を切り替えません。

## 実行時の詳細

Summary step は flavor、release tag、push 状態と、`$IMAGE:${INPUT_TAG#v}-${{ matrix.flavor }}` の表示行を組み立て、`>> "$GITHUB_STEP_SUMMARY"` で GitHub Actions の step summary に追記します。workflow に `INPUT_TAG` の明示的な再読み込み、cache、ログ出力、子プロセスへの転送、値に応じた失敗処理はありません。Bash のパラメータ展開による先頭 `v` の除去はこの step の実行時に行われます。

この名前の参照はリポジトリ全体で `.github/workflows/docker-images.yml:111,114` のみです。C/C++、Python 等の Strata 実行コードや汎用 env helper による読み取りは確認できません。そのため、OS/backend/build macro/CLI/モデル状態による Strata アプリケーション上の適用条件や cache はありません。

workflow によるタグ値の検証はなく、Summary への追記でエラーが起きた場合の回復処理もありません。追記先の失敗などでシェルのリダイレクトが失敗すれば Summary step は失敗します。タグ文字列だけを理由に終了する分岐はありません。

## 根拠

- `.github/workflows/docker-images.yml:12-18`: `workflow_dispatch` と必須の `release_tag` string input。
- `.github/workflows/docker-images.yml:70-81,105-114`: flavor ごとの image job、常時実行対象の Summary step、`INPUT_TAG` への input 設定、Bash の展開と summary 追記。
- `.github/workflows/docker-images.yml:97-104`: image の取得/build/push に渡す変数は `TAG` であり、`INPUT_TAG` は使われない。
- リポジトリ全体の `INPUT_TAG` 全参照検索: 上記 workflow の Summary 行と `env:` 設定のみ。実行コードや動的な env helper への参照なし。
