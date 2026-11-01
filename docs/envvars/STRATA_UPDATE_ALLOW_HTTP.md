# `STRATA_UPDATE_ALLOW_HTTP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の共通転送処理が HTTP URL を許可する条件を広げます。通常は HTTPS とループバック宛ての HTTP だけを許可しますが、この変数が文字列として厳密に 1 なら、ループバック以外の HTTP も許可します。対象は strata update / strata components update のフィード・署名・コンポーネント取得と、共通転送 helper を使う DFlash2 drafter の取得です。HTTP を許可しても、フィードの署名検証やダウンロード内容のハッシュ検証を無効にはしません（strata_control/feed.py:391-396, strata_control/updater.py:492-500, strata_control/drafting_fetch.py:72-82）。

## 値と判定

`check_url_policy()` は `os.environ.get(ENV_ALLOW_HTTP) == "1"` を比較します。trim、数値変換、大文字小文字変換はありません。`check_url_policy()` と `resolve_ref()` の `environ` 引数を省略した製品コード経路では現在の `os.environ` を参照します（`strata_control/transfer.py:77-86,108-119`）。

| URL | unset / 空文字 / 0 / true / その他 | 値が厳密に 1 |
|---|---|---|
| https:// | 許可 | 許可（この変数の判定は不要） |
| ループバック宛て http:// | 許可 | 許可 |
| ループバック以外の http:// | 拒否 | 許可 |
| ftp など未対応の URL scheme | 拒否 | 拒否 |

HTTP の例外判定は hostname が `localhost` か、`ipaddress.ip_address(host).is_loopback` が真になる IP literal かで行います。名前解決してループバックかどうかは調べません（`strata_control/transfer.py:56-63,82-86`）。未設定、空文字、前後に空白がある `1`、`true` はすべて非ループバック HTTP を許可しません。`file://` とローカルパスは HTTP policy check の対象外です。

## 有効になる条件

- OS、GPU backend、build macro、サーバーモードによる分岐はありません。この判定は Python の strata_control.transfer にあります。
- URL 自体が HTTP で、宛先がループバックと認識されない場合にだけ値 1 が必要です。HTTPS やローカルファイル・パスの取得には影響しません。
- strata update の --feed、STRATA_UPDATE_FEED、記憶された feed source は取得先を選びますが、この変数は取得先を選択せず、URL scheme の許可だけを変えます（strata_cli/update_cmd.py:97-106,229-245）。
- HTTP の feed が相対参照した asset も、HTTP の取得先として最終的に同じ policy check を通ります。HTTP(S) redirect の遷移先も同じ check の対象です（strata_control/feed.py:166-168, strata_control/transfer.py:108-134,176-178,242-252）。
- DFlash2 は、明示的な strata drafting fetch のほか、launch が DFlash2 を使う判断で pack がまだ無い場合に取得を試みます。失敗すると launch は警告を出し、MTP で起動を続けます（strata_control/drafting_fetch.py:54-83, strata_cli/launch/runner.py:1415-1436）。

## 実行時の詳細

値は module 定数へ cache されません。環境変数名だけが ENV_ALLOW_HTTP に定数化され、各 URL policy check が environ.get() を呼びます。feed の取得、feed 内 asset の URL 解決・取得、redirect の各 check で値を読み直すため、各 check 時点の環境が使われます（strata_control/transfer.py:34,77-86,108-119,131-134,176-178,242-252）。通常のプロセス内変更を含むキャッシュや起動時固定化はありません。

非ループバック HTTP が許可されない場合、policy check は TransferError に「is plain http; updates are fetched over https (a loopback address is the only exception)」というメッセージを設定します。feed または署名取得中なら feed.fetch() が FeedError（exit code 6）にし、strata update CLI は通常出力では stderr に strata: <message>、JSON 出力では error object を出します（strata_control/feed.py:391-396, strata_cli/update_cmd.py:187-192,257-260）。コンポーネント download 中なら updater が UpdateError（exit code 6）に変換します（strata_control/updater.py:492-500）。DFlash2 の明示 fetch は DraftingError になり、CLI は失敗メッセージを stderr に出して 5 を返します。launch 中は warning notice を出し MTP に fallback します（strata_control/drafting_fetch.py:81-82, strata_cli/drafting_cmd.py:87-94, strata_cli/launch/runner.py:1432-1436）。許可された場合、この変数自体についての警告ログはありません。

## 根拠

- strata_control/transfer.py:34,56-86: 候補名の定義、loopback 判定、HTTP URL policy、および値の厳密比較。
- strata_control/transfer.py:108-138,168-205,242-279: feed 参照と redirect の policy check、small fetch と大容量 download の拒否・例外経路。
- strata_control/feed.py:166-168,376-396: フィード参照 URL の解決、フィードと署名取得、転送失敗の変換。
- strata_control/updater.py:492-500, strata_cli/update_cmd.py:183-260: 更新 asset download と CLI の失敗表示・終了コード。
- strata_control/drafting_fetch.py:54-83, strata_cli/drafting_cmd.py:57-98, strata_cli/launch/runner.py:1415-1436: 共通転送 helper を使う drafter fetch、明示 fetch と launch 時 fallback。
