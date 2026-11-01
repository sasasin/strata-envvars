# `GPUSTAT_PCI`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業状態は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

同梱ツール `sycl/tools/gpustat.py` が telemetry の対象にする PCI アドレスを指定します。これは Strata の通常の engine が GPU を選ぶ設定ではなく、Intel Arc / xe driver 向け telemetry sampler の設定です。スクリプトは `GPUSTAT_PCI` を直接読み、値を sysfs のデバイスパス、`lspci` の `-s` 引数、出力 JSON の `pci` 欄に使います。

## 値と判定

| 環境値 | `PCI` に使われる値 |
|---|---|
| 未設定 | `find_card()` が見つけた最初の Intel GPU（xe の `tile*/gt*` を持つもの）、なければ `0000:00:00.0` |
| 空文字 | Python の `or` により未設定時と同じ fallback |
| 空でない文字列 | 文字列を変換・検証せず、そのまま使用 |

例として `0000:03:00.0` のような形式が docstring に示されていますが、実装は書式、範囲、デバイスの存在を事前検証しません。空白や不正な文字列も非空なら採用されます。数値変換、大小文字判定、範囲 clamp はありません。

## 有効になる条件

- Linux sysfs の `/sys/class/drm`、`/sys/bus/pci/devices` を参照する `sycl/tools/gpustat.py` を実行する場合に適用されます。同梱の `sycl/tools/gpustat.service` はこのスクリプトを `/usr/local/sbin/gpustat.py` から起動する設定です。
- CUDA/HIP/SYCL build macro、Strata CLI 引数、モデル状態による分岐はこの読み取り箇所にはありません。
- CLI 引数や他の環境変数による上書きはありません。未設定または空文字のときは `find_card()` の自動検出が先に使われ、検出できなければ固定値 `0000:00:00.0` になります。

## 実行時の詳細

`PCI` はスクリプトの import 時にモジュール変数として一度だけ評価されます。プロセス稼働中の環境変更を再読込する処理はありません。sampler の `main()` はこの値で `/sys/bus/pci/devices/{PCI}/device` を読み、カード名の `lspci -mm -s PCI` に渡し、PCIe link と GPU 周波数の sysfs パスを組み立てます。各 telemetry JSON にも同じ値を `pci` として格納します。

読み取りに失敗した際の Strata 側の扱いとして、デバイス ID の読み取りは `0x0` に fallback し、カード名取得時の `OSError` または `subprocess.SubprocessError` は握りつぶして `Intel GPU 8086:{dev_id}` を返します。PCIe link は該当デバイスパス上の link 情報をたどれなければ `None` になります。VRAM BAR の読み取りは `OSError` または `ValueError` 時に合計 0 MB を返します。これらの処理は設定文字列そのものを補正しません。sampler は標準出力・標準エラーへの専用警告を出さず、生成 JSON に `pci` と上記 fallback 結果を記録します。

`sycl/serve/xe_telemetry.py` は `/run/gpustat.json` を読み、15 秒より古いデータを使わない処理を持ちますが、`GPUSTAT_PCI` は読まず、Strata server から sampler へ値を渡すコードも確認できませんでした。したがって値の適用範囲は sampler プロセスです。

## 根拠

- `sycl/tools/gpustat.py:1-17` — スクリプトの用途、systemd sampler であること、候補値と既定動作の説明。
- `sycl/tools/gpustat.py:26-37` — xe 用 Intel GPU の自動検出と `GPUSTAT_PCI` の読み取り、未設定・空文字時の fallback。
- `sycl/tools/gpustat.py:40-48,51-61,68-82` — PCI 値を使う sysfs / `lspci` 経路と、読み取り・例外時の sampler 内 fallback。
- `sycl/tools/gpustat.py:128-135,158-179` — sampler 起動時のデバイス情報取得、出力 JSON と定期更新。
- `sycl/tools/gpustat.service:1-10` — sampler を起動する同梱 systemd unit。
- `sycl/serve/xe_telemetry.py:21-25,57-64,88-116` — server 側が読むのは `/run/gpustat.json` であり、環境変数は読まないこと。
