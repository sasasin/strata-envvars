# `STRATA_IO_PF_SCHED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux の file tier I/O prefetch にある、予測読み込み用ジョブのスケジューリングを有効にします。通常の prefetch は予測された expert をキューに入れます。有効時は lookahead predictor の confidence と対象 layer までの距離を受け取り、confidence による採用判定、decode window ごとの読み込み byte 予算、layer 到達期限を使って予測ジョブを選びます。レイヤー自身が要求する読み込みは、予測ジョブより先に処理されます。

これは prefetch のスケジュールだけを変えます。この変数単独で I/O prefetch を開始するものではありません。

## 値と判定

`FileExpertSource::set_io_prefetch()` が呼ばれたときに `std::atoi()` で判定し、戻り値が 0 以外なら有効です。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数値に変換できない文字列 | 無効（`atoi` が 0 を返す） |
| 数値部分の変換結果が 0 | 無効（例: `0`, `0suffix`） |
| 数値部分の変換結果が 0 以外 | 有効（例: `1`, `-1`, `2suffix`） |

文字列全体の一致や `1` との比較はしません。`atoi` は先頭の空白と符号を許し、数値の後ろの文字を判定に使いません。値は prefetch のセットアップ時にメンバー `io_sched_` に保存され、そのセットアップ中に再読込されません。

## 有効になる条件

- Linux の file tier で `set_io_prefetch()` が進み、mapped file のパスを開けること。Windows ではこの関数の Linux 専用処理は実行されません。
- I/O prefetch 自体が有効であること。`STRATA_IO_PREFETCH` が非 0、または Linux file tier の既定条件により `src.linux_io_defaults()` が成立して、呼び出し元が `set_io_prefetch(true, ...)` を呼ぶ必要があります。
- source が unbuffered (`direct_` が空でない) ではないこと。`set_io_prefetch()` はその場合に戻り、スケジューラ設定も読みません。
- 予測読み込みが許可されていること。`STRATA_IO_PF_AHEAD=0` なら worker の予測キューへ読み込みを追加しません。decode gate が閉じている間も `warm_scored()` は通常の `warm()` にフォールバックし、gate が開いていないため I/O worker に読み込みを追加しません。

`STRATA_IO_PREFETCH` 自体の既定条件や decode gate の判定は別変数の実装によります。`STRATA_IO_PF_SCHED=1` だけでは、それらの条件を上書きしません。

## 実行時の詳細

`io_sched_` と I/O prefetch がともに有効なら lookahead predictor はスコアを要求します。スコアは expert ごとの router rank に基づき、上位ほど大きく、次 layer より先の予測ほど小さくなります。同じ expert が複数 token から予測された場合は最大 confidence が使われます。予測ジョブの期限は現在の layer clock に予測距離を加えた値です。

`warm_scored()` は resident RAM にある expert を除き、confidence 下限とキュー圧力、window byte 予算を確認します。既定の confidence 下限は `0.5`、budget fraction は `0.5` です。固定 budget が指定されない場合、読み込み速度と window 時間がまだ測定できていない間は 256 MiB、その後は worker の測定読み込み速度・worker 数・window 時間・budget fraction・feedback scale から予算を計算します。キューが混むほど confidence 下限が上がり、予算を超える候補は採用されません。これらの基準値は `STRATA_IO_PF_MINCONF`、`STRATA_IO_PF_BUDGET_MB`、`STRATA_IO_PF_BUDGET_FRAC`、`STRATA_IO_PF_TARGET` で調整されます。

worker は layer 自身の demand read キューが空のときに予測ジョブを処理します。期限切れジョブは破棄され、期限が近いものを優先し、同じ期限なら confidence が高いものを先にします。decode window ごとに budget 使用量をリセットし、予測 byte のうち実際の demand より前に使われた割合に応じて後続 window の自動 budget を縮小・回復します。

prefetch が実際に有効で、スケジューラも有効な場合、stderr に `strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): ...` が出ます。request ごとの I/O ログには予測読み込み byte、利用された byte、late 件数、confidence で不採用になった件数、budget 超過件数、window budget が表示されます。スケジューラの設定を読んでも、prefetch が利用できない経路ではこの ON ログは出ません。

## 根拠

- `src/core/expert_source.cpp:1114-1161` — Linux mapped file の確認、変数読み取り、`atoi` 判定、スケジューラ worker の起動。
- `src/core/expert_source.cpp:1045-1076,1081-1112` — 自動 byte budget、window feedback、confidence と budget による候補採用。
- `src/core/expert_source.cpp:1201-1243` — demand read 優先、期限切れの破棄、期限と confidence による worker の選択。
- `src/core/expert_source.cpp:3276-3291` — layer clock と decode window の更新。
- `include/strata/core/expert_source.hpp:280-286,924-930,1146-1165` — scored prefetch の API、適用条件、既定値。
- `src/program/generate.cpp:5655-5690,15413-15438` — prefetch の有効化、スケジューラ ON ログ、request ごとの観測ログ。
- `docs/DETAILS.md:272-306` は Linux file tier prefetch の基本と測定を説明しますが、この scheduler の有効化フラグや性能測定値は記載していません。そのため本書では `STRATA_IO_PF_SCHED` 固有の性能効果を主張しません。
