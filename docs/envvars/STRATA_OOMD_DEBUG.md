# `STRATA_OOMD_DEBUG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`terminal/serve/oomd_pacer.py` の `make_room()` が、モデル読み込み前にファイルキャッシュを解放しない理由、または処理後のキャッシュ量などをサーバーの標準出力へ診断表示するための変数です。`make_room()` は `terminal/serve/server.py` のエンジン起動経路から毎回呼ばれます。変数はキャッシュ解放の可否・対象・量を変えず、診断行の表示だけを切り替えます（`terminal/serve/oomd_pacer.py:380-389, 432-439`, `terminal/serve/server.py:823-829`）。

## 値と判定

`make_room()` の呼び出し時に `environ.get("STRATA_OOMD_DEBUG") == "1"` と文字列全体を完全一致で比較します。数値変換や真偽値変換はありません。未設定・空文字・`0`・`true`・`True`・` 1`・`1 `・`01`・`1anything` はすべて無効で、ASCII の文字列 `1` だけが有効です（`terminal/serve/oomd_pacer.py:380-388`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `make_room()` が呼ばれるとき | 無効 | `1` | 空文字、`0`、`true`、大文字小文字違い、空白付き、`01`、`1anything` など、文字列 `1` 以外すべて |

この判定値を CLI 引数や別の環境変数が上書きする処理はありません。`STRATA_OOMD_ROOM=0` はキャッシュ解放処理を止めますが、デバッグが有効ならその分岐の理由 `turned off` は表示されます（`terminal/serve/oomd_pacer.py:390-396`）。

## 有効になる条件

- `terminal/serve/server.py` のサーバーがエンジンを起動する経路で `make_room(args)` を呼ぶことが条件です。この呼び出しは `popen()` より前にあり、engine の環境変数として読むのではなく、サーバープロセスの環境を参照します（`terminal/serve/server.py:823-829`）。
- `make_room()` の診断分岐自体に OS・backend・build macro の条件はありません。たとえば `_DONTNEED` が利用できない環境や、OOMD 対象外の環境でも `make_room()` が呼ばれれば、該当する理由を表示します（`terminal/serve/oomd_pacer.py:46-49, 380-396`）。
- 実際にキャッシュを解放する条件はデバッグ表示とは別です。`STRATA_OOMD_ROOM=0` または `POSIX_FADV_DONTNEED` がない場合は停止します。そうでなければ Linux の user manager 配下で systemd-oomd が kill 設定になっているか、コンテナとして検出される必要があり、さらにファイルキャッシュが 1 GiB 以上で、モデルファイル合計に対して空きメモリが不足している必要があります（`terminal/serve/oomd_pacer.py:95-114, 380-419`）。
- `STRATA_OOMD_PACER=0` のとき `applicable()` は user-manager の適用条件を満たさない扱いになります。コンテナ検出経路は別に評価されるため、コンテナなら `make_room()` のキャッシュ解放条件が残る場合があります（`terminal/serve/oomd_pacer.py:95-100, 393-406`）。

## 実行時の詳細

環境値は `make_room()` の呼び出しごとに `os.environ`（テスト等から `environ` が渡された場合はその辞書）から読み、関数内のローカル変数 `debug` に保持します。プロセス起動時の固定値や関数外の cache ではありません。同一呼び出し中に環境が変わっても再評価せず、次のエンジン起動で再度読みます（`terminal/serve/oomd_pacer.py:380-389`; 呼び出し元 `terminal/serve/server.py:823-824`）。

有効時は、何もしなかった各分岐で `[strata] memory guard (debug): make_room: <理由>` を `print(..., flush=True)` します。理由は `turned off`、`not below a user manager watched by systemd-oomd`、`no user manager cgroup`、`file cache of the manager <値> < 1073741824`、`enough room: free <値>, files <件数>, bytes <合計>`、または例外時の `error <例外型>: <内容>` です。キャッシュ解放ループに進んだ場合は、解放できた量にかかわらず `[strata] memory guard (debug): make_room: cache <解放前> -> <解放後>, <ファイル数> files, free <空き量>` を表示します（`terminal/serve/oomd_pacer.py:386-441`）。

この関数は失敗を握りつぶして 0 を返す設計で、デバッグ表示もエンジン起動を失敗させません。解放量が 256 MiB 以上なら、デバッグ設定にかかわらず通常の `[strata] memory guard: freed ...` 行も出力します。`STRATA_OOMD_DEBUG` は読み込み中にエンジンを一時停止する別処理 `start()` のログには作用しません（`terminal/serve/oomd_pacer.py:127, 434-441, 574-596`）。

## ログと測定値

診断行の実装文字列は上記のとおりです。`make_room()` は `print` を使い、サーバープロセスの標準出力へ即時 flush します。解放が 256 MiB 以上の場合の通常ログ文言は `terminal/serve/oomd_pacer.py:434-438` にあります。`docs/DETAILS.md` にこの変数固有の測定値はありません。

## 根拠

- 読み取り・理由表示・例外時の戻り: `terminal/serve/oomd_pacer.py:380-396, 432-441`
- 解放条件と通常ログ: `terminal/serve/oomd_pacer.py:391-439`
- OOMD 適用判定: `terminal/serve/oomd_pacer.py:95-114`
- サーバーの呼び出し順と engine 起動: `terminal/serve/server.py:823-836`
