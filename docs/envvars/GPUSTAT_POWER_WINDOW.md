# `GPUSTAT_POWER_WINDOW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata 同梱の Intel Arc `xe` 用テレメトリサンプラー `sycl/tools/gpustat.py` が、GPU と package の電力を energy counter の差分から計算するときに使う保持時間（秒）です。サンプラーは `/run/gpustat.json` を書き、Intel SYCL サーバーの Monitor 用テレメトリ reader がその値を読みます。この変数は Strata の推論計算や電力上限を制御するものではありません。

`GPUSTAT_POWER_WINDOW` の全参照は、同ファイルの環境変数読み取り（65 行）と説明文字列（15 行）です。動的な名前渡しや共通 env helper を介した参照はありません。

## 値と判定

| 環境の状態 | 結果 |
|---|---|
| 未設定 | `15` を `float()` で変換して使用 |
| 設定あり | 値全体を Python の `float()` で変換。整数・小数・符号・指数表記など、`float()` が受け付ける数値文字列を使用 |
| 空文字、空白のみ、数値でない文字列 | `float()` が `ValueError` を送出。モジュール初期化が失敗し、サンプラーのループは始まらない |
| 負数または 0 | 範囲検査・clamp はない。保持リングを最大 2 サンプルに縮めるため、実質的に窓を指定値どおりの正の秒数にはできない |
| `nan` / `inf` など | `float()` は有限値かを検査しない。`nan` と正の `inf` ではリング削除条件が成立せず、起動後のサンプルが保持され続ける |

環境変数は `gpustat.py` の import 時に一度評価され、`POWER_WINDOW` に格納されます。実行中の環境変更を再読込する処理はありません。CLI 引数や別変数による上書きもありません。サンプラーを systemd unit で起動した場合、空文字や不正値による起動失敗は `Restart=always` と `RestartSec=5` により systemd が 5 秒後に再起動を試みます。Python の例外 traceback は標準エラーに出ます（unit は出力先を別途指定していません）。

## 有効になる条件

- Linux 上で、同梱 `sycl/tools/gpustat.py` を直接実行するか、`sycl/tools/gpustat.service` としてインストール・起動していること。unit は `/usr/local/sbin/gpustat.py` を実行し、常時再起動を設定します。
- 通常の Strata Monitor 経路では、SYCL Intel サーバーが Intel Arc を選んで `_XeGpu` reader を使い、サンプラーが書いた `/run/gpustat.json` が 15 秒以内のデータであること。`server_intel.py` は Intel reader が使えない場合、共通 telemetry reader に戻します。
- 推論の CLI 引数、モデル状態、ビルド macro による有効化条件はありません。GPUSTAT サンプラーは独立した同梱ツールです。

サンプラーがない場合や JSON がない・古い場合、Monitor の `_XeGpu.read()` は JSON 由来の電力を使いません。hwmon `energy1_input` の直近差分から電力を求める別経路があり、こちらは `GPUSTAT_POWER_WINDOW` を読みません。したがってサンプラーが停止していても、sysfs が読めれば電力表示自体は得られる場合があります。

## 実行時の詳細

サンプラーはデフォルトで 3 秒ごとに hwmon の `energy1_input`（card）と `energy2_input`（package）を読みます。各サンプルを `(時刻, card energy, package energy)` として deque に追加し、リングに 2 件より多く残っている間、2 番目に古いサンプルが `POWER_WINDOW` 秒以上前なら先頭を削除します。最低 2 件は保持します。現在値と最古保持値の差分を経過秒数で割り、J/s（W）に換算します。経過時間が 2.5 秒未満、または energy counter が減少した場合、対応する電力値を `None` にします。結果は `power_w` と `pkg_power_w` として JSON に書かれます。

既定値 15 秒では、サンプル間隔に応じた直近約 15 秒の energy 差分が平均対象になります。0 以下ではリングが 2 件まで縮みます。`nan`/`inf` は比較により削除が起こらず、平均区間がサンプラー起動から伸びます。これらの値について、コードに警告や fallback はありません。

SYCL サーバーは `sycl/serve/server_intel.py` で Intel GPU reader を登録します。reader は `/run/gpustat.json` を読み、タイムスタンプの経過が 15 秒未満の場合に `power_w` を Monitor 用の `power` に移します。値が `None` なら sysfs の energy 差分へ fallback します。Monitor の GPU 履歴は共通 telemetry のサンプリングスレッドで読み取られます。

## 根拠

- `sycl/tools/gpustat.py:15,65`: 変数の説明と `float(os.environ.get(..., "15"))` による読み取り。
- `sycl/tools/gpustat.py:128-151,175-179`: 起動後のサンプル処理、リング窓の判定、2.5 秒条件・energy 差分による計算、JSON 出力間隔。
- `sycl/tools/gpustat.service:4-7`: root サンプラーの起動先、常時再起動と 5 秒の再起動間隔。
- `sycl/serve/server_intel.py:37-47`: Intel GPU がある場合に SYCL サーバーの reader を差し替える処理。
- `sycl/serve/xe_telemetry.py:25,57-64,88-115`: JSON の読み取りと鮮度判定、power の転送、sysfs からの fallback。
- `serve/telemetry.py:600-619`: GPU reader の継続的な読み取りと GPU 履歴への power の格納。
- `docs/INTEL.md:159-162`: Monitor と root サンプラーの説明。窓幅の値判定・計算は説明されていない。
