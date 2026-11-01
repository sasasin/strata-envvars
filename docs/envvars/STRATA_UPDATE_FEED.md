# `STRATA_UPDATE_FEED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata Control の署名付き更新 feed の取得元を指定します。`strata update` / `strata components update` と、`strata launch` が必要と判断したエンジン取得・更新、および DeepSeek 4.1 用エンジンのセットアップで参照されます。feed はエンジンや Control などの更新情報を含む署名付きマニフェストです。インストーラーが読む別名 `STRATA_FEED` はこの変数とは別です（`packaging/UPDATES.md:186-191`）。

この変数はモデル推論の設定ではありません。更新処理を呼ばない通常の起動・配信では feed を読みません。ホストアプリも起動時ではなく、更新確認または更新操作から Control CLI を呼ぶ際に feed を引き渡します（`apps/host/server/control-runtime.mjs:179-195`）。

## 値と判定

環境変数の値自体を真偽値や数値に変換する処理はありません。`strata_cli.update_cmd._feed_source()` は、次の順に**空でない値**を選びます。

| 優先順位 | 値 | 判定と動作 |
|---|---|---|
| 1 | `--feed` | Python の真偽値判定で真ならその文字列をそのまま採用。空文字なら次へ進む。 |
| 2 | `STRATA_UPDATE_FEED` | `os.environ.get()` の結果が真ならその文字列をそのまま採用。未設定または空文字なら次へ進む。空白だけの文字列は真なので採用され、ここでは trim されない。 |
| 3 | 保存済み feed | 保存先の feed が `https://` で始まる場合だけ採用。過去の既定 URL はホストに応じた feed ファイル名へ補正する。HTTP、ローカル URL、フォルダーは次回用の選択肢として採用しない。 |
| 4 | プロジェクト既定値 | GitHub Releases の `strata-feed.json`。Linux ARM64 では同じ場所の `strata-feed-linux-aarch64.json`。 |

この優先順位は `strata_cli/update_cmd.py:23-34,97-113` にあります。`--feed` の定義は `strata_cli/update_cmd.py:37-40`、launch 側は `strata_cli/launch/cmd.py:142-147` と `strata_cli/launch/runner.py:617-638,734-748` です。したがって環境変数が空文字でも「空の feed を指定した」状態にはならず、保存済みまたは既定 feed へ進みます。値の長さや数値境界はありません。

選択後の feed source は URL / file URL / フォルダー・ファイルパスとして扱われます。サポート外の URL scheme、許可されない HTTP、読み出せない場所は feed 読み込みで失敗します。Strata は署名検証前提で処理し、信頼鍵がない場合も更新を拒否します（`strata_control/transfer.py:65-86`, `strata_control/feed.py:376-396`）。環境変数の読み取り段階では URL の妥当性検査や fallback はありません。

## 有効になる条件

- **更新 CLI**: `strata update` と `strata components update` が feed source を決める際に使います。`--feed` が空でない場合は CLI が優先します。`strata update --check` も feed を読みますが、更新取得はせず報告します（`strata_cli/update_cmd.py:49-63,229-245`）。
- **Terminal の `strata launch`**: `Runner` が未導入エンジンの取得または古いエンジンの更新を行うとき、まず `self.feed`、次に環境変数を参照し、選んだ値を `strata update --no-control` に渡します。すでに使える最新エンジンがある場合はその分岐で戻り、feed は読まれません（`strata_cli/launch/runner.py:720-748`）。DeepSeek 4.1 の専用エンジンについては、必要なパッケージがない場合の取得や、既存の自動管理パッケージの更新で `_feed_source()` を使います。ユーザー指定 `--dsv41-package` / `STRATA_DSV41_EXE`、build 中、管理対象外フォルダーなどでは自動更新しません。取得不能な自動更新は起動を止めず既存実行ファイルを返します（`strata_cli/launch/runner.py:2171-2190`; `setup.py:8173-8219,8615-8630`）。
- **`setup.py` の DeepSeek 4.1 セットアップ**: `--feed` がない場合に環境変数が使われます。ローカル feed（パス、file URL、loopback URL）かどうかを判定する際も `feed or os.environ.get(...)` を trim して使い、ローカルなら GitHub 到達性の事前確認を省きます（`setup.py:8137-8146,8620-8627`）。
- **CUDA 12 の driver floor 情報**: setup が feed 参照を要求し、取得禁止状態でない場合に `_feed_source()` を呼びます。その戻り値を含む算出結果は `_CUDA12_FLOORS` にキャッシュされます。同じ setup プロセスでキャッシュ済みの呼び出しは再評価されません（`setup.py:1714-1739,9484`）。
- **ホストアプリ**: `createControl()` が受け取る `env`（既定は `process.env`）から update/check 呼び出し時に値を取り、値が truthy なら `--feed` にします。空文字の場合は引数にせず、Control の Python 側で環境変数が空なら通常の fallback が適用されます。更新 CLI の子プロセスには `env` が渡されます（`apps/host/server/control-runtime.mjs:172-195,124-129`）。

OS や GPU backend による feed 値の parse 差はありません。Linux ARM64 の既定ファイル名だけが異なります。値が選ばれても、更新を実行する場所で acquisition が許可されている必要があります。ホストアプリは明示的な update/check 呼び出しで acquisition を許可し、他の Control 呼び出しでは `STRATA_NO_ACQUIRE=1` を維持します（`apps/host/server/control-runtime.mjs:179-195`; `apps/host/server/control-runtime.mjs:90-103`）。

## 実行時の詳細

`strata update` は実行時に `_feed_source()` を呼び、決定した source を updater context に設定します。updater は feed を読み、読み取り成功後に feed sequence、署名 key ID、source、channel、確認時刻を状態へ記録します（`strata_cli/update_cmd.py:97-106,229-245`; `strata_control/updater.py:360-373`）。`STRATA_UPDATE_FEED` 自体をモジュール定数や static 値として保存する処理はなく、CLI の source 選択時に `os.environ` を読みます。setup の CUDA driver floor だけは上記の通り算出結果をプロセス内 cache します。

`strata launch` では `--feed` または環境変数から得た値を子 CLI の引数に追加し、子プロセス環境も親環境から作ります。launch の初回エンジン取得で feed が読めない場合、JSONL のエラー内容から `LaunchError` を作り、利用者に「Check your internet connection, or point Strata at an update source with --feed, then try again.」を案内します（`strata_cli/launch/runner.py:674-684,734-748,790-802`）。

読み取りエラーは `FeedError` に変換され、通常出力では stderr に `strata: <message>`、JSON/JSONL 出力ではエラー JSON と終了コードが返ります。feed が読めない場合の文言は `the update feed could not be read: ...` です。信頼鍵がない場合は `this build trusts no update key ...` で拒否します（`strata_control/feed.py:376-396`; `strata_cli/update_cmd.py:187-192,257-264`）。ホストアプリの更新確認はエラーを画面向けの状態に変換し、更新時は Control の JSON/イベントを通じて失敗を返します（`apps/host/server/control-runtime.mjs:183-195`; `apps/host/server/updates.mjs:52-60`; `apps/host/server/engine-step.mjs:62-65`）。

## 根拠

- 全候補名の検索で、本番コードの環境読み取りは `strata_cli/update_cmd.py:26,97-106`、`strata_cli/launch/runner.py:734`、`setup.py:8140`、ホスト側の `apps/host/server/control-runtime.mjs:183,188`。setup と runner の他の呼び出し先も追跡しました。
- コメント、ヘルプ、文書中の名前だけの参照（例: `setup.py:8128,8139,8175,8206,9142-9144`、`docs/TERMINAL_LAUNCH.md:111`、`packaging/UPDATES.md:190`）は、それ自体を読み取り実装の根拠にはしていません。
- `apps/host/tests/component-updates.test.mjs` と `tools/test_setup_dsv41.py` にも文字列がありますが、テストコードは実動作の根拠に含めていません。
