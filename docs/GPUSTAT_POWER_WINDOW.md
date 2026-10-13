# `GPUSTAT_POWER_WINDOW`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Strata 同梱の Intel Arc 用テレメトリ sampler `sycl/tools/gpustat.py` が、カードとパッケージの消費電力を energy counter の差分から計算するときに使う時間窓（秒）です。GPU エンジンの計算動作を変える設定ではありません。sampler が `/run/gpustat.json` に書く `power_w` と `pkg_power_w` の平滑化期間を変え、Intel 向け Monitor 表示に間接的に影響します。

## 値と判定

モジュール読み込み時に `float(os.environ.get("GPUSTAT_POWER_WINDOW", "15"))` で一度変換されます。環境変数が未設定なら既定値は `15.0` 秒です。空文字や `float()` が解釈できない文字列では変換例外となり、sampler は起動時に失敗します。空白付き数値や Python の `float()` が受け付ける数値表記もそのまま変換されます。正数に限定する検査、clamp、無効値の fallback はありません。

| 設定 | sampler での扱い |
|---|---|
| 未設定 | `15.0` 秒を使用 |
| 正の有限数 | deque の古い energy counter 標本を、窓の範囲に保つように削除 |
| `0` または負数 | 各周回で古い標本を繰り返し削除して deque に 2 件だけ残し、実質的に直近の標本間の差分を使う |
| `nan` | 比較が偽になるため標本を窓によって削除しない |
| `inf` / `Infinity` | 標本を削除しない |
| 空文字・数値でない文字列 | `float()` が `ValueError` を送出し、sampler の初期化に失敗 |

値は大文字小文字を区別する文字列比較ではなく Python の `float()` に渡されます。`nan`/`inf` は float として受理されますが、通常の有限な時間窓の意味にはなりません。

## 有効になる条件

この変数を読むのは `sycl/tools/gpustat.py` だけです。Strata 本体の engine や一般の CUDA/HIP 経路で読み取る箇所はありません。実際に効果があるのは、この sampler を起動した場合です。同梱の `gpustat.service` は `/usr/local/sbin/gpustat.py` を実行し、常駐 sampler として起動する設定です。環境変数を変えて反映するには sampler プロセスを再起動する必要があります。

Monitor への表示は Linux Intel Arc の経路です。`sycl/serve/xe_telemetry.py` は `/run/gpustat.json` の鮮度が15秒未満なら `power_w` を読み、値が `None` の場合は sysfs energy counter から別途電力を計算します。この fallback は sampler の `GPUSTAT_POWER_WINDOW` を使いません。

## 実行時の詳細

sampler は各ループで `(時刻, card energy, package energy)` を deque に追加します。2件より多くあり、2番目に古い標本が現在から `POWER_WINDOW` 秒以上古ければ、最古の標本を削除します。残った最古の標本と現在値から経過秒数 `span` と energy 差分を求め、`span >= 2.5` かつ counter が減っていない場合だけ差分をワットへ換算します。カードとパッケージの値をそれぞれ `power_w`、`pkg_power_w` として小数1桁に丸めて JSON に保存し、条件を満たさない場合は `null` を保存します。したがって 2.5 秒未満の窓を指定しても、2.5 秒未満の値が出るわけではなく、標本間隔によっては `null` が続く場合があります。

窓はサンプル周期 `GPUSTAT_INTERVAL` と deque の保持規則に依存するため、指定秒数ちょうどの固定長移動平均ではありません。ファイル先頭の説明では、energy counter の更新がまとまって行われるため、既定の3秒サンプルで短い差分を取ると値が大きく振れることがあり、電力計算に `POWER_WINDOW` を使うと説明しています。

## 根拠

- `sycl/tools/gpustat.py:7-8,15-17` — power 値の説明と sampler が認識する環境変数。
- `sycl/tools/gpustat.py:65` — `float()` による読み取りと既定値15秒。
- `sycl/tools/gpustat.py:133-151` — energy 標本の保持、窓による削除、2.5秒以上の差分計算条件。
- `sycl/tools/gpustat.py:158-164,175-179` — 計算値の JSON 保存とループ周期。
- `sycl/tools/gpustat.service:4-9` — sampler の常駐起動設定。
- `sycl/serve/xe_telemetry.py:43-50,74-97` — JSON 標本の鮮度確認、`power_w` の読み取りと sysfs fallback。
- `docs/INTEL.md:407-414` — Intel Monitor と sampler の関係。
