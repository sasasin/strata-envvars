# `GPUSTAT_VRAM_MB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリ・GPU ドライバーの環境変数動作は対象外。

## 役割

Strata 同梱の Intel GPU telemetry sampler `sycl/tools/gpustat.py` が、出力 JSON の `vram_total_mb` に記録する VRAM 総量を指定します。Strata の推論エンジンや GPU の割り当て量は変更しません。値は Monitor tab が使うメモリ総量表示に渡されます。

## 値と判定

Python の `os.environ.get()` の戻り値を真偽値で判定し、設定値が空でなければ `int()` で変換します。文字列全体を10進整数として変換し、前後の空白と正負の符号を許します。空白だけの値や整数でない値は `ValueError` になり、ここでは捕捉されません。負数や `0` の値は拒否・clamp されず、そのまま総量として返されます。

| 設定 | `vram_total_mb()` の結果 |
|---|---|
| 未設定または空文字 | PCI resource から計算した既定値へ進む |
| `0`、正の整数文字列、負の整数文字列 | `int()` の結果を返す（単位は MiB 相当） |
| 非整数文字列（例: `1.5`, `auto`） | `ValueError` が呼び出し元へ伝播する |

既定値は選択済み PCI デバイスの `/sys/bus/pci/devices/{PCI}/resource` を読み、各 resource 行の終了アドレスから開始アドレスを引いて 1 を加えたサイズの最大値を `2**20` で整数除算した値です。ファイルを読めない場合、またはアドレス変換で `ValueError` が出る場合は `0` になります。既定値計算は `GPUSTAT_VRAM_MB` と異なり `try` 節内です。

## 有効になる条件

この変数を読むのは `sycl/tools/gpustat.py` だけです。Linux の Intel `xe` ドライバー向け sampler を起動したときに適用され、Strata の他の GPU backend や通常の engine 起動には作用しません。ツールの説明では `/run/gpustat.json` を定期更新し、root 権限の systemd service `sycl/tools/gpustat.service` として使う構成です。

`PCI` は別の `GPUSTAT_PCI`、検出された Intel GPU、検出失敗時の `0000:00:00.0` の順で module import 時に選ばれます。`GPUSTAT_VRAM_MB` はそのデバイスの既定値推定だけを置き換えます。デバイス選択や実際の VRAM 使用量計測は変えません。

## 実行時の詳細

`TOTAL_MB = vram_total_mb()` は module-level で実行されるため、環境変数の評価は sampler の Python プロセス起動時（モジュール読み込み時）に一度だけです。起動後の環境変更は再読込されません。`main()` の各周期では `TOTAL_MB` を `vram_total_mb` として `/run/gpustat.json` に書き、`os.replace()` で一時ファイルから更新します。

SYCL 側の `sycl/serve/xe_telemetry.py` は15秒以内の sampler JSON を読み、`vram_total_mb` を `2**20` 倍して Monitor 用の `mem_total` にします。値が `0` なら `mem_total` は `None` になります。負数は truthy のまま負のバイト数になります。sampler JSON が古いか読めない場合、同ファイルの `read()` は sampler 由来の VRAM/load 値を使いません。sampler の `int()` 変換で例外が発生すると、systemd unit の `Restart=always` 設定ではプロセス再起動の対象になります。

## 根拠

- `sycl/tools/gpustat.py:15-17`: ツールの用途と変数の説明。
- `sycl/tools/gpustat.py:37-48`: PCI 選択、値の真偽判定、整数変換、resource による既定値と fallback。
- `sycl/tools/gpustat.py:64,128-160,175-179`: module-level の一度だけの評価、JSON の `vram_total_mb` 出力と更新周期。
- `sycl/tools/gpustat.service:4-8`: sampler の起動コマンドと再起動設定。
- `sycl/serve/xe_telemetry.py:57-64,88-99`: JSON の鮮度判定と Monitor 用の総量・使用量変換。
- `docs/INTEL.md:155-158`: Monitor tab で sampler が load と VRAM を供給する説明。
