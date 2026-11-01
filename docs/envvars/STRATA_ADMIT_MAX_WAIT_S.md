# `STRATA_ADMIT_MAX_WAIT_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーの StrataEngine が新しい要求を制御ライン（engine に prompt を送って admission を進める排他区間）へ通す順番を調整します。`STRATA_ADMIT_SHORT_FIRST` が正数のとき、長い prompt もこの秒数以上待つと短い要求と同じ優先グループに入り、長い要求が短い要求に後回しにされ続けるのを避けます。この変数単独では順序を変えません。

## 値と判定

値は Python の `float()` で変換されます。`_timeout_env()` は変換に失敗した場合に既定値を返し、変換後の値が `0` 以下なら `None` を返します。その後、この変数の代入式が `None` を `0.0` に置き換えます。

| 環境変数の状態・値 | `ADMIT_MAX_WAIT_S` | 順序判定での意味 |
|---|---:|---|
| 未設定 | `30.0` | 長い新規要求は到着から30秒以上で優先グループへ入る |
| 空文字、または `float()` が変換できない文字列 | `30.0` | 変換失敗時の既定値 |
| 正の数値文字列 | その数値 | 長い新規要求がその秒数以上待つと優先グループへ入る |
| `0`、負数 | `0.0` | 長い新規要求も直ちに優先グループへ入り、全新規要求が到着順で比較される |
| `nan` | NaN | `経過秒 >= ADMIT_MAX_WAIT_S` が成立しないため、長い要求は待ち時間で優先グループへ移らない |

`float()` が受理する数値表記（例: 指数表記や `inf`）も数値として保持されます。正の無限大では実際の有限な待ち時間は閾値に達しません。正の通常値に上限・clamp はありません。明示的な `+0` や `-0` も `0.0` として扱われます。無効文字列や空文字で警告は出ません。

## 有効になる条件

- `serve/server.py` の `ADMIT_SHORT_FIRST` が正数であることが必要です。この値は `STRATA_ADMIT_SHORT_FIRST` を整数変換し、未設定・空文字・無効値を `0`、負数を `0` にします（同ファイル `336-338` 行）。0 の場合、`_take_control()` は `_admit_next()` による優先順判定を行いません。
- StrataEngine に新規要求の初回 admission が到着し、制御ラインを待つ新規要求がある場合に働きます。すでに admission 済みの要求が slot を続行するために制御ラインへ戻る経路は `new=True` を渡さず、この新規要求の順序付けの対象外です。
- backend、OS、GPU、build macro、モデルの内容による条件はありません。効果があるのは Python サーバーの StrataEngine の要求スケジューリングです。`MockEngine` や Strata の C++ エンジン実装でこの名前を読み取る箇所はありません。
- CLI 引数によるこの閾値の上書きはありません。`STRATA_ADMIT_SHORT_FIRST` が機能を有効にする別環境変数です。

## 実行時の詳細

`_timeout_env()` と `ADMIT_MAX_WAIT_S` は `serve/server.py` のモジュール初期化時に評価され、モジュール定数に保存されます。サーバープロセス起動後に環境を変更しても再読み込みされません。設定ファイルの `env` は engine 子プロセス向け環境を組み立てる際に追加・上書きされますが、この Python 定数を変更しません（`child_env()` は `os.environ` を複製した後に設定値を適用します）。

初回の `StrataEngine.generate()` は `_take_control(..., new=True)` を呼びます。`_take_control()` は待機要求の prompt 長、単調時計による到着時刻、新規要求かどうかを `wait_lens` に記録します。`STRATA_ADMIT_SHORT_FIRST > 0` なら、制御 lock を得る前と得た後に `_admit_next()` を確認し、自分が選ばれていなければ lock を譲って待ち直します。選択関数は新規要求のうち、prompt 長が `ADMIT_SHORT_FIRST` 以下か、待ち時間がこの変数の閾値以上の要求を先のグループとし、そのグループ内は到着順にします。どの要求の prompt を engine に送るかが変わりますが、コード注釈によれば変更するのは順序であり、読み取る内容ではありません。

この変数の値について専用のログ、警告、終了・timeout 経路はありません。通常の制御 lock 待ちでは最大0.5秒間隔で再評価し、待機中の要求は10秒ごとに heartbeat を yield します。これは待ち時間を打ち切る timeout ではありません。別途、要求に queue deadline が設定され期限を過ぎた場合は `QueueWaitExpired("the inference queue wait deadline expired; retry later")` になりますが、その期限はこの環境変数からは設定されません。

## 根拠

- `serve/server.py:315-320,339`: 数値変換、既定値、非正値の処理、およびモジュール定数への代入。
- `serve/server.py:331-338`: `STRATA_ADMIT_SHORT_FIRST` の値変換と、この変数が待ち時間で長い prompt を優先対象にする説明。
- `serve/server.py:1747-1755,1767-1780`: 制御ライン待ち要求の記録、新規要求だけの選択確認、lock 取得後の再確認。
- `serve/server.py:1788-1795`: lock 待ちの再試行間隔と heartbeat。
- `serve/server.py:1861-1871`: 対象要求の絞り込みと、prompt 長・待ち時間・到着順による選択。
- `serve/server.py:1913-1917,1933-1937,2051-2064`: 初回 admission は `new=True`、再入場や譲り後の制御ライン取得は `new` を指定しないこと。
- `serve/server.py:3747-3763`: engine 子プロセス環境は親環境の複製から始まり、設定ファイルの `env` が追加・上書きされること。
- `docs/BATCHING.md:125`: `STRATA_ADMIT_SHORT_FIRST` の説明と、この変数の既定30秒という資料上の説明。実際の判定根拠は上記コード。
