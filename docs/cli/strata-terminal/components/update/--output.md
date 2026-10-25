# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

対象コマンド: `strata components update`。このオプションは同じ共通 parser 定義により `strata update` と `strata components rollback` にも登録されています。索引上の本書の scope は `components/update` です。

## 用途と利用例

進捗・結果の出力形式を選びます。

```sh
strata components update --check --output json
strata components update --output jsonl
```

## 値と既定値

| 値 | 動作 |
| --- | --- |
| `human` | 既定値。進捗や結果を人向けのテキストで表示します。 |
| `json` | 進捗イベントを表示せず、処理結果を JSON オブジェクトで出力します。 |
| `jsonl` | 進捗イベントを JSON Lines で逐次出力し、最後に処理結果の JSON オブジェクトを出力します。 |

parser は `choices=("human", "json", "jsonl")`、`default="human"` としており、別名はありません（`strata_cli/update_cmd.py:30-40`）。これ以外の値は `argparse` により引数エラーとなります。コマンドの parser を登録する際、`components update` は `_common()` を呼び、同じ `run()` に接続されます（`strata_cli/update_cmd.py:42-59`、`strata_cli/cli.py:139-140,2136-2137`）。

## 出力と効果

- `human` では進捗イベントを標準出力に表示します。TTY では同じ行を更新し、非 TTY では前回から10ポイント以上進んだ時または100%時に表示します。download 以外の phase と waiting も表示します（`strata_cli/update_cmd.py:62-84`）。処理終了後は更新結果のテキストを標準出力に出します（`strata_cli/update_cmd.py:210-224`）。
- `json` は進捗イベントを破棄し、終了後に `schema_version: 1` と `ok` を含む JSON オブジェクトを標準出力へ出します。`--check` 成功時は check report が、通常更新成功時は update result が格納されます（`strata_cli/update_cmd.py:62-71,203-209,213-224`）。
- `jsonl` は各イベントを `schema_version: 1` 付きの JSON オブジェクトとして1行ずつ標準出力へ flush し、最後に最終結果の JSON オブジェクトを出します。進捗イベントの出力は `_emit_factory()` 経由です（`strata_cli/update_cmd.py:62-71,182-183,213-216`）。
- `json` / `jsonl` では `machine` が真となり、捕捉された更新・feed・署名・acquisition エラーを `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` 形式で標準出力へ出します。`human` では `strata: ...` を標準エラーへ出します。エラーコードは例外ごとに設定され、`KeyboardInterrupt` は130です（`strata_cli/update_cmd.py:163-172,225-234`）。通常の実行コードの対応は同ファイル冒頭に記載されています（`strata_cli/update_cmd.py:9-11`）。

## 相互作用・適用条件

出力形式はフィード取得、署名検証、更新対象の選択そのものを切り替えません。`run()` は各形式で同じ `updater.check()` または `updater.run_update()` を呼び、形式に応じてイベントと結果の表示を分岐します（`strata_cli/update_cmd.py:197-224`）。`--check` と併用した場合は更新を実行せず check report を出す経路です（同 `:203-209`）。

サーバー稼働中の待機確認は出力形式に影響されます。`--wait` 未指定で稼働中の場合、JSON/JSONL または非対話 stdin では質問せず、その後の更新処理に判定を委ねます。人向け出力かつ TTY の場合だけ待機確認を表示します（`strata_cli/update_cmd.py:237-252`）。

## 副作用と制約

このオプション自体は出力先ファイルを指定せず、コード上でファイルへの出力も行いません。選択するのは標準出力・標準エラーに使う形式です。更新操作自体はダウンロードやインストールを行うため、`--output` は副作用を抑止しません。変更を行わず状況を確認する場合は `--check` を併用してください（`strata_cli/update_cmd.py:4-6,203-224`）。

JSON/JSONL の stdout は機械可読形式ですが、署名鍵の追加利用に関する test setup の注記は stderr に出る経路があります（`strata_cli/update_cmd.py:197-202`）。そのため stdout 以外も含めた全出力が JSON になるとは限りません。

## 調査範囲

指定 revision の parser・出力処理・コマンド dispatch を確認しました。実行時に安全な CLI help は起動しておらず、配布済み Release artifact との照合もしていません。本書は上記 commit のソース挙動に基づきます。
