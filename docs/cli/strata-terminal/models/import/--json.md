# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models import` |
| オプション | `--json` |
| 別名 | `--output json`（同じ出力形式を選ぶ別指定。parser 上の alias ではない） |
| 値 | 値なしの真偽フラグ。省略時 `false` |

## 役割

GGUF ファイルの取り込みプレビュー結果を機械可読な JSON で標準出力に出します。このコマンドは `--plan` が必須で、モデルを採用・コピーする処理ではありません。

## 使い方

```sh
strata models import /absolute/path/to/model.gguf --plan --json
```

`PATH` は GGUF ファイル、分割 GGUF のいずれかの shard、またはモデルファイルを含むディレクトリを指定します。`--plan` は parser で必須です。

## 値と既定値

- `--json` 自体は値を取りません。指定すると `--output json` と同じ形式になります。どちらも省略した場合、`--output` の既定値 `human` が使われます。
- `--json` と `--output human` を併記しても、one-shot 共通処理が `--json` を優先し、出力形式を `json` にします。`--output` が受け付ける値は `human` / `json` です。
- `--json` を重ねても真偽フラグのままです。`--json false` のように値は指定できません。

## 実行時の動作

成功時、標準出力に `schema_version: 1`、`ok: true`、`plan` を含む1つの JSON オブジェクトを出し、終了コード `0` を返します。問題が見つかった場合も JSON 出力を選んでいれば `schema_version: 1`、`ok: false`、`plan` を出し、終了コード `5` を返します。`plan` にはファイル情報、候補選択、問題、実行互換性が未検証であることなどが含まれます。

`--json` は表示形式だけを選びます。処理本体は `models.plan_import(PATH)` でローカルの候補を調べます。相対パスは拒否され、GGUF のファイル集合・ヘッダー・限定されたメタデータを検査します。確認対象は GGUF v3 のメタデータ、tensor directory と宣言された範囲などで、tensor payload 全体の読込みや由来の検証、エンジンでのロード確認は行いません。既知の shard 名やヘッダー一致は候補のヒントであり、互換性の保証ではありません。

## 適用条件と副作用

- `--plan` を省略すると、`argparse` が必須引数不足として usage とエラーを標準エラーに出して終了します。`--json` 付きでも、この parser 段階の失敗は JSON 形式にはなりません。
- preview は読み取り専用です。計画結果に `would_write: false` が含まれ、モデルの採用・コピー・ダウンロード・修復・エンジン起動はしません。ディレクトリ指定ではモデル候補を探し、同一フォルダにある `mmproj` は補助ファイルとして報告対象にします。
- 選択した形式は `--quiet` より優先されます。JSON 出力時は quiet 用の人間向け標準出力抑制経路に入りません。

## 出力とエラー

- 候補の検査で問題が見つかった場合、JSON では `ok: false` と `plan` を標準出力に出し、終了コード `5` です。人間向け形式では問題説明を標準エラーに出します。
- パスが相対パスなら `ProfileError` の既定終了コード `2`、パスが存在しない場合や GGUF として読めない場合などはコード `5` の失敗になります。通常の実行時例外は `--json` の指定を参照して `error` オブジェクトに変換されます。
- `--output` に未対応の値を渡す、または `--plan` を省略するなど parser の引数エラーは `argparse` が処理し、JSON レコードにはなりません。

## 根拠

- `strata_cli/cli.py:157-161` — `models import` の位置引数、必須 `--plan`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — `models_import` を one-shot parser 群に含め、値なし `--json` と `--quiet` を追加。
- `strata_cli/cli.py:2232-2237` — `--json` が `--output json` を上書き設定し、JSON/JSONL 出力時は quiet 捕捉を通さない処理。
- `strata_cli/cli.py:527-542,550-561` — 成功・問題ありの JSON 形式、標準エラー、人間向け表示と戻り値。
- `strata_cli/cli.py:2166-2188`、`strata_control/profiles.py:30-35` — 例外を JSON エラーへ変換する経路と `ProfileError` の既定コード。
- `strata_control/models.py:579-640,656-695,720-736` — 入力パス、候補の検査、対応条件、読み取り専用 preview の結果項目。
- `strata_control/models.py:232-250,438-472,475-506` — GGUF ヘッダー検証とディレクトリ・ファイル探索の上限。
- `strata_control/gguf_preflight.py:1-5,18-25,105-140` — 有界メタデータ検査の範囲と tensor payload を読まない境界。
