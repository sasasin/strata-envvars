# `ANTHROPIC_SMALL_FAST_MODEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

Strata 自身がこの名前の環境変数をプロセス環境から読み取る箇所は見つかりませんでした。候補名の唯一の参照は `strata connect claude-code` が Claude Code 用設定を生成する箇所で、サーバーに指定したモデル名を `ANTHROPIC_SMALL_FAST_MODEL` の値として設定 JSON に出力します。従って、これは Strata のエンジンやサーバーの環境変数として動作を変える設定ではありません。出力先アプリがこの設定をどう解釈するかは本調査の対象外です。

## 値と判定

| 項目 | Strata の処理 |
|---|---|
| Strata プロセス環境での未設定・空文字 | この名前を `getenv` / `os.environ` 等で読む処理はないため、Strata は判定しない。 |
| 設定ファイルへ出す値 | `t.model` を文字列値としてそのまま格納する。環境変数としての parse、数値変換、空文字検査、範囲制限はない。 |
| モデル名の供給元 | `strata connect` の `--model`、起動情報（preset を含む）の model、既定の `strata` の順。`harness.target()` でも falsy な model は `strata` に補完される。 |

ここでの「既定」は Strata が設定ファイルを作る際のモデル名の既定値です。実行時の Claude Code や Strata サーバーが未設定値をどう扱うかを示すものではありません。

## 有効になる条件

この設定値が生成されるのは、Claude Code harness (`claude-code`) の設定を表示・書き出す経路です。OS、GPU backend、build macro、モデルのロード状態には依存しません。`strata connect` の `--model` などで選んだモデル名を出力へ反映します。

## 実行時の詳細

`claude_env(t)` は `ANTHROPIC_SMALL_FAST_MODEL` を含む環境設定辞書を組み立てます。`claude_file(t)` はその辞書を JSON の `env` オブジェクトにして、`~/.claude/settings.json` 向けのファイル仕様として登録されています。`strata connect claude-code` の通常表示では `Environment:` の項目にも辞書の値を表示し、`--output json` では `env` と生成ファイル内容を返します。これらは設定内容の表示・生成であり、Strata がこの変数を自身のプロセスや起動した子プロセスに設定する処理ではありません。

`--write` を指定すると、通常は確認後に JSON 設定を書き込みます（非対話時は `--yes` がないと stderr に確認方法を出して終了コード 2）。対象 JSON が既にある場合、Strata は先にバックアップを作り、JSON merge により生成した `env` のキーを優先して書きます。書き込み後は作成または merge の結果を表示します。設定値をいつ読むか、空文字や無効値をどう扱うかは Strata コードでは定義していません。

## 根拠

- `strata_cli/launch/harness.py:111-120` — Claude Code 用辞書に `ANTHROPIC_SMALL_FAST_MODEL: t.model` を設定し、JSON の `env` オブジェクトを生成。
- `strata_cli/launch/harness.py:229-231` — Claude Code harness が `~/.claude/settings.json`、`claude_file`、`claude_env` を使用。
- `strata_cli/launch/harness.py:272-280` — falsy なモデル名を `strata` に補い、harness のファイルと環境設定を描画。
- `strata_cli/launch/cmd.py:945-951` — `--model`、起動情報、`strata` の順にモデル名を選び、設定を描画。
- `strata_cli/launch/cmd.py:978-991` — 人間向け出力で生成ファイルと環境設定を表示。
- `strata_cli/launch/cmd.py:1011-1028`, `strata_cli/launch/harness.py:288-320` — `--write` の確認と、既存 JSON のバックアップ・merge・書き込み処理。
- 候補名の全参照検索（`rg -n --hidden --glob '!.git/**' 'ANTHROPIC_SMALL_FAST_MODEL'`）では、本項の `harness.py:113` のみ。Strata 所有コード中にこの値を環境から読む箇所は確認できませんでした。
