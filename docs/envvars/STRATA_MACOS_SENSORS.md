# `STRATA_MACOS_SENSORS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

macOS で Monitor 用の GPU 温度・電力の読み取りを opt-in する。`terminal/serve/telemetry.py` の `apple_sensors()` は macOS 以外、または値が文字列 `"1"` と一致しない場合に `None` を返し、一致する場合は `AppleSensors` を作る（`terminal/serve/telemetry.py:959-964`）。`monitor_reader()` がこのセンサーを macOS の非 AMD GPU reader にだけ接続し、`_Metal.read()` が `temp` と `power` として返す。既存の GPU load / memory の取得やエンジンの計算を変える処理ではない（`terminal/serve/telemetry.py:1040-1061,1433-1445`）。

## 値と判定

`os.environ.get("STRATA_MACOS_SENSORS") != "1"` という完全一致で判定する。数値変換、空白除去、大小文字変換はしない（`terminal/serve/telemetry.py:962-963`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| macOS (`sys.platform == "darwin"`) | 無効。`apple_sensors()` は `None` | `1` のみ | 空文字、`0`、`true`、`TRUE`、` 1`、`1 `、`01`、`1anything` など |
| macOS 以外 | 無効。環境変数を有効化判定に使わず `None` | なし | すべて |

CLI 引数や別の環境変数による上書き・優先順位は、この読み取り経路にはない。値が有効でも、センサーが利用可能でなければ温度・電力が得られるとは限らない（`terminal/serve/telemetry.py:953-964,1015-1020`）。

## 有効になる条件

- 実行環境が macOS で、Monitor の telemetry reader を作る時点で値が厳密に `1` であること（`terminal/serve/telemetry.py:962-964,1433-1442`）。
- reader が AMD 経路ではないこと。`monitor_reader()` は `amd=True` のとき Apple センサーを接続しない（`terminal/serve/telemetry.py:1438-1445`）。
- 温度・電力の実値には、対応する macOS センサー読み取り元が利用可能であること。`AppleSensors.available()` は有効範囲内の GPU 温度、または IOReport 購読のいずれかを確認する。利用できる読み取り元がない場合、note は有効時の説明に変わらず、読み取り値も得られない（`terminal/serve/telemetry.py:936-956,1015-1020`）。
- この環境変数を読む箇所に build macro、モデル状態、CLI オプションの追加条件はない。サーバー側の VRAM 判定や drafter の sizing は `gpu_reader()` を使い、このセンサーを受け取らない（`terminal/serve/telemetry.py:1433-1437`; `terminal/serve/server.py:3760-3775`）。

## 実行時の詳細

サーバーが `Telemetry` を初期化すると、対象 GPU ごとに `monitor_reader()` が作られる。この時点で `apple_sensors()` が環境値を読み、該当すれば `AppleSensors` を構築する。`Telemetry` はサンプラー thread を開始し、1 秒ごとの `sample()` で reader の `read()` を呼び、温度・電力を `/metrics` の GPU telemetry に含める（`terminal/serve/telemetry.py:1433-1445,1704-1719,1777-1803,1826-1850`; `terminal/serve/server.py:4925-4933,8265`）。

値は reader の構築時に読む。既存の `Telemetry` インスタンスは reader とセンサー接続を保持するため、プロセス実行中に環境値だけを変更してもそのインスタンスには反映されない。コード上、環境値自体を static cache する処理はない（`terminal/serve/telemetry.py:959-964,1433-1442,1717-1719`）。

温度は、まず SMC GPU 温度のうち `0 < t < 110` °C を採用し、該当値がなければ名前が `GPU MTR Temp` で始まり `0 <= t < 110` °C の HID 温度を使う。複数値は平均して小数 1 桁に丸め、なければ `None`。電力は `GPU Energy` チャンネルの対応単位（mJ / uJ / µJ / nJ）をジュールに換算し、前回サンプルからの秒数で割って W にする。最初の energy 読み取りは差分基準なので電力は `None` で、後続で正の経過時間と対応チャンネルが得られた場合に値が出る（`terminal/serve/telemetry.py:927-951`; `terminal/serve/telemetry.py:1040-1061`）。

## ログと測定値

センサーが利用可能な場合、`_Metal.note` は `GPU temperature and power from macOS's sensors without root (STRATA_MACOS_SENSORS=1 turned them on); an Apple Silicon GPU sits on the die, so there is no PCIe link to show` に変わる（`terminal/serve/telemetry.py:974-975,1015-1020`）。Monitor telemetry の sample で例外が起きると、sampler は最初の 1 回だけ `[strata] metrics: a sample failed ({e}); the sampler keeps trying` を出し、1 秒待って再試行する。失敗した sample では最新 telemetry を更新しない（`terminal/serve/telemetry.py:1826-1850`）。この環境変数に関する測定値は記載されていない。

## 根拠

- 値の判定とセンサー構築: `terminal/serve/telemetry.py:959-964`
- Monitor reader への限定的な接続: `terminal/serve/telemetry.py:1417-1445`
- 温度・電力の集計と欠損判定: `terminal/serve/telemetry.py:919-956,1040-1061`
- サンプラーと `/metrics` telemetry の生成: `terminal/serve/telemetry.py:1704-1719,1777-1803,1826-1855`; `terminal/serve/server.py:4925-4933,8265`
- サーバーの VRAM 読み取り経路: `terminal/serve/server.py:3760-3775`
