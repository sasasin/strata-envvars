# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`、既定値 `false`） |

## 役割

`strata serve` の計画表示を機械可読な JSON にするためのフラグです。現行実装では `--output json` を選ぶ効果がありますが、`--plan` は自動で有効になりません。そのため実際には `--json --plan` のように併用します。

## 使い方

```sh
strata serve --profile CONFIG.json --json --plan
```

同じ計画出力は `strata serve --profile CONFIG.json --plan --output json` でも選べます。`--profile`（別名 `--config`）は parser で必須です。

## 値と既定値

値は取りません。parser は `action="store_true"` を指定しているため、省略時は `false`、指定時は `true` です。複数回指定しても真偽値が変わるだけで、反復回数による追加効果はありません。値を後ろに付ける構文はありません。

## 実行時の動作

トップレベルの dispatch 前処理は、`strata serve` で `--json` が真なら `output` を `json` に設定します。ただし `plan` の値には触れません。その後 `_serve` は `output=json` かつ `plan` が偽の場合にエラーを返します。したがって parser の help にある「`--plan --output json` の alias」という説明と異なり、現行実装の `--json` 単独指定では計画表示になりません。

`--json --plan` の場合、`_serve` は launch plan を組み立てて server を起動せず、`{"schema_version":1,"ok":true,"plan":...}` 形式の JSON を stdout に出して終了コード `0` を返します。計画には profile 情報、実効設定とその由来、server/engine の argv、ready-file、notes などが含まれます。`--quiet` を併用しても `output=json` の経路では標準出力は抑制されません。

## 適用条件と副作用

このフラグは `strata serve` の parser に属し、値を server の引数として転送するオプションではありません。`--output jsonl` を同時に指定すると、前処理は JSONL のまま `--json` を拒否し、foreground event 用には `--output jsonl` を使うよう案内します。

正常な `--json --plan` 経路は server や inference engine を起動しません。ただし計画生成では profile/run config の読み込み、設定の検証、engine argv の組み立てが行われます。また `--ready-file` を同時に指定した場合は、絶対パス・親 directory の存在・対象が未作成であることを preflight で確認します。この preflight 自体はファイルを作成しません。

## 出力とエラー

- `--json` 単独では `_serve` が `--output json requires --plan; use --output jsonl for foreground events` をエラーとして返します。JSON 出力は `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` 形式で、終了コードは `2` です。
- `--json --output jsonl` は JSONL の `failed` event（`schema_version: 1`、`exit_code: 2`、`error.message` を含む）を stdout に出して終了コード `2` を返します。
- 不正な設定など計画組み立て中の `ValueError` は、通常の `_run` の例外処理を通り、JSON 形式のエラーと例外の `exit_code`（属性がなければ `2`）になります。
- `--json --plan` の成功出力は `_success` が JSON 1行として stdout に出します。JSON の形式・キーは実装上の出力であり、別の安定性保証はこの調査範囲では確認できません。

## 根拠

- Strata `strata_cli/cli.py:46-67` — `serve` parser、必須 profile、`--plan`・`--output`・`--json` の定義と help 文。
- Strata `strata_cli/cli.py:527-542` — JSON success/error envelope と終了コード。
- Strata `strata_cli/cli.py:782-826` — launch plan の作成、設定由来・server argv・engine argv の収集、ready-file preflight 呼び出し。
- Strata `strata_cli/cli.py:829-835,915-955` — serve のエラー形式、JSON/JSONL と plan の条件、計画表示または foreground 起動の分岐。
- Strata `strata_cli/cli.py:2232-2236` — `--json` で `output` を `json` に変える処理。`plan` は変更しない。
- Strata `serve/ready.py:16-24` — ready-file preflight の検査内容。ファイル作成は `publish` 側の別処理。
- `docs/cli/README.md` — `strata serve` の `--json` 文書リンクとコマンド scope。

調査時点の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されません。Release 配布物との照合および実行中 CLI の help 表示は行っていません。parser の help 文と実際の `--json` 処理との相違は、上記 commit のソースで確認した範囲の記述です。
