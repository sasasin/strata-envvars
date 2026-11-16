# `STRATA_PREFILL_TIMING`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

prompt の prefill 処理中に GPU stream 上の phase mark を記録し、phase ごとの GPU timeline と host 側の所要時間を stderr に出す診断用スイッチである。CUDA/HIP 実装では通常の `Prefill::run_impl` と layer-major 経路、SYCL 実装では `Prefill::run_impl` に `PfTimer` があり、multi-GPU peer がある場合は `PeTimer` も作られる（`src/prefill/prefill.cpp:3785-3822,4086-4088,7403-7432,7881,8909-8921`; `sycl/src/prefill/prefill.cpp:2353-2409,2413-2455,2538-2540,5247-5286`）。

環境変数は計測イベントと集計ログの有効・無効を切り替える。モデルや生成 token を選ぶ分岐には使われず、CLI 引数や別の環境変数によるこのスイッチの上書きもない。イベント記録自体の実行コストはあり得るため、計測あり・なしの実行時間を同一条件の値として扱う設定ではない。

## 値と判定

両 backend とも `std::getenv("STRATA_PREFILL_TIMING") != nullptr` の真偽だけを使う。値の文字列を変換・比較しないため、空文字も設定済みとして有効であり、`0`、`false`、`off`、`1` はいずれも有効になる。大文字小文字、空白、数値としての妥当性、境界値は判定に影響しない（`src/prefill/prefill.cpp:3785-3787,3826-3828`; `sycl/src/prefill/prefill.cpp:2353-2355,2413-2415`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP または SYCL の prefill timer | 計測しない | 空文字、`0`、`false`、`1`、任意の文字列 | なし（環境変数が存在する限り有効） |

## 有効になる条件

- 対象バイナリに該当 backend の Strata prefill 実装が含まれ、prompt 処理が `Prefill::run_impl` または（CUDA/HIP の）`run_layer_major` に到達する必要がある。変数は prefill timer の生成時に読む。CUDA/HIP の multi-GPU peer 集計は peer prefill が存在するときだけ行う（`src/prefill/prefill.cpp:4086-4088,7817,7881`; `sycl/src/prefill/prefill.cpp:2538-2540`）。
- layer-major は別の prefill 経路であり、この変数がその経路を選ぶわけではない。経路の選択・適用条件が満たされない場合も通常の prefill timer は動作する（`src/prefill/prefill.cpp:8991-9026`）。
- `STRATA_PREFILL_SYNC` は SYCL 実装で別途読み取られ、各 mark で queue を待って sync 診断行を出す設定である。`STRATA_PREFILL_TIMING` の有効条件や判定値には影響しない（`sycl/src/prefill/prefill.cpp:2353-2362,2363-2381`）。
- OS、CLI オプション、モデル形状、設定ファイルによる値の上書き・追加条件は、対象名の読み取り経路にはない。

## 実行時の詳細

`PfTimer` は prompt 処理のローカル変数として作られ、その初期化時に環境変数の有無を読み込む。CUDA/HIP の `run_impl` と `run_layer_major`、SYCL の `run_impl` では、それぞれの呼び出しで新しい timer が環境を評価する。したがって実行中の同じ prefill 呼び出しでは `on` は固定だが、プロセス環境を変更した場合は後続の prefill 呼び出しで再評価される（`src/prefill/prefill.cpp:3785-3787,4086-4088,7881`; `sycl/src/prefill/prefill.cpp:2353-2355,2538-2540`）。

有効時、CUDA/HIP は compute stream に CUDA event を記録し、SYCL は queue に event barrier を記録する。隣接 mark 間の経過時間を先行する mark の phase に加算し、MoE layer の host sync 後などに fold する。CUDA/HIP では同じ phase の連続 mark を省略して event record 数を抑える（`src/prefill/prefill.cpp:3791-3817`; `include/strata/prefill/timer_marks.hpp:15-18`; `sycl/src/prefill/prefill.cpp:2363-2382,2383-2405`）。

有効時、SYCL の各 chunk 開始時には `strata prefill timing: setup ...` の内訳も出す。正常終了時は phase ごとの正の時間をまとめ、GPU timeline 合計、wall time、host staging、および host 側の chunk setup / 待ち / 後処理時間を出す。peer timer が有効な場合は peer GPU の集計も出す。layer-major 経路では phase 別 GPU timeline の行を出す（`src/prefill/prefill.cpp:7403-7432,8909-8921`; `sycl/src/prefill/prefill.cpp:2613-2619,5247-5286`）。

early return や失敗で処理末尾に達しない場合、末尾の集計行は実行されない。SYCL の `PfTimer::fold` は profiling 情報取得中の `sycl::exception` を stderr に表示して `exit(1)` する（`sycl/src/prefill/prefill.cpp:2383-2405,5247-5262`）。

## ログと測定値

CUDA/HIP および SYCL の標準的な集計行は `strata prefill timing: ...`、peer 用は `strata prefill timing (peer GPU, ms):...` で、いずれも `stderr` に出る。host 内訳は `strata prefill timing: host: chunk setup (PLE rows, the expert stream plan) ...` から始まる。SYCL では chunk ごとに `strata prefill timing: setup %s %.1f ms` 形式の行も出る。layer-major では `strata prefill timing (layer-major): ...` が出る（`src/prefill/prefill.cpp:7403-7432,8920-8921`; `sycl/src/prefill/prefill.cpp:2613-2619,5258-5286`）。通常の sync/warning/error をこの変数が直接出す実装はない。SYCL の計測 fold 失敗時の例外表示と終了は上記のとおり。

`docs/OLDER_GPUS.md:281` は `STRATA_PREFILL_TIMING=1` を profiling switch の使用例として挙げる。ソースでは値 `1` を特別扱いせず、設定有無だけで計測するため、資料の例は有効化方法としては正しいが、有効値が `1` に限定されるわけではない。性能値はこの調査では測定していない。

## 根拠

- `src/prefill/prefill.cpp:3773-3822` — CUDA/HIP の phase 名、環境判定、event 記録・fold。
- `src/prefill/prefill.cpp:4086-4089,5693-5696,7403-7432` — timer の生成、layer sync での集計、正常終了時の stderr 出力。
- `src/prefill/prefill.cpp:7817-7824,7881,8909-8921` — layer-major 経路の timer と出力。
- `sycl/src/prefill/prefill.cpp:2342-2409,2410-2455` — SYCL の環境判定、phase event、peer timer、fold 時の失敗処理。
- `sycl/src/prefill/prefill.cpp:2538-2541,5247-5286` — timer の生成と正常終了時の stderr 出力。
- `include/strata/prefill/timer_marks.hpp:15-18` — CUDA/HIP 側で連続する同一 phase mark を省略する条件。
- `src/prefill/prefill.cpp:8991-9026` — layer-major の選択が別条件によること。
- `docs/OLDER_GPUS.md:281` — `=1` を用いる profiling switch の資料上の例。
