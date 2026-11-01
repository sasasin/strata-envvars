# `GPUSTAT_INTERVAL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

同梱の Intel GPU telemetry sampler `sycl/tools/gpustat.py` が `/run/gpustat.json` を更新する間隔（秒）を指定します。これは Strata 本体の GPU 計算間隔や生成処理を制御する変数ではありません。sampler が systemd サービスとして起動されている場合に、Monitor 用の load・VRAM 等の更新頻度に影響します。

## 値と判定

| 状態 | 判定・結果 |
|---|---|
| 未設定 | 文字列 `"3"` を `float()` で変換し、3.0 秒を使う |
| 空文字 | `float("")` の変換で `ValueError`。例外を捕捉しないため sampler は起動時に失敗する |
| 数値文字列 | Python の `float()` で変換した値を使う。整数・小数・符号・前後空白を含む文字列を変換できる |
| 数値に変換できない文字列 | `float()` の `ValueError` が捕捉されず、sampler は起動時に失敗する |
| 0 | clamp されず 0.0 秒として `time.sleep()` に渡るため、sleep による待ちを置かないループになる |
| 負数 | `float()` 変換自体は通るが、サンプルを書き出した後の `time.sleep()` で失敗する |
| `nan` / `inf` 等 | `float()` が受け付けた場合も値の範囲検証はなく、そのまま `time.sleep()` に渡る |

環境変数の存在だけを真偽値として調べたり、`1` と比較したりはしません。`os.environ.get("GPUSTAT_INTERVAL", "3")` の既定値は変数が未設定の場合にだけ使われるため、明示した空文字は既定値へ戻りません。CLI 引数、設定ファイル、別環境変数による上書きもありません。

根拠: `sycl/tools/gpustat.py:19-22,128-136,175-179`。

## 有効になる条件

- `sycl/tools/gpustat.py` が実行される場合にだけ読み取られます。リポジトリ内の `sycl/tools/gpustat.service` は `/usr/local/sbin/gpustat.py` を起動し、異常終了時は `Restart=always`、再起動まで 5 秒としています。service 自身にはこの値の指定がなく、CLI 引数にも渡していません。
- このツールは Linux の `/proc`、`/sys`、`/run` を使う Intel GPU（xe）向けの同梱ツールです。CUDA/HIP の Strata 実行経路や build macro による条件はありません。手動実行も可能ですが、Strata の本体サーバーが自動で sampler を起動する処理は確認できませんでした。
- SYCL の Intel Monitor は `/run/gpustat.json` の `ts` が現在から 15 秒未満の場合に sampler の値を採用します。したがって interval を 15 秒以上にすると、更新の間に sampler の統計値が stale と判定され、Monitor では load・VRAM 等を採用できない時間が生じます。Monitor は温度・電力・PCIe 情報の一部を sysfs から補完します。

根拠: `sycl/tools/gpustat.service:4-7`, `sycl/serve/xe_telemetry.py:1-6,57-64,88-100`。

## 実行時の詳細

`INTERVAL` はモジュール読み込み時に一度だけ評価されます。sampler の `main()` は各ループで `/proc` 等から値を集め、JSON を一時ファイルへ書いて `/run/gpustat.json` に置き換えた後、`time.sleep(INTERVAL)` を呼びます。プロセス実行中に環境変数を変更しても、既に評価された `INTERVAL` は再読込されません。

変換エラーは `main()` より前のモジュール初期化で発生します。負数等、sleep に渡せない値は最初の JSON 書き込み後にループ内で失敗します。スクリプトにこの例外を捕捉する処理や独自のエラーログはなく、Python の例外がプロセス終了として表れます。systemd unit を使っている場合は `Restart=always` に従い、5 秒後に再起動します。

参照: `sycl/tools/gpustat.py:21-22,128-136,175-182`, `sycl/tools/gpustat.service:4-7`。

## 根拠

- 読み取り・既定値・変換: `sycl/tools/gpustat.py:19-22`。
- サンプリングループ、JSON 更新、sleep: `sycl/tools/gpustat.py:128-179`。
- systemd 起動・再起動設定: `sycl/tools/gpustat.service:1-10`。
- Monitor での統計ファイルの鮮度判定と利用: `sycl/serve/xe_telemetry.py:57-64,88-100`。
- Monitor 用 sampler の役割に関する文書: `docs/INTEL.md:159-162`。
