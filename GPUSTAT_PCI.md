# `GPUSTAT_PCI`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata 同梱の Intel Arc / xe 向け telemetry sampler `sycl/tools/gpustat.py` が、監視対象となる GPU の PCI BDF アドレス（例: `0000:03:00.0`）を選ぶために使います。Strata の推論エンジンはこの名前を読まず、エンジンの計算やメモリ確保を変えません。サンプラが選んだ GPU の状態を `/run/gpustat.json` に出力し、Intel 向け Monitor tab が利用します。

## 値と判定

| 状態 | 選択される `PCI` |
|---|---|
| 未設定 | `find_card()` が見つけた最初の Intel GPU（xe） |
| 空文字 `""` | 同上。`or` による fallback |
| 空でない任意の文字列 | その文字列をそのまま使う |
| 自動検出にも失敗 | `0000:00:00.0` |

値の trim、大小文字変換、BDF 形式の検証、数値変換はありません。したがって空白だけの値も truthy な文字列として採用され、正規化されずに各パスや `lspci -s` に渡されます。自動検出は `/sys/class/drm/card[0-9]*/device` をソート順に調べ、`vendor` が `0x8086` かつ `tile*/gt*` が存在する最初のデバイスの realpath basename を返します。該当デバイスがない場合に限り、最後の既定値 `0000:00:00.0` が使われます。

## 有効になる条件

- `sycl/tools/gpustat.py` を実行した場合だけ有効です。同梱 service は `/usr/local/sbin/gpustat.py` を起動します。service unit 自体には `Environment=` 指定がないため、設定する場合はサンプラプロセスの起動環境に渡す必要があります。
- Linux の Intel xe sysfs レイアウトを前提としたツールです。通常の Strata engine や `sycl/serve/xe_telemetry.py` は `GPUSTAT_PCI` を直接読みません。
- `GPUSTAT_VRAM_MB` が truthy な場合、PCI デバイスの `resource` ファイルから VRAM 総量を算出する処理は省略されます。ただし `PCI` はカード名取得、デバイス ID、PCIe link、GPU 周波数の読み取り先に引き続き使われます。
- Intel サーバー側の `_XeGpu` は独自に最初の Intel GPU を選び、sampler JSON の `pci` フィールドとその選択先を照合しません。複数 GPU で `GPUSTAT_PCI` にサーバー側とは別のカードを指定すると、Monitor tab の sampler 由来 load / VRAM / 温度 / 電力が別カードの値になる可能性があります。`xe_telemetry.py` の sysfs 由来温度・電力・PCIe link は `_XeGpu` 側で選んだカードから読みます。

## 実行時の詳細

`PCI = os.environ.get("GPUSTAT_PCI") or find_card() or "0000:00:00.0"` はモジュール読み込み時に一度評価されます。プロセス起動後の環境変更は反映されません。選択したアドレスは次の用途に使われます。

- `vram_total_mb()` が `/sys/bus/pci/devices/<PCI>/resource` を読み、最大の BAR 幅を MiB にする（`GPUSTAT_VRAM_MB` が truthy ならこの読み取りをしない）。読み取り・parse で `OSError` / `ValueError` が起きた場合、総量は `0` になります。
- `/sys/bus/pci/devices/<PCI>/device` から device ID を取得し、既知 ID `e223` なら固定名を使います。それ以外は `lspci -mm -s <PCI>` でカード名を調べ、失敗時は `Intel GPU 8086:<device id>` に fallback します。
- PCIe link 情報を `/sys/bus/pci/devices/<PCI>` から取得します。30 秒ごとに再読込し、変化した link training を反映します。
- `/sys/bus/pci/devices/<PCI>/tile0/gt0/freq0/act_freq` から現在周波数を読みます。
- 出力 JSON の `pci` に選択値を記録し、`name`、link、frequency、その他の sampler 値と一緒に `/run/gpustat.json` へ書きます。

これ以外の telemetry（`/proc/*/fdinfo` の client VRAM / busy、xe hwmon の温度・電力など）はカード BDF で絞り込まず取得されます。実装は一つの選択 GPU を前提にしているため、複数 xe GPU 環境で全ての値が指定カードだけに属するとは限りません。コードに `GPUSTAT_PCI` 固有のログや警告はありません。サーバー側は JSON の `ts` が15秒未満なら sampler 値を利用しますが、BDF は照合しません。

## 資料との照合

`sycl/tools/gpustat.py` のヘッダーは、GPUSTAT_PCI がカードを指定し、既定では xe 上の最初の Intel GPU を選ぶと説明しています。`docs/INTEL.md` は Monitor tab の load / VRAM が root sampler の `/run/gpustat.json` から来ることを説明しています。値の空文字・未検証文字列の扱い、モジュール読み込み時の選択、JSON の PCI アドレスを server が照合しない点は資料では説明されておらず、コードから確認しました。測定値に関する記載はありません。

## 根拠

- `sycl/tools/gpustat.py:15-17`: 環境変数の概要と既定値の説明。
- `sycl/tools/gpustat.py:26-38`: `find_card()` の検出条件と import 時の優先順位。`GPUSTAT_PCI` の唯一の実読み取り箇所。
- `sycl/tools/gpustat.py:40-48,51-61`: VRAM BAR 読み取り、カード ID / 名称と `lspci`。
- `sycl/tools/gpustat.py:68-82,128-134,152-173,175-179`: PCIe link と周波数の参照、30秒ごとの link 再読込、JSON への出力および周期処理。
- `sycl/tools/gpustat.service:4-7`: service の起動環境に `GPUSTAT_PCI` の設定がないこと、および再起動設定。
- `sycl/serve/xe_telemetry.py:21-30,43-50,74-102`: server 側が別途最初の Intel GPU を選び、JSON を鮮度判定して利用する処理。
- `sycl/serve/server_intel.py:37-48`, `docs/INTEL.md:407-414`: xe telemetry reader の取り付け条件と Monitor tab の sampler 利用。
