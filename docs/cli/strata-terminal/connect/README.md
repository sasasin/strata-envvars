# `strata connect`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| 主な実装 | `strata_cli/launch/cmd.py`、`strata_cli/launch/harness.py`、`strata_cli/launch/check.py` |

## 役割

Strata サーバーを利用する対応アプリ（harness）の設定例と環境変数を表示し、必要なら設定ファイルへ書き込みます。`strata connect` 単体では対応アプリを一覧表示し、アプリ名を付けると、そのアプリ向けの設定を表示します。`--check` では設定対象のサーバーへ実際にリクエストを送り、`--write` では設定ファイルを作成・更新します。このコマンド自身がサーバーや外部アプリを起動する動作は確認できません。

## 代表的な使い方

```sh
# 対応アプリを一覧表示
strata connect

# OpenCode 向けの設定と環境を表示
strata connect opencode

# 接続先を指定して設定を表示
strata connect codex --url http://127.0.0.1:8080 --model strata

# サーバーへ prompt と tool call を送り、設定が機能するか確認
strata connect opencode --check

# 対話確認を省略して設定ファイルを書き込む
strata connect opencode --write --yes
```

利用可能な名前は `opencode`、`codex`、`claude-code`、`omp`、`pi`、`hermes`、`openclaw`、`deepseek-harness` です。いくつかの別名も登録されています（例: `claude`、`oh-my-pi`、`dsh`）。各アプリのファイル位置・生成内容・注意点はコードの harness 定義に従います。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 対応アプリ一覧 | `strata connect` | 対応名、接続プロトコル、状態を人間向け表または JSON で表示します。 |
| 設定表示 | `strata connect opencode` | アプリ用ファイルの内容、必要な環境変数、既知の注意点、インストール・実行例を表示します。設定ファイルは変更しません。 |
| 接続確認 | `strata connect opencode --check` | アプリが使う wire format で短い prompt と tool call を各 1 回送ります。アプリ自体は起動しません。 |
| 設定書込 | `strata connect opencode --write` | 既定では確認後にファイルを作成・更新します。`--yes` を加えると確認を省略します。 |

## 接続先と設定の決まり方

指定 harness が有効な場合、接続 URL は `--url`、実行中の Strata launch または `--preset` から得た情報、既定の `http://127.0.0.1:8080` の順で選ばれます。URL 末尾の `/v1` は取り除いてサーバールートとして扱います。key は `--key`、`--key-env` で指定した環境変数、launch/preset の key、空文字列の順です。key がない設定を生成する場合、harness 側で `strata-local` という非秘密の placeholder が使われます。model と context は明示値、launch 情報、既定値 `strata` / 32K の順です。`--context` は `k` / `m` 付きサイズまたは token 数を受け取り、parser の変換で 1,024 未満は拒否されます。

`--preset NAME` はその名前に対応する実行中 launch または保存済み preset の情報を選ぶために使います。`--url` や `--key` 等の明示値は、得られた情報より優先されます。引数なしの一覧表示は harness 一覧だけを返し、接続先の解決や通信を行いません。

## 主要な動作と副作用

- `--check` は `/v1/responses`、`/v1/messages`、または `/v1/chat/completions` に prompt と tool call を POST します。返答に `pong` が含まれるか、`get_weather` の引数に Paris が含まれるかを判定します。各リクエストの timeout は既定で 240 秒です。結果は接続確認であり、外部アプリを実際に起動するテストではありません。
- `--write` は harness が列挙するファイルを作成し、既存ファイルがあれば `<ファイル名>.strata-bak-<時刻>` へコピーしてから書き込みます。JSON merge 対象として定義されたファイルは既存キーを残し、新しい設定値を優先します。書込後は可能な環境でファイル mode を `0600` にします。key を含み得る設定ファイルを対象にするため、書込先とバックアップを確認してください。
- `--yes` は `--write` の対話確認だけを省略します。`--write` がなければファイル書込を開始しません。`--write` を対話端末以外で `--yes` なしに実行すると stderr に案内を出し終了コード 2 になります。確認への回答が `y` / `yes` 以外なら何も書かず正常終了します。
- `deepseek-harness` は Strata app 内蔵で、この harness には書込ファイルがないため、`--write` を付けても「Nothing to write for this app.」と表示して終了します。
- `--output json` は構造化 JSON を出力します。JSON 出力では `--show-key` の指定にかかわらず生成設定中の key はマスクされます。人間向け表示では通常 key をマスクし、`--show-key` 指定時は実際の値を表示するため、共有ログ等に残さないよう注意してください。

## 出力と失敗

未知の harness 名は候補名を含む診断を stderr に表示して終了コード 2 になります。`--check` の失敗は人間向け表示では各チェックを `FAIL` として示し終了コード 1、JSON では `ok: false` と `error` を出して終了コード 1 です。サーバーへ到達できない場合、HTTP 401/403、404、その他の HTTP エラーは異なる説明に変換されます。`--check` が成功した場合は終了コード 0 です。

JSON 出力で `--check` を指定しない場合は、設定内容を JSON で出して終了します。`--check` と `--write` を同時に指定した場合は、先に疎通確認を行い、失敗すると書込処理へ進みません。確認できた範囲では、書込時の個別ファイル I/O エラーは CLI 共通の `OSError` 経路で扱われます。

## 関連文書

- [CLI 索引](../../README.md) — `strata connect` のオプション文書一覧。
- [`strata launch` 概要](../launch/README.md) — 接続先となる Strata サーバーの起動と管理。
- [Terminal CLI 調査手順](../../001_investigation.md) — 文書配置規約と調査基準。

## 根拠

- `strata_cli/cli.py:492-494,2153-2155` — `launch_cmd.add_parsers` の登録と `connect` 実行の委譲。
- `strata_cli/launch/cmd.py:148-165` — `connect` parser、位置引数、オプション、既定出力形式。
- `strata_cli/launch/cmd.py:605-627,842-870` — launch/preset 情報、接続先・key・model・context の解決と harness 設定生成。
- `strata_cli/launch/cmd.py:871-896,897-947` — JSON/人間向け出力、key マスク、確認、接続チェック、書込分岐と終了コード。
- `strata_cli/cli.py:2176-2183` — 書込時を含む CLI 共通の `OSError` 処理。
- `strata_cli/launch/harness.py:209-243,253-267` — harness 名・別名・対応ファイル・環境・注意事項の登録、target と設定生成。
- `strata_cli/launch/harness.py:275-299` — バックアップ、JSON merge、書込後の権限設定。
- `strata_cli/launch/check.py:36-68,111-155` — HTTP POST、確認リクエスト形式、判定条件と通信失敗の説明。
- `strata_cli/launch/settings.py:47-57` — context サイズの変換と最小値検証。
