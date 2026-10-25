# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

成功時の人間向け説明を標準出力に出さないようにします。`models inspect` 自体は指定モデルのローカル run config と関連コンポーネントを読み取り、状態を表示するコマンドです。`--quiet` は検査内容やファイル探索を変えず、出力だけを制御します。

## 使い方

```sh
strata models inspect MODEL_ID --quiet
```

`MODEL_ID` はセットアップが作成した run config の ID です。別のインストール先を調べる場合は `--install-dir /absolute/path` を併用できます。

## 値と既定値

値は不要です。共通 parser 登録ループが `models_inspect` に `action="store_true"` の `--quiet` を追加し、既定値は `argparse.SUPPRESS` としています。そのため未指定時は namespace に値がなく、実行時の `getattr(a, "quiet", False)` が偽として扱います。`--quiet=true` のような値付き指定はこのフラグの構文ではありません。

## 実行時の動作

`main()` は `--quiet` が有効で出力形式が human の場合、`_run()` の標準出力を一時バッファへリダイレクトします。`models inspect` が成功すると、通常の human 要約は表示されません。`--output json` または `--json` を指定した場合は quiet でも JSON をそのまま標準出力へ出します。`--json` は one-shot コマンドで `--output json` の alias として処理されます。

このオプションは設定ファイルや環境変数の値を変更しません。inspect は run config を読み、コンポーネント検査の前後で config を再読込して同時変更を検出します。検査は参照先ファイルやディレクトリの存在・状態を確認しますが、`models.inspect()` は live probe を有効にせずコンポーネント検査を呼び出すため、engine の起動や GPU の live probe は行いません。`--install-dir` が明示されていればその絶対パスの既存ディレクトリを対象にし、省略時は既知のインストール先を探索します。

## 適用条件と副作用

この `--quiet` は `strata models inspect` parser に適用されます。検査自体は読み取り専用で、モデル設定やコンポーネントを移動・変更する処理は確認できません。quiet は成功時の人間向け標準出力を抑えますが、エラーを隠す指定ではありません。

## 出力とエラー

- human 出力で成功した場合、`--quiet` により inspect の要約は出力されません。
- `--output json` / `--json` では quiet を指定しても JSON 成功結果を出力します。
- `_run()` が例外をエラーへ変換する場合、human 形式のエラーは標準エラーへ出ます。quiet 実行中に失敗し、処理中に標準出力へ既に出た内容があると、その内容も標準エラーへ返されます。捕捉する標準出力は最大 64 KiB です。バッファが切り詰められた場合は省略を示すメッセージを標準エラーへ出します。
- 不明な引数などの parser エラーは `argparse` のエラー経路です。`--quiet` はエラーを無効化しません。

## 根拠

- `strata_cli/cli.py:153-156` — `inspect` parser と位置引数、`--install-dir`、出力形式の宣言。
- `strata_cli/cli.py:508-515` — 共通 one-shot parser 登録。`models_inspect` を含むループが `--quiet` と `--json` を追加。
- `strata_cli/cli.py:550-603` — `models inspect` の dispatch、`models.inspect()` 呼び出し、human / JSON 成功出力。
- `strata_cli/cli.py:527-542` — 成功・エラーの stdout / stderr と戻り値の処理。
- `strata_cli/cli.py:2170-2193` — 例外をエラー出力へ変換する経路。
- `strata_cli/cli.py:2196-2214` — quiet 用 stdout 捕捉バッファ（64 KiB）。
- `strata_cli/cli.py:2223-2248` — `--json` の変換、quiet 時の stdout 抑制と失敗時の再出力。
- `strata_control/models.py:62-72` — 明示インストール先の検証と既定の探索。
- `strata_control/models.py:106-129,173-182,213-229` — run config の読み取り、コンポーネント検査、ID 検索と inspect 結果の構築。
- `strata_control/doctor.py:1,146-235` — コンポーネント検査は read-only inventory で、live probe は `live=True` の場合だけ行う。
