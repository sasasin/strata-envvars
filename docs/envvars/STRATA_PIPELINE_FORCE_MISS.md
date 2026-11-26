# `STRATA_PIPELINE_FORCE_MISS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン decode の MTP 予測窓を意図的に不一致にし、検証後の rollback 経路を通す診断用設定です。正の値 `k` では、MTP chain から作る B 窓のうち `k` 回目ごとに先頭予測 token を必ず別の値 (`0` と `1` の間) に差し替えます。生成 token の設定や、通常の MTP 予測方式を変更する設定ではありません。窓が実際に投機実行され、検証される条件を満たしたときに rollback が起きます。CUDA/HIP 実装は `engine/src/program/generate.cpp`、SYCL 実装は `engine/sycl/src/program/generate.cpp` にあります。読み取り箇所は各 backend に 1 箇所です。(`engine/src/program/generate.cpp:20280-20283,21967-21984`; `engine/sycl/src/program/generate.cpp:11159-11162,11939-11955`)

## 値と判定

helper `pipe_dbg_env()` が `STRATA_PIPELINE_DEBUG` を有効と判定した場合に限り、対象変数を `getenv` で読み、C の `atoi` で変換してから `max(0, 値)` を取ります。したがって文字列全体の厳密な数値検査はなく、`atoi` が読む先頭の整数部分だけが使われます。空文字や整数として読めない文字列は `0`、先頭空白や符号の後の整数は変換され、数値の後ろの文字は無視されます。負数は `0` に丸められます。`atoi` の整数範囲外入力はコードで検査されず、動作を保証できません。(`engine/src/program/generate.cpp:684-687,20280-20283`; `engine/sycl/src/program/generate.cpp:337-340,11159-11162`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_PIPELINE_DEBUG` が有効 | `0` | `1`, `2`, `+3`, ` 4`, `2anything` はそれぞれ正の間隔 | ``, `0`, `0anything`, `true`, `-1`, `-2` は `0` |
| `STRATA_PIPELINE_DEBUG` が無効 | `0` と同じ | なし。helper が対象名を読まず `nullptr` を返す | 設定値にかかわらず無効 |

`STRATA_PIPELINE_DEBUG` 自体は helper 内の関数 static `bool` として最初の helper 呼び出し時に一度評価されます。未設定・空文字・先頭文字が `0` の値は無効、それ以外（例: `false`）は有効です。したがって最初の評価後にこの gate をプロセス内で変更しても反映されません。対象値は request の prompt-read 設定時に `pl_force_miss` へ読み込まれます。さらに gate が有効で `STRATA_PIPELINE_SWITCH` のファイルを開けた場合、その内容の `force_miss=<k>` が環境変数の値を上書きします。(`engine/src/program/generate.cpp:684-687,20280-20302`; `engine/sycl/src/program/generate.cpp:337-340,11159-11174`)

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。無効なら対象変数は読み取られず、既定値 `0` です。(`engine/src/program/generate.cpp:681-686`; `engine/sycl/src/program/generate.cpp:325-339`)
- layer split が別 GPU 上の 2 段以上で有効になり、`pipe` が成立すること。decode のパイプライン窓は `--pipeline-windows 2` 相当 (`pl_pw >= 2`) かつ snapshot の準備が成功した場合にだけ実行されます。(`engine/src/program/generate.cpp:13256-13267,21802-21822`; SYCL は `engine/sycl/src/program/generate.cpp:11775-11795`)
- request が decode パイプラインへ進み、キャンセルされておらず生成上限にも達していないこと。さらに `penalty_last_n` による履歴反復ペナルティがなく、draft が coupled sampling でない必要があります。条件を満たさない request は serial decode になります。(`engine/src/program/generate.cpp:21811-21822`; SYCL は `engine/sycl/src/program/generate.cpp:11783-11795`)
- MTP chain から B 窓が作られること。正の値でも B 窓が作られない場合や、gate が投機 launch を止めた場合には forced mismatch の rollback は発生しません。(`engine/src/program/generate.cpp:21967-21984,22321-22330`; SYCL は `engine/sycl/src/program/generate.cpp:11939-11955`)
- SYCL では別の診断設定 `STRATA_PRIVATE_MTP_DEMAND=1` の計測経路が `force_miss == 0` を条件に含みます。この変数が正である間、その private demand 計測は有効になりません。(`engine/sycl/src/program/generate.cpp:12132-12135`)

## 実行時の詳細

`pl_force_miss` は request の prompt-read 準備箇所で初期化され、decode loop に値渡しされます。プロセス実行中に対象環境変数を書き換えても、その request の読み込み済み値は変わりません。`STRATA_PIPELINE_SWITCH` が gate 有効時に開けた場合は、request ごとに読んだファイル内の `force_miss=` が先に読み込まれた値を置き換えます。CLI の `--pipeline-windows` は強制不一致の数値を指定しませんが、decode pipeline 自体を成立させる条件です。(`engine/src/program/generate.cpp:20245-20302,21850-21853`; SYCL は `engine/sycl/src/program/generate.cpp:11151-11174,11812-11817`)

CUDA/HIP では MTP chain から B を作るたびにローカルカウンター `pl_fm` を増やし、`pl_fm % force_miss == 0` の場合 `B.tok[0]` を `0` なら `1`、それ以外なら `0` にします。SYCL も同じ差し替えを行います。これは drafter の確率や通常の出力 token を書き換える処理ではなく、stage 0 が先行実行する speculative B の入力だけを不一致にします。(`engine/src/program/generate.cpp:21896,21967-21984`; `engine/sycl/src/program/generate.cpp:11877,11939-11955`)

不一致の窓が止まると、CUDA/HIP はその窓が通った front stage の GDN snapshot と状態を復元し、直前の正しい窓を実際の commit 数で再 commit して `pl_undo` を増やします。SYCL も snapshot と `ple_prev` を戻して正しい commit を再実行します。通常の不一致検証・rollback 経路を使うため、変数単独でエラー終了させる分岐はありません。(`engine/src/program/generate.cpp:22169-22189`; `engine/sycl/src/program/generate.cpp:12165-12183`)

## ログと測定値

環境変数を読み取っただけでは専用ログは出ません。`STRATA_PIPELINE_SWITCH` が設定され、そのファイルを開けた場合は stderr に `strata pipeline switch: ... force_miss=<値> ...` を出します。decode timing が有効な場合 (`STRATA_DECODE_TIMING` が設定されている場合) は stderr の `strata pipeline:` 集計に rollback 数 (`rolled back`) が含まれますが、個々の rollback をこの環境変数名付きで記録するログではありません。(`engine/src/program/generate.cpp:20284-20302,21778-21780,22588-22599`; SYCL の switch ログは `engine/sycl/src/program/generate.cpp:11163-11174`)

`docs/DETAILS.md` にこの変数固有の測定値や説明はありません。`docs/MULTI_GPU.md:203` は `STRATA_PIPELINE_*` の調整・テスト変数が `STRATA_PIPELINE_DEBUG=1` の場合だけ読まれる旨を記しています。これは helper の実装と整合しますが、値の変換や rollback の詳細はソース実装に基づきます。

## 根拠

- `engine/src/program/generate.cpp:681-687` — debug gate と読み取り helper。
- `engine/src/program/generate.cpp:20245-20302` — pipeline の request 設定、対象値の parse、switch ファイルによる上書きとログ。
- `engine/src/program/generate.cpp:13256-13267,21802-21822` — pipeline/backend 構成と decode 適用条件。
- `engine/src/program/generate.cpp:21896,21967-21984,22169-22189` — カウンター、forced mismatch、snapshot 復元と rollback。
- `engine/src/program/generate.cpp:22430-22442,22588-22599` — 不一致の判定と rollback 集計ログ。
- `engine/sycl/src/program/generate.cpp:325-340,11151-11174,11775-11795,11877,11939-11955,12132-12135,12165-12183` — SYCL 側の対応実装と private demand 条件。
