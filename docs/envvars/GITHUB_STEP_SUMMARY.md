# `GITHUB_STEP_SUMMARY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の実行バイナリや Python サーバーが読む環境変数ではありません。Strata リポジトリの GitHub Actions workflow `.github/workflows/docker-images.yml` が、Docker イメージ作成 job の Summary step でこの名前のシェル変数を展開し、リリース・push 状態・イメージタグの3行をそのパスへ追記します。

## 値と判定

workflow 内に値の parse、既定値、空値の補完、CLI 引数による上書きはありません。`GITHUB_STEP_SUMMARY` は step の `env:` で設定されず、そのまま引用符付きのシェル変数展開として追記先に使われます。

| 状態 | workflow の処理 |
|---|---|
| 通常のファイルパス | そのパスを追記先にして、Summary step の3行を書き込みます。引用符で囲まれているため、空白を含むパスも一つの追記先として扱います。 |
| 未設定または空文字 | workflow 側に fallback はありません。空の追記先となり、シェルのリダイレクトが失敗します。 |
| 書き込みできないパスなど | workflow 側に事前検証や回復処理はありません。リダイレクトの失敗は Summary step の失敗になります。 |

値の内容を `1` などと比較したり、文字列・数値として変換したりする処理はありません。

## 有効になる条件

この処理は通常の Strata 起動時には実行されず、手動起動専用の `Docker images` workflow の `image` job 内で実行されます。Summary step は `if: ${{ always() }}` のため、その job の先行 step の成否にかかわらず実行対象です。matrix の各 flavor に対して step が定義されています。

## 実行時の詳細

Summary step は `${{ matrix.flavor }}`、`${{ inputs.release_tag }}`、`${{ inputs.push }}` と `IMAGE` / `INPUT_TAG` を使って、flavor、release と push 状態、image tag を示す行を組み立てます。`INPUT_TAG` は同 step の `env:` で release tag から設定されます。組み立てた内容を `>> "$GITHUB_STEP_SUMMARY"` で追記します。workflow 自体に別ファイルへの転送、環境変数の再設定、summary 書き込みのエラー回復はありません。

この名前の参照はリポジトリ全体でこの1箇所です（`.github/workflows/docker-images.yml:112`）。C/C++、Python 等の Strata 実行コードでの直接読み取りや、名前を渡す汎用 env helper 経由の読み取りは確認できません。したがって、Strata アプリケーションの起動時期、cache、backend、CLI、モデル状態による環境変数動作はありません。

## 根拠

- `.github/workflows/docker-images.yml:1-4,12-14`: Docker images workflow は手動起動専用。
- `.github/workflows/docker-images.yml:70-81,105-114`: flavor ごとの image job、常時実行対象の Summary step、行の内容、追記先の展開。
- `GITHUB_STEP_SUMMARY` の全参照検索: `.github/workflows/docker-images.yml:112` のみ。
