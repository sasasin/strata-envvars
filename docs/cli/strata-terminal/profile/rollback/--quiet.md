# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

rollback 成功時の人間向け完了メッセージを標準出力に表示しない。rollback の実行や保存内容そのものには影響しない。

## 使い方

```sh
strata profile history demo
strata profile rollback demo --to 0123456789abcdef --quiet
```

`--to` には `profile history` で確認した、復元したい16桁の revision を指定する。上の revision は形式を示す例であり、実在する履歴を選ぶ必要がある。

## 値と既定値

- `--quiet` は `argparse` の `store_true` フラグで、値を取らない。省略時は偽、指定時は真になる。rollback parser への追加時に `default=argparse.SUPPRESS` が指定されているため、省略時は属性を作らず、実行時の `getattr(a, "quiet", False)` が偽として扱う。
- 複数回指定しても真のまま。`--quiet=true` のような値付き指定はこの parser では受理されない。
- `--quiet` は `--json`、`--output`、必須の `--to REVISION` と共存できる。`--json` は `--output json` の alias として扱われ、JSON 出力時には `--quiet` があっても機械可読出力を抑止しない。

## 実行時の動作

rollback 専用 parser には `--to` と `--output` が定義され、その後、one-shot parser の共通設定として `--quiet` と `--json` が登録される。したがってこのフラグの scope は `strata profile rollback` である。

人間向け出力で `--quiet` が有効な場合、CLI はコマンドの標準出力を一時捕捉する。成功時は捕捉した完了メッセージを捨てる。rollback 成功時の通常メッセージは `Restored profile NAME: OLD -> NEW; running instances are unchanged`。

処理は引き続き実行される。指定 revision が有効で現在値と異なる場合、profile の現在内容を履歴に保存してから選択した履歴内容を profile ファイルへ書き戻す。実行中の instance は変更されない。同じ内容への rollback では保存関数が変更なしと判定し、profile を書き換えない。

## 適用条件と副作用

- `--to` は必須で、値は小文字16進数16桁の revision に限られる。対象履歴は通常ファイルであり、ファイル内容の SHA-256 先頭16桁がファイル名の revision と一致し、profile として検証できなければならない。
- rollback は保存 profile を読み、対象履歴を検証し、保存関数で更新する。保存時には profile ディレクトリの lock を使い、変更がある場合は現在 profile の履歴コピーと新しい profile を一時ファイル経由で置換する。指定 profile の保存内容が変更されるが、参照元 run config や稼働中 instance は書き換えない。
- 保存関数は参照元 run config も読み込んで検証するため、そのファイルが利用できない場合は更新に失敗し得る。通常の profile 読み込みには、権限を修復して読み込む経路もある。
- JSON (`--json` または `--output json`) の場合、成功 JSON は `--quiet` でも stdout に出る。JSON 出力では `--quiet` による stdout 捕捉を行わない。

## 出力とエラー

- 人間向け成功出力: `--quiet` なしでは復元元・復元先 revision を含む完了文を stdout に出す。`--quiet` ありでは成功文を抑える。
- JSON 成功出力: `--quiet` の有無によらず stdout に成功結果 JSON を出す。
- 失敗: 引数不足・形式不正など argparse の parser エラーは usage とエラーを表示し、終了コード 2。profile/履歴がない場合や内容が不正な場合は CLI のエラー経路からメッセージを stderr に出し、通常は終了コード 2 または `ProfileError` が割り当てた 5/6 を返す。`--quiet` は失敗を無音にせず、処理中に stdout へ出た内容があれば失敗時に stderr へ転送する。捕捉量が64 KiBを超えると末尾だけが保持され、stderr に「earlier human output omitted in quiet mode」の注記が加わる。

## 根拠

- `strata_cli/cli.py:102-105` — rollback parser、位置引数、必須 `--to`、既定 `--output`。
- `strata_cli/cli.py:508-515` — `profile_rollback` を含む one-shot parser への `--quiet` / `--json` 追加。
- `strata_cli/cli.py:958-1014` — profile command の dispatch と rollback 成功出力。
- `strata_cli/cli.py:535-542`、`strata_cli/cli.py:2119-2193` — 成功出力と例外・エラー処理。
- `strata_cli/cli.py:2196-2214`、`strata_cli/cli.py:2225-2248` — quiet 時の stdout 捕捉上限と失敗時の転送、`--json` の出力選択。
- `strata_control/profiles.py:150-165` — profile 読み込み、regular file 検査、アクセス修復読み込み。
- `strata_control/profiles.py:185-233` — 保存 lock と atomic replace。
- `strata_control/profiles.py:266-295` — run config の再検証、競合検査、履歴保存と profile 更新、変更なしの場合の処理。
- `strata_control/profiles.py:326-346` — rollback revision の検証、履歴読み込み、profile 保存。
