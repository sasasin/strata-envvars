# `GPUSTAT_INTERVAL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Intel Arc（xe ドライバー）向けの GPU telemetry sampler `sycl/tools/gpustat.py` が、GPU 状態のサンプルと `/run/gpustat.json` の更新の間に待つ秒数を指定します。Strata の推論エンジンや全体のリクエスト間隔を制御する変数ではなく、この同梱診断ツールだけが読み取ります。

## 値と判定

| 環境変数の状態 | `INTERVAL` | 結果 |
|---|---:|---|
| 未設定 | `3.0` 秒 | 既定の間隔で動作 |
| 設定あり | Python の `float()` で変換した値 | 変換に成功すればその値を `time.sleep()` に渡す |
| 空文字、または `float()` が認識しない文字列 | なし | モジュール読み込み時に `ValueError` となり、sampler は開始しない |

文字列全体を `float()` に渡すため、整数・小数・符号付き数値・指数表記や、Python が認識する `inf` / `nan` 表記を受け付けます。単位換算、丸め、clamp、正の値かどうかの事前検査はありません。負数は `time.sleep()` で `ValueError`、`nan` も sleep 時にエラーとなります。正の無限大など実装上 sleep できない値も、通常の周期動作には使えません。空白だけの値も変換できず起動時エラーです。

## 有効になる条件

- `sycl/tools/gpustat.py` を実行するときだけ参照されます。通常の Strata engine 起動や、`sycl/serve/xe_telemetry.py` が sysfs から値を読む経路では、この変数を読みません。
- この sampler は Linux の Intel xe GPU 向けとして記述され、root で実行する systemd service の例が同梱されています。サンプル処理は `main()` の無限ループに入ります。
- service unit は `ExecStart` と再起動設定だけを持ち、`GPUSTAT_INTERVAL` を指定していません。値を変える場合は、sampler プロセスの環境に設定して起動する必要があります。

## 実行時の詳細

`INTERVAL` は Python モジュールの読み込み時に一度だけ評価されます。各ループで `/proc/*/fd` と fdinfo、hwmon、PCI sysfs などを読み、JSON を一時ファイルに書いて `/run/gpustat.json` へ置換した後、`time.sleep(INTERVAL)` します。したがって、サンプル開始時刻の間隔は、指定秒数に加えて各サンプル処理にかかった時間が加わります。実行中にプロセス環境を変えても、読み込み済みの `INTERVAL` は再評価されません。

`xe_telemetry.py` は `/run/gpustat.json` の `ts` が現在時刻から15秒未満の場合に sampler の値を利用します。この期限を超えた場合も、温度・電力・PCIe link は sysfs から表示できますが、sampler由来の load と VRAM 値などは利用されません。

## 根拠

- `sycl/tools/gpustat.py:1-17`: ツールの用途、出力先、root sampler と設定可能な環境変数の説明。
- `sycl/tools/gpustat.py:19-22`: `os.environ.get("GPUSTAT_INTERVAL", "3")` の import 時評価と `float()` 変換。
- `sycl/tools/gpustat.py:128-179`: 初期化、サンプリングループ、JSON の置換、各ループ末尾の `time.sleep(INTERVAL)`。
- `sycl/tools/gpustat.service:1-10`: service の起動コマンドと再起動設定。環境変数の指定はない。
- `sycl/serve/xe_telemetry.py:43-50,74-85`: sampler JSON の読み取りと15秒の鮮度判定、Monitor tab 向けの値利用。
- `docs/INTEL.md:407-414`: Intel 向け Monitor tab での sampler の役割。
