# `strata models list`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/models.py`、`strata_control/discovery.py` |

## 役割

既定では、Strata が認識するインストール先にある setup 生成のモデル run config を列挙し、参照コンポーネントの状態を読み取ります。モデルをロードしたり、ファイルを移動・コピー・ダウンロードしたりするコマンドではありません。`--served` を指定するとローカルのインストール一覧ではなく、接続先の現在の server instance が報告するモデル ID とロード状態を取得します。

## 使い方

```sh
# 認識されたインストール先のモデル設定候補を表示
strata models list

# 絶対パスで指定した既存のインストール先だけを JSON で調査
strata models list --installed --install-dir /absolute/Strata/install --output json

# 保存済み read-only connection の server instance を確認
strata models list --served --connection work --output json

# ローカル server を URL で指定して確認
strata models list --served --url http://127.0.0.1:8095
```

コマンド例の構文は `strata_cli/cli.py:141-152,508-515` の parser 定義に基づきます。モデル一覧を JSON で使う場合は `--output json` またはその alias の `--json` を使えます。

## 実行モード

| モード | 動作 |
| --- | --- |
| ローカル一覧（既定） | setup が書いた run config を既知のインストール先から探し、各候補の必須コンポーネントの存在・妥当性を検査して表示します。`--install-dir` を指定すると、そのディレクトリだけが対象です。 |
| served instance | `--served` で指定された URL または saved connection に read-only telemetry 要求を送り、現在の instance のモデル ID と loaded 状態を表示します。これはインストール済みモデル全体の一覧ではありません。 |

`--installed` は parser で受理されますが、既定の処理も `models.list_installed()` に進み、`a.installed` を参照する分岐はありません。そのため、現行実装ではこの指定による動作差は確認できません（`strata_cli/cli.py:144-146,564-596`）。索引にもこのフラグが掲載されています（[`docs/cli/README.md`](../../../README.md)）。

## 主な動作と注意点

- ローカル一覧は、明示した `--install-dir` または `STRATA_INSTALL_DIR` があればその場所だけを調べます。指定がなければ、Terminal の checkout / install、設定に記録された以前の install、Desktop app の install などを discovery 順に探します。同じ model ID が複数箇所にある場合は、先に見つかったものを採用します（`strata_control/models.py:62-82,185-210`、`strata_control/discovery.py:4-18,160-203`）。
- run config は install directory の直下にある `strata-<id>.json` が対象です。1 directory あたり最大128件を調査します。要件コンポーネントの有無は報告しますが、実行互換性は `unverified` としており、実際のモデルロードを保証しません（`strata_control/models.py:31-35,88-103,158-182`）。
- ローカル確認はファイル・設定の読み取りです。モデル構成ファイルの不正や必須項目の不足は候補ごとの `invalid` として一覧に残ります。明示した install directory が存在しない、絶対パスでない等の全体エラーは終了コード5で失敗します（`strata_control/models.py:62-72,106-129,191-205`）。
- `--served` は `/v1/telemetry` を優先し、未実装（HTTP 404）の場合に `/metrics` と `/v1/status`、または `/v1/status` のみへ fallback します。HTTP redirect は追従せず、認証情報は選択した環境変数から Bearer token として渡します（`strata_cli/client.py:79-132,134-153`）。
- served mode の URL は server root である必要があります。localhost / loopback 以外への接続には HTTPS が必要です。timeout は既定3秒、明示値は `0 < timeout <= 30` 秒です。URL、保存済み connection、credential environment variable の選択・validation は `strata_cli/connections.py:273-303` と `strata_cli/client.py:45-63` にあります。
- `--install-dir` は `--served` と併用できません。また `--url`、`--connection`、`--credential-env`、`--timeout` は `--served` がないとエラーになります（終了コード2、`strata_cli/cli.py:564-587`）。
- 成功時は既定で人間向けテキストを stdout に、`--output json` / `--json` では JSON を出力します。空のローカル一覧では調査場所と次の手段を案内します。served mode ではモデル ID がなければ “No model ID reported by this server” を出します（`strata_cli/cli.py:527-541,581-596`）。`--quiet` は人間向け成功出力を抑制しますが、JSON 出力には適用されません（`strata_cli/cli.py:508-515,2232-2248`）。
- parser 検証エラーや connection 設定エラーは stderr の `strata: ...` または JSON の error object で返ります。HTTP 通信・認証失敗は `ClientError` の終了コード（既定3、401/403 は4、schema 不整合などは5）で報告されます（`strata_cli/cli.py:527-531,2166-2188`、`strata_cli/client.py:38-42,117-132,140-144`）。

## 関連文書

- [`strata models` の一覧と各 option 文書](../../../README.md#strata-models-list-modelslist)
- [Terminal CLI のコマンド案内（Strata `docs/TERMINAL.md`）](../../../../../../../Niko1221/Strata/docs/TERMINAL.md) — ローカル一覧と served instance の利用例
- [モデル検出の説明（Strata `docs/TERMINAL_LAUNCH.md`）](../../../../../../../Niko1221/Strata/docs/TERMINAL_LAUNCH.md#models-you-already-have)

## 根拠と調査範囲

- `strata_cli/cli.py:141-152,508-515` — command parser、排他 scope、出力形式と `--json` / `--quiet` の追加。
- `strata_cli/cli.py:550-600,2119-2142,2166-2188,2217-2248` — local / served 分岐、出力、終了・エラー処理。
- `strata_control/models.py:62-82,88-129,158-210` — install 解決、候補の読取・検査、一覧と上限。
- `strata_control/discovery.py:4-18,112-203` — install 候補の探索順と読み取り専用 discovery。
- `strata_cli/connections.py:273-303`、`strata_cli/client.py:38-63,79-153` — served 接続設定、URL / timeout validation、read-only telemetry と fallback。
- Strata `docs/TERMINAL.md:16-28`、`docs/TERMINAL_LAUNCH.md:91-98` — 利用者向け説明との照合。

調査対象は上記 SHA の checkout です。調査では source parser と実装、同一 checkout 内の説明資料を確認しました。配布済み Release の CLI 実体や異なる OS での実行結果は確認していません。
