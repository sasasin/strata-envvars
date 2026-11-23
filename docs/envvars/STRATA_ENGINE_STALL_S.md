# `STRATA_ENGINE_STALL_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`terminal/serve/server.py` の HTTP サーバーが、応答行を出さない engine を「処理が遅い」のか「停止・凍結した」のか判定する時間窓を秒単位で設定する。既定は90秒。指定時間中に CPU とディスク I/O の動きがほぼなく、GPU も稼働中でないと判定した場合は engine プロセスを終了し、該当リクエストを失敗させる。engine が無音でも処理中なら終了せず、一度だけ警告する。また、batch の空き slot を待つリクエストがこの時間を超えたとき、待ち状況を一度ログに出す。この slot 待ち側は通知だけで、engine やリクエストを終了しない。 (`terminal/serve/server.py:436-442`, `terminal/serve/server.py:2145-2159`, `terminal/serve/server.py:2725-2764`)

これは `terminal/serve/server.py` が読むサーバー側の変数であり、engine バイナリ自身の環境変数読み取りではない。`python -m serve.server --engine strata` などのサーバー経路に適用され、`--engine mock` は `StrataEngine` の request watchdog を通らない。CUDA/HIP/SYCL 等の engine backend 自体による値判定はない。 (`terminal/serve/server.py:1-4`, `terminal/serve/server.py:714-724`, `terminal/serve/server.py:8968-8973`)

## 値と判定

`server.py` の import 時に `_timeout_env("STRATA_ENGINE_STALL_S", 90.0)` を呼ぶ。helper は環境値を Python の `float` に変換し、`ValueError` なら既定値へ戻す。変換後の値が `0` 以下なら `None`（無効）を返す。空文字も変換エラーなので無効化ではなく90秒に戻る。 (`terminal/serve/server.py:442`, `terminal/serve/server_parts/base.py:260-265`)

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| サーバー起動時の共通判定 | `90.0` 秒 | float に変換できる正の有限値。例: `1`, `90`, `1.5`, `1e2` | `0`, `-1`, `-inf` は監視を無効化。空文字、`0anything` などの不正文字列は無効化ではなく既定の90秒へ fallback |

Python の `float` 変換なので、数値文字列全体を変換し、前後空白を含む数値は受理する一方、数値の後ろに文字が続く値は受理しない。大文字小文字の比較や整数限定の検査はない。`nan` は `v <= 0` を満たさず helper から返るが、その後の `stall_s > 0` 判定を満たさないため監視は実質無効。`inf` は正値として返るが、経過時間が `inf` に達しないため判定閾値として機能しない。 (`terminal/serve/server_parts/base.py:260-265`, `terminal/serve/server.py:2147`, `terminal/serve/server.py:2574-2595`)

## 有効になる条件

- `terminal/serve.server` を起動するサーバーモードであること。CLI の `--engine mock` は `MockEngine` となり、engine の出力を待つ `StrataEngine` の watchdog は使わない。 (`terminal/serve/server.py:1-4`, `terminal/serve/server.py:714-724`, `terminal/serve/server.py:8968-8973`)
- リクエスト中の凍結判定は、engine から新しい行が来ず、正の stall 閾値を超えて無音が続く場合に行う。CPU 利用量が窓内で0.5秒以下、読み書き量が1 MiB以下で、GPU 使用率が10%未満（または GPU 使用状況を取得できず busy 扱いでない）なら凍結として終了する。 (`terminal/serve/server.py:2570-2611`, `terminal/serve/server.py:2714-2749`, `terminal/serve/server_parts/base.py:294-302`)
- `psutil` が利用できず CPU/I/O の測定値を得られない場合、`_activity()` は `None` を返し、凍結による終了判定はしない。GPU の稼働中判定は telemetry のスナップショットから行い、いずれかの GPU 使用率が10%以上なら engine を凍結扱いにしない。 (`terminal/serve/server.py:2714-2723`, `terminal/serve/server.py:2734-2749`, `terminal/serve/server.py:4925-4942`)
- 同じ変数は batch の空き slot 待ちにも使われる。ここでは slot が空かない状態が閾値を超えると待ち状況を一度出力するが、これ自体は engine の凍結判定ではない。 (`terminal/serve/server.py:2145-2159`)
- 別設定の `engine_silence_s` は、リクエスト中に engine が無音でいられる上限を定める。こちらは CPU/I/O/GPU の活動判定とは別に働き、より早く上限に達すればその経路で engine が終了し得る。`STRATA_ENGINE_STALL_S` はこの設定や CLI 引数を上書きしない。 (`terminal/serve/server.py:2570-2584`, `terminal/serve/server.py:8935-8963`)

## 実行時の詳細

環境変数は `server.py` のモジュール初期化時に一度読み取られ、`ENGINE_STALL_S` に保持される。リクエスト開始時にその値をローカル変数 `stall_s` へ取り、無音を検査するループで使用するため、サーバープロセス稼働中に環境を書き換えても値は再読込されない。設定値は engine の子プロセスに渡して engine 側で使うものではない。 (`terminal/serve/server.py:442`, `terminal/serve/server.py:827-829`, `terminal/serve/server.py:2570-2575`)

無音中、最初のチェックで CPU 秒と読み書き byte 数の基準値を取り、その後 stall 窓ごとに再計測する。各窓で CPU 増分が `0.5` 秒以下かつ I/O 増分が `1 MiB` 以下なら「凍結候補」とし、telemetry が GPU 使用中と示していないことも確認する。凍結条件を満たせば `EngineSilent` を発生させ、`_silent()` がプロセスを kill して終了済みと記録する。次のリクエストでは engine が再起動される。活動が観測された場合は警告を一度出し、その後も窓ごとに再判定する。CPU/I/O の測定値を得られない場合は凍結判定をせず、終了もしない。 (`terminal/serve/server.py:2576-2611`, `terminal/serve/server.py:2714-2764`, `terminal/serve/server_parts/base.py:294-302`)

無音が続く間でも engine が活動していれば、この変数による終了はしない。ただし `engine_silence_s` の上限は別に適用される。engine が出力行を返すと無音計測の基準時刻と stall 状態がリセットされる。 (`terminal/serve/server.py:2570-2613`, `terminal/serve/server.py:2742-2749`)

## ログと測定値

活動中の engine が無音のまま閾値を超えた場合、サーバー標準出力に次の警告を一度出す（閾値を過ぎた無音秒数を埋め込む）。

```text
[strata] the engine has said nothing for {age:.0f} s but is still working; it is not ended (the limit is engine_silence_s). If it is stuck, "engine_silence_s" can be set lower.
```

凍結と判定した場合、`EngineSilent` の理由に次の文言を含め、engine を終了する。

```text
the engine said nothing for {age:.0f} s and used no CPU or disk in that time (frozen; STRATA_ENGINE_STALL_S sets this, 0 = off); the server ended the engine
```

`age` は経過秒を整数に丸めて表示する。通常の JSON API 経路では回答開始前の `EngineDied` として HTTP 503 とエラー理由を返す。設定値の fallback や無効化について専用ログはない。測定値の記載はない。 (`terminal/serve/server.py:2740-2764`, `terminal/serve/server.py:7530-7533`)

## 根拠

- 読み取り箇所と既定値: `terminal/serve/server.py:436-442`
- 共通の値変換、fallback、0以下の無効化: `terminal/serve/server_parts/base.py:260-265`
- 空き slot 待ちでの通知: `terminal/serve/server.py:2145-2159`
- リクエスト内の監視開始・無音ループ: `terminal/serve/server.py:2567-2613`
- CPU/I/O 取得と無音凍結判定: `terminal/serve/server.py:2714-2749`; 閾値: `terminal/serve/server_parts/base.py:294-302`
- GPU 活動判定: `terminal/serve/server.py:4925-4942`
- engine 終了処理: `terminal/serve/server.py:2751-2764`
- HTTP 503 への変換: `terminal/serve/server.py:7530-7533`
- サーバー起動時に telemetry を初期化: `terminal/serve/server.py:8263-8268`
- 説明資料との照合: `docs/DETAILS.md:1524-1525`。既定90秒、値での変更、0による無効化、psutil が必要という説明は実装と一致する。
