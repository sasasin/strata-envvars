# `--feed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | `URL|DIR`。署名付き更新フィードの URL またはローカルのディレクトリ／ファイルを指定 |

## 役割

`strata launch` が起動に必要な推論エンジンを取得するときに参照する更新フィードを指定します。通常の起動で、使用可能なエンジンが既にあり更新も不要なら、この値はそのエンジン確認経路では使われません。エンジンが未導入または古い場合、launch は `strata update --no-control --output jsonl` を子プロセスとして実行し、指定されたフィードを渡します。対話画面での起動にも同じ値が引き継がれます。（`strata_cli/launch/cmd.py:139,706-716,780-783`; `strata_cli/launch/runner.py:546-568`; `strata_cli/launch/app.py:438-455`）

## 使い方

```sh
strata launch --model iq3_xxs --feed https://updates.example.invalid/strata-feed.json --no-tui
```

`--feed` 自体はフィードを取得しません。上の例では launch がエンジンの確認・取得を必要とした場合に使われます。HTTPS URL、ローカルの feed ファイル／ディレクトリを渡せます。URL が `.json` で終わらない場合は末尾に `/strata-feed.json` を付け、ローカルのディレクトリにも `strata-feed.json` を加えて読みます。フィード本体と隣接する `.sig` ファイルが必要です。（`strata_control/feed.py:342-360`）

## 値と既定値

parser は `--feed` に `URL|DIR` という metavar を表示しますが、型変換や値検証は行わず、文字列を `None` 既定で受け取ります。同じオプションを複数回指定した場合、argparse の通常の `store` 動作により最後の値が残ります。（`strata_cli/launch/cmd.py:139`）

launch が指定値を受け取った場合、runner はエンジン更新コマンドにその値を `--feed` として転送します。明示値がない場合のフィード選択は、update 側で `STRATA_UPDATE_FEED`、端末に記録された前回の feed source、プロジェクト既定 URL `https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json` の順です。空文字列は parser では受理されますが、launch と update のどちらも真偽値で判定するため明示指定として扱わず、この既定選択に進みます。（`strata_cli/launch/runner.py:561-569`; `strata_cli/update_cmd.py:23-26,87-95`）

受理される場所は HTTPS、loopback の HTTP、`file:` URL、またはファイル／ディレクトリのパスです。通常の HTTP は loopback 宛てか `STRATA_ALLOW_HTTP=1` の場合に限り許可されます。URL scheme が未対応の場合や URL policy に反する場合は転送層が拒否します。（`strata_control/transfer.py:65-86`; `strata_control/feed.py:342-360`）

## 実行時の動作

通常エンジン経路では、利用可能な engine が見つかり、古い engine 判定にも該当しなければ `ensure_engine()` はそこで終了し、feed は参照しません。必要な場合は feed を明示した更新子プロセスを起動します。更新結果は JSONL で読み取られ、進捗・警告が launch のイベントに反映されます。（`strata_cli/launch/runner.py:546-568,575-595`）

DeepSeek 用の専用 engine には別の更新経路があります。明示的な `STRATA_DSV41_EXE` または `--dsv41-package` の指定がなく、検出された実行ファイルが `engine-dsv41` 配下にある場合、feed を選び、source が到達可能なら更新を試みます。例外や到達不能は launch を止めず、既存 engine を使います。（`strata_cli/launch/runner.py:1896-1915`）

feed の取得後、Strata は信頼鍵で署名を検証し、JSON/schema、channel、有効期限、端末に記録された sequence より古くないことを確認します。これらは `--feed` 値自体の検証ではなく、読み込んだ feed の検証です。（`strata_control/feed.py:312-339`; `strata_control/updater.py:355-366`）

## 適用条件と副作用

このオプションは起動設定や preset に保存されず、launch の runner に渡される feed source です。エンジン取得が必要ならネットワークまたはローカル feed を読み、更新処理が選択した engine package をダウンロード・検証・導入することがあります。feed の URL／パスは信頼鍵による署名検証を迂回しません。（`strata_cli/launch/cmd.py:715`; `strata_cli/launch/runner.py:561-575`; `strata_control/feed.py:312-360`）

`--plan` は計画表示後に終了する分岐であり、`runner.run()` に進まないため、このエンジン取得経路を実行しません。（`strata_cli/launch/cmd.py:733-760,784-787`）

## 出力とエラー

エンジン取得を行ったとき更新処理が非 0 で終わると、launch は `LaunchError`（code 6）を返し、「The engine could not be installed.」と、可能なら子プロセスの最後のエラー内容を含めます。通常出力では `strata: ...` を stderr に出し、`--output json` ではエラー code と message を含む JSON を stdout に出します。指定フィードを読めない場合、更新側の feed 転送エラーは code 6 として launch に伝わります。（`strata_cli/launch/runner.py:617-629`; `strata_cli/launch/cmd.py:630-641,784-787`; `strata_control/feed.py:355-358`; `strata_cli/update_cmd.py:225-230`）

署名が信頼されない、feed が壊れている、channel／期限／sequence 条件を満たさない場合も feed 検証で拒否されます。エラー文言や終了 code は失敗の種類に依存します。（`strata_control/feed.py:312-339`; `strata_cli/update_cmd.py:225-230`）

## 根拠

- `strata_cli/launch/cmd.py:139` — `--feed` parser 定義と help 表示。
- `strata_cli/launch/cmd.py:706-716,780-787` — 対話式／通常 launch への feed 引き渡し、計画分岐、失敗表示。
- `strata_cli/launch/runner.py:546-568,575-629` — engine 状態に応じた update 子プロセスへの転送と失敗処理。
- `strata_cli/update_cmd.py:23-31,87-95,197-230` — feed の既定値、優先順位、update 側の選択とエラー処理。
- `strata_control/feed.py:312-360` — 署名・feed 条件の検証、feed と署名ファイルの取得。
- `strata_control/transfer.py:65-86,159-187` — source 種別、HTTP policy、feed ファイル読み込み。
- `strata_cli/launch/runner.py:1896-1915` — DeepSeek 専用 engine の条件付き更新。
