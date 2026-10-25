# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

人向けの通常出力を抑制します。`models list` ではモデル一覧または「モデルが見つからない」案内の標準出力を抑えます。parser の共通 one-shot オプションとしてこのコマンドにも登録されています（`strata_cli/cli.py:508-515`）。

## 使い方

```sh
strata models list --quiet
```

このオプションは `models list` の引数です。`strata models list --quiet --output json` のように機械可読出力と併用できます。

## 値と既定値

値は不要です。`action="store_true"` で登録され、オプションを省略した場合の実効値は偽です。`default=argparse.SUPPRESS` により省略時には属性自体を作らず、実行時に `getattr(a, "quiet", False)` で偽として扱います（`strata_cli/cli.py:514-515`, `2236-2243`）。値の範囲や追加の validation はありません。短縮 alias は定義されていません。

## 実行時の動作

`main()` は `--quiet` が有効で、かつ `output` が `json` / `jsonl` ではない場合、標準出力を一時バッファへ向けてコマンドを実行します。成功時はバッファの内容を表示しないため、人向け一覧が出ません。機械可読出力を選んだ場合はこの抑制経路を使わず、JSON を通常どおり標準出力へ出します（`strata_cli/cli.py:2232-2248`, `535-542`）。

`--quiet` は一覧の探索方法や内容を変えません。ローカル一覧では `models.list_installed()` が設定候補を列挙・検査し、サーバー一覧では `Endpoint.snapshot()` を取得した後にモデル ID とロード状態を表示用に整形します（`strata_cli/cli.py:564-596`; `strata_control/models.py:185-210`）。`--served` のサーバー問い合わせやローカル設定ファイルの読み取りも引き続き行われます。

## 適用条件と副作用

`--quiet` は `strata models list` parser にのみ追加されるフラグで、`models` の親 parser ではなく list の one-shot parser に登録されています（`strata_cli/cli.py:141-152`, `508-515`）。`--output json`（または `--json`）と併用すると JSON は抑制されません。`--json` は `output` を `json` に正規化し、quiet の標準出力抑制条件から除外されます（`strata_cli/cli.py:2232-2237`）。

フラグ自体が行うのは出力制御です。ローカル一覧は設定ファイルとコンポーネント状態を調べる読み取り経路で、サーバー一覧を選んだ場合は read-only telemetry endpoint を呼び出します（`strata_control/models.py:185-210`; `strata_cli/client.py:101-152`）。サーバー通信などコマンド本体の副作用・失敗可能性は、このフラグでは取り除かれません。

## 出力とエラー

- 人向け出力は標準出力に出ません。コマンドが失敗しても、quiet は標準エラーをリダイレクトしないため、通常のエラー診断は標準エラーに残ります（`strata_cli/cli.py:527-532`, `2236-2248`）。quiet の実行中に標準出力へ出た内容があり、終了コードが非 0 の場合は、その内容を標準エラーへ戻します。捕捉上限 64 KiB を超えた場合は省略通知も出ます（同 `2196-2214`, `2241-2248`）。
- 例として、ローカル一覧に `--served` 専用の接続指定を渡した場合、または `--served` と `--install-dir` を組み合わせた場合は終了コード 2 で拒否されます（`strata_cli/cli.py:565-587`）。ローカルインストール先の validation エラーは `ProfileError`（`ValueError` 派生）として処理され、既定の終了コードは 2 です（`strata_control/models.py:62-72`; `strata_control/profiles.py:30-35`; `strata_cli/cli.py:2166-2173`）。サーバー接続では URL・timeout・応答などにより診断と失敗コードが異なります（`strata_cli/connections.py:273-302`; `strata_cli/client.py:101-152`）。
- `--output json` と併用した場合は、人向け出力抑制の分岐に入らず、成功・失敗の JSON が標準出力へ出ます（`strata_cli/cli.py:2232-2237`, `527-542`）。

## 根拠

- parser と共通 option の追加: `strata_cli/cli.py:141-152`, `508-515`
- quiet の実効値、JSON との相互作用、標準出力捕捉・失敗時の復元: `strata_cli/cli.py:2232-2248`, `2196-2214`
- `models list` のローカル／served 分岐と成功表示: `strata_cli/cli.py:564-596`
- ローカル一覧処理: `strata_control/models.py:185-210`
- served の telemetry 取得: `strata_cli/client.py:101-152`
- connection 解決と timeout の検証: `strata_cli/connections.py:273-302`
- エラー表示と `ProfileError` の既定終了コード: `strata_cli/cli.py:527-532`, `2166-2188`; `strata_control/profiles.py:30-35`
