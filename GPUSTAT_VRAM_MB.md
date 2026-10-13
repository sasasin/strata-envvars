# `GPUSTAT_VRAM_MB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。Strata 同梱ツールの読み取りを対象とし、外部ライブラリやドライバー内部の挙動は扱わない。

## 役割

Intel xe GPU 用の同梱テレメトリー sampler `sycl/tools/gpustat.py` が、VRAM 総量として `/run/gpustat.json` に書く MiB 値を指定する。Web server 自体はこの環境変数を読まず、sampler が出力した `vram_total_mb` を `sycl/serve/xe_telemetry.py` が byte 単位に変換して Monitor 用の `mem_total` に渡す。

## 値と判定

| 状態 | 処理 |
|---|---|
| 未設定 | `GPUSTAT_PCI` で選ばれた PCI device の `resource` を読み、各領域のサイズ `end - start + 1` の最大値を MiB に切り捨てて使う。読み取り失敗または不正な数値なら `0`。 |
| 空文字 | `os.environ.get()` が空文字を返し条件が偽になるため、未設定と同じ自動算出へ進む。 |
| 空でない文字列 | Python の `int()` で変換した整数をそのまま使う。正値かどうか、VRAM の実容量以内かなどの範囲検査や clamp はない。たとえば `0` は `0`、負数は負数として採用される。 |
| 整数に変換できない文字列 | `ValueError` が発生する。例外を捕捉するのは自動算出側だけなので、この指定値を使った起動では `TOTAL_MB` の初期化中に sampler が終了する。 |

## 有効になる条件

この変数を読むのは同梱の Intel xe telemetry sampler だけであり、通常の Strata engine の GPU メモリ確保量を変えない。sampler が `/run/gpustat.json` を出力し、Intel 用 server の `_XeGpu` がその JSON を読み込めた場合に、Web Monitor 用の総 VRAM 値へ反映される。sampler は `sycl/tools/gpustat.service` から起動する構成だが、service unit 自体はこの変数を設定していないため、値を指定する場合は sampler プロセスの環境に渡す必要がある。

## 実行時の詳細

`GPUSTAT_PCI` は `GPUSTAT_VRAM_MB` より先に評価され、空でない値、xe GPU の自動検出、最後の fallback `0000:00:00.0` の順で PCI address を決める。`vram_total_mb()` はこの PCI address の sysfs `resource` を参照する。

総量はモジュール読み込み時に `TOTAL_MB = vram_total_mb()` として一度だけ計算される。実行中の環境変数変更や BAR の変更を再読込しない。サンプルごとに `vram_total_mb` として JSON に出力するが、値自体は更新されない。`GPUSTAT_VRAM_MB=0` の場合、JSON には `0` が書かれ、server 側では byte 変換後の `0` を `or None` により `None` として扱う。負数の場合は server 側でも負数を byte 換算した値のまま渡す。

sampler が動作していない、JSON がない、または JSON の timestamp が15秒以上古い場合、`_XeGpu` は sampler データを採用しない。この場合、この変数で指定した総量も Monitor へ届かない。これは変数の値の無効判定ではなく、データ供給経路の条件である。

## 根拠

- `sycl/tools/gpustat.py:15-17` — sampler のヘッダーにある用途と既定値の説明。
- `sycl/tools/gpustat.py:37-48` — PCI address の決定、自動算出、例外時 `0` fallback、環境変数の読み取りと `int()` 変換。
- `sycl/tools/gpustat.py:64,157-160` — import 時の一度だけの算出と JSON 出力。
- `sycl/tools/gpustat.service:4-7` — sampler の起動コマンド。環境変数の設定はない。
- `sycl/serve/xe_telemetry.py:43-50,74-82` — JSON の鮮度確認と VRAM 値を byte 単位の Monitor データへ変換する処理。
- `docs/INTEL.md:407-414` — Intel Monitor の VRAM/load 表示が sampler の JSON に依存するという説明。
