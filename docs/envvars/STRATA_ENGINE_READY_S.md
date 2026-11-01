# `STRATA_ENGINE_READY_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata --serve` の Python サーバーが engine 子プロセスを起動した後、標準出力から `READY` 行を待つ秒数を指定します。既定は 900 秒です。engine のモデル読込などが長引いても、設定時間内に `READY` が届けば起動を継続します。これは server 側の待機上限であり、engine の読込処理自体の設定ではありません。

## 値と判定

モジュール読み込み時に Python の `float()` で環境変数を変換します。未設定時は `900.0`、空文字または数値に変換できない文字列は `ValueError` を捕捉して `900.0` に戻ります。変換後の値が `0` 以下なら timeout を `None` にし、時間制限なしで待ちます。正の数値はその秒数を使います。整数・小数・指数表記など `float()` が受理する書式が対象で、整数への丸めや上限 clamp はありません。`NaN` や無限大のような非有限値には明示的な検査がありません。

| 環境変数値 | server の timeout |
|---|---:|
| 未設定 | 900 秒 |
| 空文字・不正な数値 | 900 秒へ fallback |
| `0`、負数 | 無期限（READY を待つ） |
| 正の数値（例: `30`, `0.5`） | 指定秒数 |

## 有効になる条件

この値は `serve/server.py` が import される実行経路で評価され、engine を起動して `READY` を待つ際に使われます。CLI の独立した timeout 引数による上書きはありません。サーバー設定 JSON の `engine_ready_s` が数値として存在すると環境変数由来の値を上書きします。ただし設定値は bool ではない int/float かつ `> 0` でなければならず、違反時は設定エラーで起動を止めます。したがって config の `engine_ready_s: 0` は環境変数と異なり無期限指定にならず無効です。

適用先は server が管理する engine 子プロセスの起動待ちです。OS や GPU backend 別の分岐はこの判定にはありません。

## 実行時の詳細

`serve/server.py` のモジュール初期化で `_timeout_env("STRATA_ENGINE_READY_S", 900.0)` が一度呼ばれます。値を module global `ENGINE_READY_S` に保持するため、server 起動後の `os.environ` 変更は反映されません。server 設定に `engine_ready_s` がある場合、engine 起動前に `apply_ready_timeout()` が global を更新します（この関数は同一プロセス内の後続起動にも影響します）。

engine 起動後、別スレッドが標準出力行を queue に渡し、起動処理は `ENGINE_READY_S` から deadline を作って `READY` を待ちます。タイムアウトすると engine を kill し、`EngineDied` に `the engine did not report READY within N s` を含めます。engine が先に終了した場合は `the engine exited before it was ready` の失敗経路です。通常の要求経路ではこの失敗を通じてロード待ちの要求を 503 にします。timeout 後に自動再試行する分岐はなく、再試行分岐は timeout ではない一時的な起動失敗に限られます。

## 根拠

- `serve/server.py:307-320`: READY 行待ち timeout の説明と `_timeout_env()` の変換、fallback、0 以下を無期限にする判定。
- `serve/server.py:362-364`: import 時の環境変数読み取りと既定値 900 秒。
- `serve/server.py:1085-1110`: engine 起動後の deadline 設定、READY 待ちと受信処理。
- `serve/server.py:1111-1153`: timeout 時の kill、失敗理由、engine 終了時のエラー経路。
- `serve/server.py:3211-3220,9252-9256`: config の `engine_ready_s` による上書き、型・正数チェック、設定エラー。
- `serve/server.py:1145-1147`: READY 起動失敗を `EngineDied` として扱う説明。
- `docs/DEEPSEEK41.md:94`: 大きなモデル向けに config の `engine_ready_s` を 3600 秒にする記載。環境変数自体の性能測定値は確認できません。
