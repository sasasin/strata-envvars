# `OPENAI_API_KEY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の推論エンジンやサーバーが `OPENAI_API_KEY` という固定名を直接参照する実装は確認できない。一方、CLI は `--key-env OPENAI_API_KEY` または `--api-key-env OPENAI_API_KEY` のように環境変数名を引数で指定すると、その値を実行時に読み取る。また `strata connect hermes` は、接続先用のキーを Hermes 向けの環境設定 `OPENAI_API_KEY=<key>` として生成し、端末表示または JSON に出力する。ここで扱うのは Strata CLI のキー取得と設定出力であり、Hermes やサーバー側がキーをどう使うかではない。`terminal/strata_cli/launch/cmd.py:137-138,163-174,1074-1080`、`terminal/strata_cli/launch/harness.py:286-309,343-348`

## 値と判定

値は文字列のまま扱われ、`OPENAI_API_KEY` 固有の形式検査、数値変換、長さ制限はない。固定名が環境から検索されるのではなく、CLI 引数の環境変数名が `OPENAI_API_KEY` のときにだけ参照対象となる。

| 読み取り経路 | unset | 空文字 | その他の値 |
|---|---|---|---|
| `strata launch --api-key-env OPENAI_API_KEY` | `os.environ.get()` が `None`。空文字と同様にエラー | エラー | 文字列を API キーとして採用。空白だけの値も truthy なので受け付ける |
| `strata connect <app> --key-env OPENAI_API_KEY` | 環境値を使わず次の候補へ進む | 同左 | 文字列をキー候補にする。空白だけの値は truthy なので採用 |

launch 経路は `if not val` で未設定と空文字を同じ扱いにし、`The environment variable OPENAI_API_KEY is empty or not set.` を出して終了コード 2 で失敗する。空白文字列はこの判定を通る。connect 経路は `or` による選択なので、未設定・空文字のときだけ後順位のキーへ進み、無効値としてのエラーや形式検査はない。`terminal/strata_cli/launch/cmd.py:288-300,703-725,1074-1079,1009-1012`

## 有効になる条件

- 環境値を launch のサーバーキーにするには `strata launch --api-key-env OPENAI_API_KEY` を指定する必要がある。環境値が空または未設定だと起動処理は終了コード 2 で失敗する。`--api-key` と併用した場合、`--api-key-env` の値が `s.api_key` に後から代入されるため優先する。`--no-api-key` も併用すると、キー指定がある旨の警告を出し、キーを保持する。`terminal/strata_cli/launch/cmd.py:137-140,288-300`
- connect の出力に環境値を使うには `strata connect hermes --key-env OPENAI_API_KEY` のように `--key-env` を指定する。`--key` が非空ならそれが優先し、次に `--key-env` の非空値、次に起動中サーバーまたは指定 preset のキー、それらがなければ空文字が候補となる。`terminal/strata_cli/launch/cmd.py:169-174,703-725,1074-1079`
- Hermes 用の `OPENAI_API_KEY` 行を出すのは `hermes` / `hermes-agent` を選んだ場合である。`strata connect` の別アプリ設定がこの名前を生成するわけではない。値候補が空なら `target()` が `strata-local` に置き換えるため、Hermes の環境設定にもそのプレースホルダーが出る。`terminal/strata_cli/launch/harness.py:21,307-309,318-323,339-347`
- OS、GPU backend、build macro、サーバーモードによる `OPENAI_API_KEY` 固有の分岐はない。読み取りは CLI 引数に指定した名前を使うため、固定名を直接探す挙動はない。`terminal/strata_cli/launch/cmd.py:288-294,1074-1079`

## 実行時の詳細

両 CLI 経路ともコマンド実行時に環境を一度参照し、その後の変更を監視・再読込する cache はない。launch 側では環境値を `s.api_key` に設定する。connect 側では得たキーを `Target` に渡し、Hermes の `Harness.env` がその文字列を `OPENAI_API_KEY` の値にする。`render()` はファイル内容と環境マップを返すだけで、`--write` が書き込む対象は `out["files"]` の設定ファイルのみであり、環境変数をプロセス環境やファイルへ設定する処理ではない。`terminal/strata_cli/launch/cmd.py:288-300,1074-1080,1019-1050,1156-1161`、`terminal/strata_cli/launch/harness.py:205-208,307-309,339-348`

通常出力では環境設定行は `Environment:` 以下に表示され、キーは既定で `mask()` により一部置換される。キーが設定されていて出力中に含まれる場合は `The key is hidden here; add --show-key to print it.` と案内する。JSON 出力では `env` の値も `mask()` を通して返す。組み込みモニターの Connect 画面でも環境行を表示・コピーできるが、画面表示は既定でマスクされ、コピー操作は `KEY=value` の行を組み立てる。`terminal/strata_cli/launch/cmd.py:1081-1086,1120-1136`、`terminal/strata_cli/launch/harness.py:432-433`、`terminal/strata_cli/launch/monitor_ext.py:240-255,410-430`

## ログと測定値

測定値は該当しない。キー取得の失敗は launch のエラー文 `The environment variable {NAME} is empty or not set.`（ここでは `NAME` が `OPENAI_API_KEY`）として報告され、終了コード 2 になる。connect は `--key-env` の値が空でもそれ自体では警告せず、後順位のキーまたは `strata-local` を使う。生成したキー行は前節のとおり既定でマスクされる。`terminal/strata_cli/launch/cmd.py:288-294,1009-1012,1074-1079,1131-1136`、`terminal/strata_cli/launch/harness.py:21,339-347,432-433`

## 根拠

- `terminal/strata_cli/launch/cmd.py:137-140,163-178` — launch/connect の CLI 引数。
- `terminal/strata_cli/launch/cmd.py:288-300,1009-1012` — launch 側の動的環境変数読み取り、判定、エラー終了。
- `terminal/strata_cli/launch/cmd.py:703-725,1074-1080` — 起動情報と connect のキー選択順。
- `terminal/strata_cli/launch/cmd.py:1081-1086,1120-1136` — JSON・端末出力とキーのマスク。
- `terminal/strata_cli/launch/harness.py:21,286-315,318-348,432-433` — Hermes の環境マップ、キーの fallback と表示用マスク。
- `terminal/strata_cli/launch/monitor_ext.py:240-255,410-430` — モニターの設定表示とコピー。
