# `STRATA_UPDATE_FEED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

署名付き update feed の場所を、環境から読む経路の既定値として指定する。主な利用先は `strata update` と `strata launch` が必要時に取得する engine / Control、および feed から tuned drafter を探す処理である。feed の取得元を選ぶだけで、feed に含まれる engine の選択条件や署名検証を変更しない。`update_cmd._feed_source` は CLI の `--feed` が truthy ならそちらを先に採り、そうでなければこの変数、記憶済み feed、プロジェクトの release feed の順に選ぶ（`terminal/strata_cli/update_cmd.py:142-151`）。drafter 検索の `drafting_fetch._feed_source` は明示引数、環境変数、プロジェクト既定 feed の順で、remembered feed は参照しない（`terminal/strata_control/drafting_fetch.py:207-212`）。

## 値と判定

値は文字列として読み、値自体を trim・parse・大文字小文字変換しない。`os.environ.get(ENV_FEED)` の truth 判定なので、未設定と空文字は指定なしとして扱い、空白だけの文字列を含む非空文字列はそのまま feed source に渡す。`--feed` も同様に truthy 判定される（`terminal/strata_cli/update_cmd.py:142-151`）。

| 条件 | unset | 有効になる値 | 無効・指定なしになる値 |
|---|---|---|---|
| `strata update` / setup の共通選択 | 記憶済みの許可対象 feed、なければプロジェクトの既定 feed | 空でない任意の文字列。URL、file URL、ファイルまたはフォルダーのパスを feed 読み取り処理が扱う | 空文字は指定なし。値の構文検査は変数選択時にはしないため、不正な非空文字列も選択され、feed 読み取りで失敗する |
| `strata launch` の通常 engine 更新 | `--feed` もなければ上と同じ | 空でない任意の文字列 | 空文字は指定なし。既に使用可能で stale でない engine があれば feed の確認自体を行わない |
| tuned drafter の feed 検索 | プロジェクトの既定 feed | 空でない任意の文字列。明示的な `feed` 引数がある場合はそちらが優先 | 空文字は指定なし。`url` または `STRATA_DFLASH2_TUNED_URL` の直接ファイル指定がある場合は feed を使わない |
| Desktop app の更新 check/update | `env` の値が `null` / `undefined` なら Python 側の選択規則 | `createControl` に渡された `env.STRATA_UPDATE_FEED`。非空なら `--feed` として渡す | 空文字は Node 側で `--feed` 引数にならず、Python 側で空文字も指定なしとして扱う |

`strata update` での優先順位は、truthy な CLI `--feed` > truthy な `STRATA_UPDATE_FEED` > state に記憶された HTTPS feed > `DEFAULT_FEED`。記憶値が旧 `DEFAULT_FEED` と同じ場合は、Linux ARM64 向け feed 名へ組み替える。HTTPS 以外の feed は次回用に記憶値として採用されない（`terminal/strata_cli/update_cmd.py:142-159`）。環境変数が不正でも remembered/default へ fallback せず、feed の読み取りエラーとなる。

feed 読み取り処理は URL、file URL、ファイルまたはフォルダーのパスを受け、フォルダーや JSON 以外の URL にはホスト OS に応じた feed ファイル名を付ける。Linux ARM64 は `strata-feed-linux-aarch64.json`、それ以外は `strata-feed.json`（`terminal/strata_control/feed.py:680-705`）。この後に feed 本体と署名を読み、信頼鍵で検証する（`terminal/strata_control/feed.py:691-717`）。

## 有効になる条件

- `strata update` / `strata components update` は feed を読む通常の更新・check 経路で参照する。`--check` も feed を読む。rollback、installed engine の一覧・切替・削除、および `install-file` は `_feed_source` を通らない（`terminal/strata_cli/update_cmd.py:59-99, 341-358`）。
- 更新は取得を許可する実行経路でなければならない。`STRATA_NO_ACQUIRE` などにより acquisition が拒否されると feed 読み取り前に止まり、CLI はエラーを出して終了コード 5 を返す（`terminal/strata_cli/update_cmd.py:355-388`; `terminal/strata_control/updater.py:451-457`）。
- feed の署名検証に使える信頼鍵が必要。鍵がなければ `this build trusts no update key ... so no update can be verified; nothing was downloaded` で失敗する（`terminal/strata_control/feed.py:691-696`）。
- `strata launch` の通常 engine 経路では、engine が既に使用可能で stale でなければ feed を読まずに戻る。engine がない、または stale の場合は `strata update --no-control` を子プロセスとして呼ぶ。`--feed` または変数の値を引数へ渡し、なければ update 側の remembered/default 規則に任せる（`terminal/strata_cli/launch/runner.py:1077-1113`）。Qwen4 の shape 固有 engine 経路も `update_cmd._feed_source` を使う（`terminal/strata_cli/launch/runner.py:1231-1248`）。
- tuned drafter 検索では `drafting_fetch._feed_source` がその場で環境を読み、`tuned_from_feed` / `tuned_offered` が feed を読む。`ensure_tuned` で直接 `url` 引数または `STRATA_DFLASH2_TUNED_URL` がある場合はその直接指定を使い、feed とこの変数は使わない（`terminal/strata_control/drafting_fetch.py:207-212,229-271,294-320`）。
- 環境変数の判定に OS / GPU backend / build macro の分岐はない。OS は環境変数を選ぶ条件ではなく、既定 feed 名を決めるときだけ Linux ARM64 が特別扱いされる（`terminal/strata_control/feed.py:680-688`）。

## 実行時の詳細

Python の共通選択 helper は呼び出しごとに CLI 値と現在の `os.environ` を参照し、変数値の独自 cache はない。`strata update` は選ばれた source を `Context.source` に設定し、更新器が feed を読むと `sequence`、`key_id`、`source`、channel、確認時刻を component state に記録する（`terminal/strata_cli/update_cmd.py:307-358`; `terminal/strata_control/updater.py:451-470`）。次回起動で参照される remembered source は HTTPS のものに限られる（`terminal/strata_cli/update_cmd.py:148-159`）。

setup も update helper を利用しており、CUDA 12 の driver floor 参照、shape engine の取得、feed による model setup で同じ CLI / 環境 / remembered / default 選択を使う（`terminal/setup.py:2120,9500,9685`）。一方、drafter の `drafting_fetch._feed_source` は各呼び出し時に `os.environ.get(...) or default_feed()` を評価する。`tuned_offered` は計画表示にも feed 状態を照会し、`ensure_tuned` は feed からファイルを見つけたときだけ取得へ進む（`terminal/strata_control/drafting_fetch.py:207-212,260-271,294-320`）。

Control runtime は `createControl` に渡された `env` オブジェクトから update check/update の呼び出し時に feed 値を読み、空でなければ `--feed` を CLI に追加する。既定の `env` は `process.env` なので、明示的な `env` を渡さない場合は Node プロセス環境から呼び出し時に参照する。値は feed source の指定であり、engine 子プロセスの GPU 実行設定として転送されるものではない（`app/host/server/control-runtime.mjs:213,236,269-300`）。

feed の読み取り時に接続不能は `FeedUnreachable`（exit code 6）、その他の転送失敗は `FeedError`（通常 exit code 6）になり、CLI は人向け出力で `strata: <message>` を stderr に出す。JSON / JSONL 出力ではエラーオブジェクトとして返す。feed が過去に受理した sequence より古い場合は replay 拒否になる。成功時は人向け更新出力に feed sequence と署名 key ID を表示する（`terminal/strata_control/feed.py:706-716`; `terminal/strata_control/updater.py:451-470`; `terminal/strata_cli/update_cmd.py:311-316,378-394`）。

通常 launch の engine 取得に失敗した場合は runner が engine 状態を確認し、更新子プロセスからのエラーを engine 段階の通知として表示する処理がある。feed 変数だけで結果を保証するものではなく、source の到達性、署名、sequence、hardware に適合する package の有無など更新処理側の条件に従う（`terminal/strata_cli/launch/runner.py:1083-1118`; `terminal/strata_control/updater.py:451-470,761-780`）。

## ログと測定値

feed 選択時には人向け `strata update` が `Strata update (<source>)` を表示し、feed 読み取り時に `Reading the signed update feed` を出す。失敗時は `strata: <message>` と終了コード、または JSON の `error` が観測できる。launch は engine 段階の進捗・警告として表示する。性能測定値は該当しない（`terminal/strata_cli/update_cmd.py:358-377`; `terminal/strata_control/updater.py:451-457`）。

`docs/DETAILS.md` にこの変数固有の説明や測定値は見つからなかった。更新 feed の署名検証とダウンロードを行うという一般説明は `docs/SAFETY.md:47` と一致するが、変数値の優先順位・空文字処理は上記ソースコードに基づく。

## 根拠

- `terminal/strata_cli/update_cmd.py:33-49,142-159,307-388` — 既定値、CLI / 環境 / remembered の優先順位、更新経路とエラー処理。
- `terminal/strata_control/feed.py:680-717` — feed ファイル名、source 形式、feed と署名の読取り。
- `terminal/strata_control/updater.py:451-470` — 署名付き feed の取得、state への記録。
- `terminal/strata_control/drafting_fetch.py:207-212,229-271,294-320` — tuned drafter 用 feed 選択と直接 URL による迂回。
- `terminal/strata_cli/launch/runner.py:1077-1118,1231-1248` — launch における条件と子 CLI への feed 引き渡し。
- `app/host/server/control-runtime.mjs:213-236,265-300` — app の update check/update における `env` 読取りと `--feed` 引き渡し。
