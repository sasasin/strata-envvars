# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False` |

## 役割

`strata serve` の人間向け情報出力を抑えます。前景サーバーの起動・稼働・終了時に標準出力へ出る情報を隠しながら、失敗や終了時の簡潔な診断は標準エラーに残します。parser の説明は「人間向け情報出力を抑制」です（`strata_cli/cli.py:67`）。

## 使い方

```sh
strata serve --profile ./run-config.json --quiet
```

`--profile`（alias `--config`）で既存 run config または保存済み profile を指定します。`--quiet` 自体に引数は付けません（`strata_cli/cli.py:46-48,67`）。

## 値と既定値

- `action="store_true"` であり、指定すると真、指定しなければ偽です。別名や値の選択肢はありません（`strata_cli/cli.py:67`）。
- `--quiet=false` のような値付き構文はこの parser では定義されていません。無効な引数は argparse が拒否します（`strata_cli/cli.py:2223-2231`）。
- 複数回指定した場合の独自処理はありません。真偽値フラグとして同じ値になります。

## 実行時の動作

- **通常の前景実行（`--plan` なし）:** 人間向けサーバー出力を `os.devnull` にリダイレクトします。標準エラーはリダイレクトしません。終了コード 8 なら drain 期限切れと要求キャンセルの説明を、他の非 0 終了なら終了コードを標準エラーに出します（`strata_cli/cli.py:900-912`）。
- **`--output jsonl`:** 起動・ready・停止・失敗などの JSONL lifecycle event は標準出力に出したまま、サーバー側の人間向け標準出力だけを抑えます。JSONL 出力の受け手が閉じても、サーバーを止めず以後の event 書き込みを止める処理があります（`strata_cli/cli.py:838-873,851-866`）。例外時の簡潔な診断は標準エラーに出ます（同 `:874-889`）。
- **`--plan` と人間向け出力:** main が標準出力を最大 64 KiB の捕捉領域に向け、成功時は表示しません。失敗して捕捉済み出力があるときは標準エラーに出し、捕捉上限を超えた場合は省略通知も出します（`strata_cli/cli.py:2196-2214,2236-2247`）。
- **機械可読出力:** `--output json` または `--output jsonl` の場合、main は `--quiet` による通常の stdout 捕捉を行いません（`strata_cli/cli.py:2232-2243`）。したがって JSON の計画結果や JSONL event は抑制対象ではありません。parser の help は `--json` を `--plan --output json` の alias と説明しますが、確認した実装では `--json` により `output` を `json` にするだけで `plan` は有効になりません。このため `--json` 単独では `_serve` の `--output json requires --plan` エラーになり、`--plan --json` なら JSON 計画出力になります（`strata_cli/cli.py:66,915-917,2232-2235`）。

## 適用条件と副作用

- `--quiet` は `strata serve` parser に属します。他のサブコマンドでの同名フラグの動作はこの文書の対象外です。索引も `strata serve` 配下の独立した option として掲載しています（[`docs/cli/README.md`](../../README.md) の `strata serve` 節）。
- `--output json` は `--plan` と併用する必要があり、`--output jsonl` は `--plan` と併用できません。parser help の `--json` 説明と実装にも差があり、`--json` 単独ではこの JSON/plan 条件を満たしません。これらの条件は `--quiet` でも変わりません（`strata_cli/cli.py:66,915-919,2232-2235`）。
- 前景サーバーそのものの実行、設定の読み込み、ネットワーク待受などの副作用は停止しません。`--quiet` は出力先を変えるだけで、起動を計画表示だけにする機能ではありません（計画のみの動作は別の `--plan`、同 `:63,900-912,940-953`）。
- server の標準エラーは破棄されないため、server がそこへ書くメッセージは表示されることがあります。確認できた実装は標準出力のみをリダイレクトします（`strata_cli/cli.py:903-912,870-873`）。

## 出力とエラー

- 通常の前景実行では成功時の人間向け stdout を抑制し、終了コードが非 0 の場合は CLI の簡潔な説明を stderr に出します。終了コード 8 には drain 期限切れの説明を出します（`strata_cli/cli.py:903-911`）。
- `--output jsonl` の前景実行は JSONL の `starting` / `ready` / `stopping` / `draining` / `stopped` / `failed` event を stdout に出します。起動失敗、割り込み、例外は失敗 event と終了コードへ反映され、例外型など一部の診断は stderr に出ます（`strata_cli/cli.py:843-889`）。
- 引数値の検証、profile 読み込みなど前景実行の前に起きる失敗は、JSONL では failed event、それ以外では共通エラー処理に進みます（`strata_cli/cli.py:829-835,915-939,2166-2193`）。JSON 出力時は machine-readable error に切り替わります（同 `:829-835`）。
- CLI 全体の出力や全ての依存処理が静かになるわけではありません。抑制の実装対象はこのコマンドが標準出力へ流す人間向け出力です。

## 根拠

- `strata_cli/cli.py:46-67` — `serve` parser、コマンドスコープ、`--quiet` の値規則と説明。
- `strata_cli/cli.py:829-835,838-897` — JSONL error/event、human stdout 抑制、例外・失敗経路。
- `strata_cli/cli.py:900-955` — foreground quiet の stdout/stderr と終了コード、plan 実行。
- `strata_cli/cli.py:2119-2193,2196-2247` — serve への dispatch、共通失敗処理、quiet 捕捉と機械可読出力の例外。
- `docs/cli/README.md` の `strata serve` 節 — この文書のリンクと option scope。
- `docs/cli/001_investigation.md` の「文書の一意な配置規約」「各オプション文書の内容」— 配置・記載基準。
