# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は無効 |

## 役割

`strata runtime start` の結果を、人向けの表示ではなく1行の JSON として標準出力へ出します。runtime start 自体は保存済み profile をバックグラウンドサービスとして開始する操作です。`--json` はその操作を計画表示に変えたり、起動の副作用を抑えたりはしません。

## 使い方

```sh
strata runtime start --profile <profile名> --json
```

起動を行わず、起動候補の計画を JSON で確認する場合は `--plan` を併用します。

```sh
strata runtime start --profile <profile名> --plan --json
```

## 値と既定値

値は不要です。parser では `store_true` のフラグとして追加され、既定値は偽です（`strata_cli/cli.py:508-515`）。runtime start の parser にある `--output` は `human` / `json` を受け取り、既定値は `human` です（`strata_cli/cli.py:203-212`）。

## 実行時の動作

`--json` は runtime start 専用の宣言ではなく、複数の one-shot parser 群へ共通追加されます。その対象に `runtime_start` が含まれます（`strata_cli/cli.py:508-515`）。解析後、`--json` が指定され、コマンドが `status`、`monitor`、`logs`、`connection`、`config` 以外なら `a.output` を `json` に設定します（`strata_cli/cli.py:2232-2237`）。このため `--output human` と同時に指定しても `--json` が優先されます。

runtime start の処理では `a.output == "json"` を機械可読出力の選択として使います（`strata_cli/cli.py:1331-1334`）。通常の実行結果は `schema_version: 1` と runtime の結果フィールドを含む JSON として標準出力へ出され、成功時は終了コード 0、失敗時は結果の `exit_code`（なければ 6）を返します（`strata_cli/cli.py:1345-1373`）。`--plan` による成功結果は `_success` を通り、`schema_version: 1`、`ok: true`、`plan` を含む JSON になります（`strata_cli/cli.py:1357-1360`, `strata_cli/cli.py:535-542`）。

## 適用条件と副作用

このフラグは出力形式だけを切り替えます。`--plan` がなければ runtime start は通常どおりバックグラウンドサービスを起動し、端末終了後もサービスを継続します。`--plan` を付けた場合は起動候補を検査して計画を返し、実際の起動を行いません（`strata_cli/cli.py:197-212`, `strata_control/management.py:202-230`, `strata_control/runtime.py:518-530`, `strata_control/management.py:207-219`）。

JSON 選択時は `--quiet` の標準出力捕捉を通らず、通常の処理へ進みます（`strata_cli/cli.py:2236-2244`）。サービス側の標準出力と標準エラーは runtime のログファイルに追記されますが、これは start 処理の動作であり `--json` による追加副作用ではありません（`strata_control/runtime.py:548-574`）。

## 出力とエラー

runtime 操作で捕捉された例外は、機械可読モードでは `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を標準出力へ出し、同じ code を終了コードとして返します（`strata_cli/cli.py:527-532`, `strata_cli/cli.py:2166-2188`）。runtime start がエラー結果を返す場合も JSON の結果オブジェクトを出力し、その `exit_code` を返します（`strata_cli/cli.py:1359-1373`）。

未知の引数や parser の値エラーは `--json` の結果変換より前に処理されるため、argparse の usage / エラー表示となり、JSON 形式は保証されません（`strata_cli/cli.py:2223-2235`）。また、開始失敗時に人向け出力へ追加される engine log hint は JSON モードでは出力されず、JSON 結果に含まれる範囲が出力されます（`strata_cli/cli.py:1359-1372`）。

## 根拠

- `strata_cli/cli.py:203-212` — runtime start の parser と `--output` の値・既定値。
- `strata_cli/cli.py:508-515` — `--json` を含む共通 one-shot option の追加。
- `strata_cli/cli.py:1331-1373` — runtime 結果の JSON 化、計画結果、終了コード。
- `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2188`, `strata_cli/cli.py:2223-2244` — エラー出力、解析後の JSON 切替、quiet との関係。
- `strata_control/management.py:202-230` — start の plan / 実行の分岐と runtime への引き渡し。
- `strata_control/runtime.py:518-599` — background runtime の起動、ログへの出力、待機結果。

索引 `docs/cli/README.md` では `strata runtime start` の option として掲載されています（`docs/cli/README.md:388-400`）。この調査では同一 revision の CLI help や Release 配布物は確認していません。記述は上記ソース checkout の実装に基づきます。
