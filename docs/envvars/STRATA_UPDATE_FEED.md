# `STRATA_UPDATE_FEED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata update` が読む署名付き更新 feed の場所を指定します。feed はエンジン、Control、必要に応じてデスクトップアプリの更新候補と配布物の参照先を持ちます。`strata launch` では、エンジンが未導入または利用不能で、起動時にエンジンを導入する経路に入った場合にも参照されます。

## 値と判定

この変数自体の数値・真偽値への変換はありません。Python の `os.environ.get()` で文字列を取り、文字列が空でないかを判定します。

| 状態 | `strata update` / `strata components update` で使う feed |
|---|---|
| `--feed VALUE` が空でない | コマンドラインで指定した `VALUE` |
| `--feed` が空または未指定で、環境変数も空でない | `STRATA_UPDATE_FEED` の値 |
| 両方が空または未指定 | components 状態に記録された直近の feed。記録がなければ組み込みの GitHub Releases feed (`https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json`) |

空文字 (`STRATA_UPDATE_FEED=`) は設定済み feed として使われず、直近の feed または組み込み feed に進みます。空白だけの値は空文字ではないため feed の場所として渡されます。値の trim はせず、通常はその名前の場所を読めずエラーになります（同名のローカルパスが存在する場合はそのパスとして扱われます）。文字列の大小文字変換や URL 正規化も、この変数の選択段階では行いません。

feed の場所には HTTPS URL、loopback 宛て HTTP URL、`file://` URL、またはローカルのファイル/ディレクトリパスを指定できます。HTTP は loopback 以外では既定で拒否され、別変数 `STRATA_UPDATE_ALLOW_HTTP=1` の場合だけ許可されます。URL の末尾要素が `.json` で終わらない場合、およびローカルディレクトリを指定した場合は、その場所の下の `strata-feed.json` を読みます（拡張子の判定は大文字小文字を区別します）。署名ファイルも同じ場所から読みます。

## 有効になる条件

- `strata update` と `strata components update` は `_feed_source()` で値を選び、`strata_control.feed.fetch()` に渡します。`--check` も同じ feed を読みます。
- `strata launch` の `--feed` は引数が指定されると Runner に渡されます。エンジンが既に利用可能なら Runner は feed を読みません。エンジンが利用できない場合は update 子プロセスを起動し、`--feed`、または環境変数を使わせます。
- Host の明示的な更新確認・更新処理は、渡された `feed` がなければ Host プロセスの `STRATA_UPDATE_FEED` を `--feed` として Control CLI に渡します。空文字は `--feed` 引数にはなりません。
- feed 取得には署名検証が必要です。ソースは、信頼鍵がない場合や署名・feed の検証に失敗した場合に受理されません。`STRATA_UPDATE_FEED` を指定するだけで検証を迂回する経路はありません。
- `strata components rollback` も共通 parser に `--feed` を持ちますが、rollback 分岐は feed の選択・読込みより前に実行されるため、この変数も `--feed` も rollback の動作には使われません。

## 実行時の詳細

CLI は更新コマンドの実行ごとに環境変数を読みます。`--feed` が空でないときは環境変数より優先します。feed の読み込みに成功すると、feed の source と sequence が `<components>/.updates/state.json` に保存され、次回以降、非空の `--feed` と `STRATA_UPDATE_FEED` がどちらもなければ、その source が組み込み feed より優先されます。`--check` も成功した feed source を記録します。したがって、環境変数を外しただけでは、以前保存された source が選ばれる場合があります。新しい非空 `STRATA_UPDATE_FEED` または `--feed` を指定すればその保存値を上書きします。

feed の取得・更新は明示的な acquisition 経路です。`STRATA_NO_ACQUIRE` などにより acquisition が禁止されたプロセスでは更新を拒否します。更新確認・失敗は `strata update` の通常出力または `--output json/jsonl` の結果に現れます。feed 読込みエラーは「the update feed could not be read: ...」として報告され、CLI の更新経路では終了コード 6 になります。

## 根拠

- `strata_cli/update_cmd.py:23-31,87-95,156-205`: 既定 feed、共通 `--feed`、優先順位、`--check` を含む更新処理。
- `strata_cli/update_cmd.py:167-192`: rollback は `_feed_source()` より先に分岐し、通常更新では選択済み source を Context に設定。
- `strata_control/feed.py:322-340`: URL/パスから feed と署名を読み、ディレクトリや URL prefix の場合に `strata-feed.json` を補う。
- `strata_control/transfer.py:61-82,85-102`: source 種別、HTTP 許可条件、feed 内相対参照の基準。
- `strata_control/updater.py:127-165,308-316,529-545,1123-1145`: state ファイル、読み込んだ source の記録、check/update 後の保存。
- `strata_cli/launch/cmd.py:129-131,629-634,696-699` と `strata_cli/launch/runner.py:416-426,446-467`: launch の `--feed`、環境の継承、未導入エンジン時にだけ行う update 呼び出し。
- `apps/host/server/control-runtime.mjs:160-180`: Host の更新確認・更新呼び出しが環境変数由来の feed を `--feed` に渡す処理。
