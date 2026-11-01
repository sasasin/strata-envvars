# `STRATA_ADMIT_SHORT_FIRST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更は表示されていません。外部ライブラリの環境変数は対象外。

## 役割

`serve/server.py` のバッチサーバーで、エンジンの制御行（プロンプト読み込みなど）を次に処理する新規リクエストの順序を決めます。指定したトークン数以下の短いプロンプトを、より長いプロンプトより先に扱います。すでに一度 admission されたリクエストの継続にはこの順序付けを適用しません。順序だけを変え、プロンプト内容や計算を変更する処理ではありません（`serve/server.py:1747-1751,1861-1871`）。

この値を読むのは Strata の Python サーバーです。GPU backend や build macro による分岐はありません。効果が現れるのは、実際にエンジンがバッチ slot を使う経路です。

## 値と判定

| 環境値 | `ADMIT_SHORT_FIRST` | 動作 |
|---|---:|---|
| 未設定 | `0` | 無効。ロックを先に取ったリクエストから進む |
| 空文字 | `0` | `or 0` により無効 |
| `0`、負の整数 | `0` | `max(0, int(...))` により無効 |
| 正の整数文字列 | その整数 | 長さがこの値以下の新規プロンプトを先に選ぶ |
| `int()` で整数に変換できない文字列（例: `1.5`、`abc`） | `0` | `ValueError` を捕捉して無効。起動エラーや警告は出さない |

Python の `int()` で変換し、浮動小数点としては読みません。正の値に上限 clamp はありません。プロンプト長は `len(ids)`、つまりサーバーが engine に渡す token ID 列の長さです（`serve/server.py:335-338,1913-1917`）。

## 有効になる条件

- サーバーが複数 slot を使うバッチ経路に入ること。`StrataEngine.generate()` は engine の `batch_slots` が 0 以外のときだけ `generate_batched()` を呼びます。これは engine の実際の slot 数で判定され、要求数どおりの slot が使えない場合もあります（`serve/server.py:1167-1173,2327-2336`）。設定経路は engine 引数の `--batch` / `--slots`、またはサーバー設定の `parallel` です（`serve/server.py:3303-3324`）。
- リクエストがその prompt の最初の admission であること。`generate_batched()` は初回に `_take_control(..., new=True)` を呼びますが、slot から solo 経路へ戻った継続では `new` を指定しないため、短さによる優先順位付けの対象外です（`serve/server.py:1913-1917,1932-1937,1747-1751`）。
- 値が正であること。`ADMIT_SHORT_FIRST <= 0` なら `_admit_next()` を使う分岐に入らず、従来どおりロック取得順です（`serve/server.py:1767-1775`）。

CLI 引数や設定ファイルによるこの値の上書きはありません。サーバーの `--parallel` / `parallel` 設定はバッチ経路を選ぶためのもので、サーバーはそれを engine の `--batch` に渡します。閾値そのものは上書きしません。

## 実行時の詳細

値は `serve/server.py` のモジュール読み込み時に一度だけ評価され、モジュール変数 `ADMIT_SHORT_FIRST` に保持されます。サーバー稼働中にプロセス環境を変更しても再読込されません。反映にはサーバープロセスの再起動が必要です（`serve/server.py:335-338`）。

新規 admission の待機項目には prompt 長と到着時刻が記録されます。`_admit_next()` は待機中の `new=True` の項目から、次のどちらかを満たすものを優先グループとして扱い、その中では到着時刻が最も早いものを選びます（`serve/server.py:1747-1755,1861-1871`）。

1. prompt 長が閾値以下。
2. prompt が長くても、待機時間が `STRATA_ADMIT_MAX_WAIT_S` 以上。

`STRATA_ADMIT_MAX_WAIT_S` は別の環境変数です。未設定時は 30 秒で、共通 helper が `float()` 変換し、不正値は既定値に戻します。0 以下は helper から `None` となり、この箇所では `0.0` に置き換わるため、長い prompt も直ちに優先グループに入ります（`serve/server.py:315-320,339,1867-1871`）。この待ち時間による昇格により、長い新規リクエストが短いリクエストの後ろに恒久的に留まることを避けています。

選ばれたリクエストがロック取得を待つ間にも待機列は変化し得るため、ロック取得後に再度 `_admit_next()` を確認します。自分が次でなくなっていた場合はロックを解放して待ち直します（`serve/server.py:1772-1780`）。この環境変数専用の有効・無効ログや、無効値の警告はありません。

別途 `--queue-timeout` または設定 `queue_timeout` による待ち時間上限がある場合、順番を待つ途中で期限に達すると `QueueWaitExpired` になります。通常の非 streaming API では HTTP 429 と `queue_wait_timeout`、streaming API では同コードのエラー event を返します（`serve/server.py:1758-1766,1781-1785,7552-7557,7907-7910,8140-8144`）。この timeout は閾値の意味を変えず、待機中のリクエストを終了させる別の制約です。

## 根拠

- 実際の環境読み取りと既定値・変換: `serve/server.py:335-338`。
- 初回 admission と順序付け対象の登録: `serve/server.py:1747-1755,1913-1917`。
- 有効条件、ロック待ち中の再確認: `serve/server.py:1767-1785,2327-2336`。
- 短い prompt / 待ち時間 / 到着順の選択: `serve/server.py:1861-1871`。
- バッチ経路の有効 slot 判定と設定: `serve/server.py:1167-1173,3303-3324`。
- 関連するサーバー向け説明: `docs/BATCHING.md:110-125`。`docs/DETAILS.md` にはこの変数の記載はありません。
- `rg -n --hidden --glob '!.git/**' 'STRATA_ADMIT_SHORT_FIRST' .` で確認した全参照は `serve/server.py`、`serve/test_admit_order.py`、`docs/BATCHING.md`。環境から値を読む本番実装は `serve/server.py:336` のみです。テストと文書の記述は実装根拠として扱っていません。
