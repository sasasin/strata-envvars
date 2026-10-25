# `strata ops runs --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。省略時は無効 |

## 役割

成功したときの人間向け一覧出力を抑制します。失敗の報告は抑制しません。

## 使い方

```sh
strata ops runs --profile default --quiet
```

## 値と既定値

値は不要です。指定すると真、未指定では `quiet` 属性を作らず、実行時に偽として扱われます。`--quiet` の重複指定による追加効果はありません。`strata ops runs` は必須の `--profile`、出力形式 `--output {human,json}`（既定値 `human`）、および整数の `--limit`（既定値 `20`）を受け付けます。`--limit` の有効範囲は 1〜100 で、範囲外はエラーになります。

## 実行時の動作

`ops` の各サブコマンド parser に共通の one-shot オプションとして `--quiet` が追加されます。`runs` は `journal.list_runs(profile, limit=...)` を呼び、結果を人間向けには operation ID と state（またはレコード error）で表示します。成功時、quiet はこの stdout を抑制します。`--json` は `--output json` の alias で、JSON 出力時は quiet を指定しても JSON レコードが stdout に出ます。空の一覧では通常 `No operation runs recorded` と出ますが、quiet の人間向け成功出力では空になります。

## 適用条件と副作用

対象は `strata ops runs` の一回実行です。journal は profile の `.ops/<profile>/.runs` ディレクトリから読み取られ、更新・削除はしません。journal ディレクトリが存在しない場合は空一覧になります。ディレクトリはシンボリックリンクであってはならず、POSIX では所有者専用であることも検査されます。既存 JSON レコードは更新時刻の新しいものから `--limit` 件まで読みます。個々の不正レコードは一覧全体を止めず、その項目に error を載せます。

## 出力とエラー

人間向け成功出力は quiet により stdout から隠されます。JSON 出力は隠されません。範囲外の `--limit`、profile の読み込み失敗、不正な journal ディレクトリなどのエラーは通常の CLI エラー経路に入り、quiet でも stderr に報告されて非ゼロ終了コードになります。引数の型・構文エラーは `argparse` が処理します。

## 根拠

- `strata_cli/cli.py:255-270` — `ops runs` の parser、必須 profile、output 既定値、`--limit` の型と既定値。
- `strata_cli/cli.py:508-515` — 全 `ops` parser を含む one-shot parser への `--quiet` / `--json` 追加。
- `strata_cli/cli.py:535-542` — 人間向け／JSON 成功出力。
- `strata_cli/cli.py:1391-1408` — `runs` の一覧取得と成功時出力。
- `strata_cli/cli.py:2166-2188,2232-2247` — 例外をエラー出力へ変換する経路、JSON 出力時は quiet 捕捉を通らない処理。
- `strata_control/journal.py:47-57,254-273` — journal ディレクトリの検査、limit 範囲、未作成時の空一覧、更新時刻順の読み取り、不正レコードの項目化。
- 索引上の配置と scope: `docs/cli/README.md:585-594`。

調査対象 checkout は `main...origin/main` で未コミット変更なしでした。Release artifact と同一 revision の `--help` 出力は照合していません。
