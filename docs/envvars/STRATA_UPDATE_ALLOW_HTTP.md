# `STRATA_UPDATE_ALLOW_HTTP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata のネットワーク取得処理で、通常は拒否する loopback 以外の `http://` URL を許可するスイッチ。`terminal/strata_control/transfer.py` の `check_url_policy()` が URL の scheme を確認し、HTTP の場合に loopback 判定または本変数の値を調べる。HTTPS はこの値に関係なく許可され、HTTP でも loopback は本変数なしで許可される。ソースコード上、この値は TLS 検証、署名検証、取得対象の選択を変更しない（`transfer.py:145-175`, `feed.py:691-717`）。

共通判定は更新 feed と署名ファイルの読み取り、feed 内の絶対 URL、ダウンロード先、およびリダイレクト先に使われる。ドラフターの疎通確認も同じ判定を呼ぶ（`transfer.py:197-217,254-264,298-331,405-418`; `drafting_fetch.py:106-118`）。通常の `strata update` は取得を禁止する起動・serve 経路では実行できず、明示的な update が feed を読んでから各コンポーネントを処理する（`updater.py:438-457,2109-2122`）。

## 値と判定

実装は `os.environ.get("STRATA_UPDATE_ALLOW_HTTP") == "1"` という文字列の完全一致であり、真偽値や整数への変換はしない。環境変数名は定数として置かれ、値自体は `check_url_policy()` の呼び出しごとに `os.environ` から取得される。関数引数 `environ` は呼び出し側が明示した場合の辞書で、通常の本番呼び出しでは省略される（`transfer.py:109-110,166-175`）。

| URL / 値 | 判定 |
|---|---|
| HTTPS URL、値は任意または未設定 | 許可。HTTPS の分岐で直ちに戻る。 |
| loopback の HTTP URL、値は任意または未設定 | 許可。`localhost` または `ipaddress.ip_address(host).is_loopback` が真なら通る。 |
| loopback 以外の HTTP URL、値が文字列 `1` | 許可。 |
| loopback 以外の HTTP URL、未設定・空文字・`0`・`true`・`false`・`01`・`1anything`・` 1` | 拒否。いずれも文字列 `1` と一致しない。 |
| 上記以外の scheme | 拒否。「`{url} is not an https address`」の `TransferError`。 |

判定は scheme が `http` のときにだけ本変数を参照する（`transfer.py:166-175`）。HTTP が拒否されると `TransferError` に `"{url} is plain http; updates are fetched over https (a loopback address is the only exception)"` が設定される。`localhost` は `urlparse(...).hostname` を使って比較し、IP アドレスは標準ライブラリの loopback 判定を使う（`transfer.py:145-151,168-175`）。

## 有効になる条件

- 対象処理が `check_url_policy()` を通る URL であること。feed の読み取りとファイル取得では HTTP URL を実際に開く前に検査し、リダイレクト先も別途検査する（`transfer.py:254-264,298-318,405-418`）。
- loopback 以外の HTTP を通すには、検査時点で値が厳密に `1` であること。プロセス環境にその値が設定されていても、別 scheme・ローカルファイル・通常パスの処理を HTTP に変換しない（`transfer.py:154-175,178-185`）。
- ローカルの feed が外部 URL を参照する場合は、この変数にかかわらず拒否される。`resolve_ref()` は URL ポリシー検査より先に、ローカル feed が remote address を参照することを拒否する（`transfer.py:197-208`）。
- feed からの取得は信頼鍵がある場合に限られる。鍵がなければ HTTP 許可の値にかかわらず `FeedError` となる（`feed.py:691-696`）。
- `strata update` は acquisition が禁止された start / serve 経路からは実行できない。許可値はこの acquisition 制限を変更しない（`updater.py:438-457,2112`）。

## 実行時の詳細

`transfer.py` の import 時に行うのは環境変数名の定数定義だけで、値の読み取りやキャッシュはない。`check_url_policy()` は既定で `os.environ` を参照し、HTTP URL を確認するたびに値を取得する。そのため、プロセス実行中の環境辞書の変更は、その後の検査に反映される（`transfer.py:109-110,166-175`）。

通常の update では `open_feed()` が `feed.fetch()` を呼び、feed 本文と署名を `read_small()` で読む。コンポーネント URL は `Feed.url()` から `resolve_ref()` を通り、取得は `updater._download()` から `transfer.download()` に進む。feed の HTTP URL、絶対 HTTP 参照、ダウンロード URL、各 HTTP リダイレクト先でポリシーを検査する（`updater.py:451-457,574-593`; `feed.py:302-303,691-717`; `transfer.py:197-217,254-264,298-318,405-418`）。

値が `1` でも、HTTP 接続先が応答しない、応答コードがエラー、取得データが feed 記載のサイズまたは SHA-256 と一致しない場合には、取得は成功しない。ダウンロードサイズと SHA-256 は別途検査される（`transfer.py:345-398,445-453`）。

## ログと測定値

本変数を有効にしたことを知らせる専用ログや警告は見当たらない。拒否された HTTP は `TransferError` となり、feed 読み取り時は `FeedError("the update feed could not be read: ...", 6)` に包まれる。コンポーネントのダウンロード時は `updater._download()` が `UpdateError(str(exc), 6)` に変換する（`transfer.py:166-175`; `feed.py:706-714`; `updater.py:590-599`）。

測定値は該当しない。

## 根拠

- `terminal/strata_control/transfer.py:109-110,145-175` — 環境変数名、loopback 判定、値の比較と拒否文言。
- `terminal/strata_control/transfer.py:197-217,254-264,292-331,345-398,405-453` — feed URL 解決、リダイレクト、read/download 経路と取得後の検査。
- `terminal/strata_control/feed.py:302-303,691-717` — feed 内 URL 解決、feed と署名の読み取り、失敗の変換。
- `terminal/strata_control/updater.py:438-457,574-599,2109-2122` — acquisition 制約、update の feed / download 呼び出し、download 失敗の終了コード。
- `terminal/strata_control/drafting_fetch.py:106-118` — ドラフターの疎通確認が共通 URL ポリシーを使う箇所。
