# `DS4_CPU_SMT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Windows上のDS4エンジンで、CPU laneのworker配置に物理コアごとの先頭logical CPUだけを使う既定動作を切り替え、SMT siblingも配置候補に含めます。結果としてCPU laneのpoolが使えるCPU数と、既定時のworker数が変わり得ます。これはCPU配置・並列度の設定で、環境変数自体がモデル計算式を切り替える処理はありません。

## 値と判定

`src/dsv41/ds4_model.cu` のWindowsビルドでのみ読み取られます。`std::atoi` の結果が0以外ならSMTを含め、0なら含めません。文字列全体の検証はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（物理コアごとの先頭logical CPUのみ） |
| 空文字 | `atoi("") == 0` のため無効 |
| `0`、`00`、数字で始まらない文字列 | 変換結果が0のため無効 |
| `1`、`2`、`-1`、`1tail` | 変換結果が0以外のため有効。後ろの文字列は検査しない |

`atoi` による変換なので、先頭空白や符号を含む数値の接頭部も変換されます。`true` / `false` の文字列比較や、1との完全一致は行いません。

## 有効になる条件

- Windows向けビルドのDS4エンジンで、`node_cores()` が呼ばれた場合にだけ値を参照します。Linux側は`/sys/devices/system/node/.../cpulist`と各CPUの`thread_siblings_list`を読み、各sibling群の先頭CPUだけを追加する実装で、`DS4_CPU_SMT`を読みません。
- WindowsではOSのNUMA node情報とprocessor core情報の両方が取得できる必要があります。取得に失敗してCPU一覧が空の場合は、共通fallbackが`hardware_concurrency()/2`相当のCPU番号を使うため、環境変数によるsibling追加はそのfallbackには反映されません。
- Windows側の列挙はprocessor group 0のみを扱い、CPU番号0〜63の範囲に限られます。SMT有効時も、各coreのprocessor group 0のmask内にあるlogical CPUだけが候補になります。
- `--cpu-threads` が正数なら、poolのworker数はNUMA分割とその指定で制限されます。`STRATA_DS4_LANE_FREE` が有効になる条件では、先頭poolから空けるCPU数もworker数に影響します。

## 実行時の詳細

Windowsでは`node_cores()`内の関数static変数として判定結果を初期化します。最初の`node_cores()`呼び出し時に一度評価され、そのプロセスで以後の環境変数変更は再評価されません。DS4モデルのロード経路では、この関数で得た一覧をCPU laneの`cores`として保持し、その後poolを作ります。

`os::node_cores(smt)`は各NUMA nodeについて、通常はcore maskの最小CPU番号だけを追加します。`smt`がtrueなら同じcore mask内のそれより大きいCPU番号も追加し、最後に一覧をソートします。得られた一覧を`make_pools()`がNUMAごとに分けてPoolへ渡し、初期worker数をCPU一覧の長さから決めます。CPU一覧が増えると、`--cpu-threads`等で制限されない範囲でpool workerを増やせます。CPU laneはexpert処理の仕事をworkerとpool呼び出し元で分担するため、一覧の増加はその並列実行資源に反映されます。

`-v` / verbose時にはpool生成後に`ds4: CPU lane: %d threads, MXFP4 rows %s (%s)`をstderrに出します。変数専用の警告やログはありません。

## 根拠

- `src/dsv41/ds4_model.cu:117-145`: Windowsでの環境変数判定、Linuxでの物理core列挙、空一覧時のfallback。
- `src/dsv41/ds4_os.hpp:466-485,488-531`: CPU pinningとWindows NUMA/core mask列挙。SMT有効時は同一core maskの追加logical CPUも列挙。
- `src/dsv41/ds4_model.cu:2665-2670,2788-2792,4832-4870`: CPU一覧の取得、CPU lane用poolへのCPU一覧の引き渡し・worker数決定、service threadのpinning、およびverboseログ。
