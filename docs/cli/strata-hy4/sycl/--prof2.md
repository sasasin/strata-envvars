# `strata-hy4-sycl --prof2`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL runner） |
| オプション | `--prof2` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

prefill と通常の decode で、`Runner` 内の計測対象区間を SYCL event の開始時刻で測り、区間ごとの合計 GPU 時間と 1 step あたりの時間・呼び出し回数を stderr に出します。既定では無効です。実測には SYCL queue の profiling も必要なため、`HY4S_PROF=1` と併用します。

## 使い方

```sh
# SYCL queue の event profiling を有効にし、入力 token の prefill / decode を区間別に計測
HY4S_PROF=1 strata-hy4-sycl --model model.strata --tokens ids.txt --gen 16 --prof2
```

## 値と既定値

値は不要です。parser は `--prof2` を見つけると boolean を `true` にし、未指定時は `false` のままです。複数回指定しても同じ boolean を設定するだけです。フラグ自体に範囲検証はありません（`engine/src/hy4flash/sycl/sy_main.cpp:99,105-116,177-179`）。

## 実行時の動作

メイン処理は値を `Runner::prof2` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:283-292`）。区間の開始・終了時に空の `single_task` を投入し、その event の `command_start` の差をミリ秒へ変換してラベルごとに加算します。集計時は queue を待ち、合計値を step 数で割って表示し、各ラベルの累積値をクリアします（`engine/src/hy4flash/sycl/sy_graph.h:423-475`）。計測ラベルは attention、MLP、router、Engram、出力 head などのコード上で `PS` によって囲まれた区間です（例: `engine/src/hy4flash/sycl/sy_graph.h:951-985,1023-1039,1050-1063,1071-1085,1411,1463-1469`）。

prefill 終了時は chunk 数 `(T0 + Tc - 1) / Tc` で正規化した `[prof2 prefill]` レポートを出します（`engine/src/hy4flash/sycl/sy_main.cpp:344-371`）。非 speculative decode の経路では decode 後に `[prof2 decode]` を出します（`engine/src/hy4flash/sycl/sy_main.cpp:535-580`）。`--draft dfly2` で speculative decode に入る場合、その decode 分岐に `pacc_report` 呼び出しはありません。`--load-only` は Runner 初期化後に終了するため、prefill 計測レポートまで進みません（同 `:294-319`）。

## 適用条件と副作用

- profiling 対象 queue は、`HY4S_PROF` の値が `1` で始まる場合にのみ `enable_profiling` 付きで作られます（`engine/src/hy4flash/sycl/sy_common.h:154-175`）。`--prof2` はこの queue property を設定しません。profiling 無効時の event profiling 問い合わせは SYCL exception になり得て、main の catch は `SYCL exception: ...` を stderr に出して終了コード `4` を返します（`engine/src/hy4flash/sycl/sy_graph.h:452-456`, `engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。
- `prof2` が有効だと、通常の forward、head、DFly2 にある command graph 実行条件から外れ、個別の eager 処理経路を使います（`engine/src/hy4flash/sycl/sy_graph.h:1382-1392,1435-1460`, `engine/src/hy4flash/sycl/sy_dfly2.h:703-706,928-931`）。したがって、プロファイル結果は `--prof2` 無効時と同一の graph 実行条件での測定値ではありません。
- `--serve` でも parser はフラグを受理しますが、server 用 `ServeOpts` に `prof2` は渡されず、`Runner` にも設定されません。従って serve モードの計測フラグとしては機能しません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。
- `--prof` とは別の計測です。両方を指定すると両方のレポートが出る構造です（`engine/src/hy4flash/sycl/sy_main.cpp:177-178,290-291,369-371,577-580`; `engine/src/hy4flash/sycl/sy_graph.h:1426-1433`）。

## 出力とエラー

計測レポートは stderr に出力し、区間ごとに GPU ms/step と calls/step、最後に区間時間の合計を表示します（`engine/src/hy4flash/sycl/sy_graph.h:461-474`）。計測区間の marker task 投入、集計時の queue wait、profiling 情報の取得を伴います（同 `:436-459`）。profiling 情報取得で SYCL exception が発生した場合の表示と終了コードは前節のとおりです。

## 根拠

- parser・既定値・値を取らない設定: `engine/src/hy4flash/sycl/sy_main.cpp:99,105-116,177-179`
- `Runner` への設定と prefill/decode レポート箇所: `engine/src/hy4flash/sycl/sy_main.cpp:283-292,344-371,535-580`
- 区間 event の生成・集計・stderr 出力: `engine/src/hy4flash/sycl/sy_graph.h:423-475`
- profiling queue property と exception 経路: `engine/src/hy4flash/sycl/sy_common.h:154-175`, `engine/src/hy4flash/sycl/sy_main.cpp:612-615`
- command graph の無効化条件: `engine/src/hy4flash/sycl/sy_graph.h:1382-1392,1435-1460`, `engine/src/hy4flash/sycl/sy_dfly2.h:703-706,928-931`
