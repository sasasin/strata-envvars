+# `OPENAI_API_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の推論 engine が OpenAI の API キーとして自動取得する環境変数ではありません。Strata CLI は、環境変数名を CLI 引数で指定した場合に限り値を読みます。また `strata connect hermes` は、接続先 Strata サーバーのキーを Hermes Agent 起動用の `OPENAI_API_KEY` として表示します。

## 値と判定

| 読み取り経路 | 未設定・空文字 | 設定時の扱い |
|---|---|---|
| `strata launch --api-key-env OPENAI_API_KEY` | 未設定または空文字ならエラー。空白だけの文字列は取得時には通るが、後続の API キー検証で無効 | 値を launch 設定の API キーにする。カンマ区切りはサーバー側で複数キーとして解釈し、各キー前後の空白を除く |
| `strata connect <app> --key-env OPENAI_API_KEY` | 未設定・空文字なら実行中 launch のキーへ進み、なければ `strata-local` | `--key` が空でなければそれを優先し、そうでなければこの環境値を使う |
| Hermes 用の環境表示 | 選択したサーバーキーがなければ `strata-local` | `strata connect hermes` の出力に `OPENAI_API_KEY=<接続先キー>` を含める |

数値変換や `1` 判定はありません。launch 経路では `--api-key-env` の値が明示的な `--api-key` より後に適用されるため、両方を指定すると環境変数側が上書きします。さらに `--no-api-key` も指定するとキー指定は保持され、stderr に警告が出ます。

## 有効になる条件

- `strata launch` は `--api-key-env OPENAI_API_KEY` を明示した場合にこの名前を検索し、値を launch の `api_key` 設定に入れます。サーバー起動時には別環境変数 `STRATA_API_KEY` がこの設定値より優先されます。
- `strata connect` は `--key-env OPENAI_API_KEY` を指定した場合に検索します。`--key`、環境値、実行中 launch のキー、`strata-local` の順で選びます。これはクライアント設定を作る CLI の処理です。
- Hermes 用の表示は harness 定義にあります。`--write` が書くのは設定ファイルで、環境行を環境や shell profile に設定しません。

## 実行時の詳細

Python の `os.environ.get()` で CLI 処理中に読みます。`--api-key-env` の未設定・空文字は `ValueError` となり、CLI は `strata: The environment variable OPENAI_API_KEY is empty or not set.` を stderr に出し、通常のエラーコード 2 で終了します。空白だけの値は取得時に受け入れられますが、サーバー側の `api_key_of()` が空白を除去した結果が空なら無効です。launch 時の検証に失敗すると `ProfileError("the inference API key is invalid", 5)` になります。値にカンマがあれば複数の許可キーとして扱われます。

`strata connect` では `--key-env` の値が空なら launch キーへフォールバックし、それもなければ `Target` が `strata-local` を使います。人向け出力では通常キーをマスクし、`--show-key` で実値を表示します。Hermes 用の `env` 辞書は同じ `Target.key` から作られます。

読み取りは CLI コマンドごとで、static cache はありません。環境変数名は CLI 引数から渡されるため、利用者が `OPENAI_API_KEY` と指定した場合に読み取り対象になります。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:474`。
- launch の引数、値設定、空値拒否、優先順位、`--no-api-key` 警告: `strata_cli/launch/cmd.py:130-133,270-283`。
- CLI のエラー表示・終了コード: `strata_cli/cli.py:2166-2173,528-532`。
- launch 設定への反映: `strata_cli/launch/runner.py:524-536`。
- 実行時の `STRATA_API_KEY` 優先と API キー検証: `strata_cli/cli.py:782-795`。
- 空値、空白除去、カンマ区切りの扱い: `serve/server.py:8358-8399`。
- connect の引数とキー優先順位: `strata_cli/launch/cmd.py:161-172,945-950`。
- `Target` のプレースホルダー: `strata_cli/launch/harness.py:22,28-44,272-273`。
- Hermes harness の環境値と render: `strata_cli/launch/harness.py:240-242,276-281`。
- 人向け出力のマスク、`--show-key`、`--write`: `strata_cli/launch/cmd.py:951-957,978-992,1011-1028`。
