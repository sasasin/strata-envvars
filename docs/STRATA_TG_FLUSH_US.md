# `STRATA_TG_FLUSH_US`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（`2026-10-13` 時点）。

## 役割

トークングラフ実行中、GPU が次のレイヤーの doorbell を鳴らすのを CPU が待つ際に、実行キューを再確認する間隔をマイクロ秒で指定する。遅いレイヤーの待機中にキューの完了・エラーを検出するためのポーリング間隔であり、トークングラフ自体を有効化する設定ではない。

## 値と判定

| 環境変数の状態・値 | `flush_us` の値と処理 |
| --- | --- |
| 未設定 | `2000`（2,000 マイクロ秒） |
| 設定あり | `std::atoi` の戻り値を使用 |
| 空文字、または整数として先頭を変換できない文字列 | `0` |
| 整数の後ろに文字が続く文字列 | `atoi` が変換した先頭の整数を使用（例: `25ms` は `25`） |
| 負数 | 負の値をそのまま使用 |

文字列全体の検証、範囲チェック、clamp、無効値時の既定値への戻しはない。値は待機ループ内で `std::chrono::microseconds(flush_us)` と比較され、経過時間がその値を**超えた**ときに追加のキュー確認を行う。実際の確認はループの各反復ではなく、spin カウンターが 1024 回ごとの箇所に限られる。したがって `0` や負数はその確認箇所に来るたび条件を満たすが、指定値がそのまま一定周期のタイマーになるわけではない。

## 有効になる条件

SYCL の `strata generate` は、`--no-capture` がなく、`--no-token-graph` がなく、レイヤー単位または半精度の dump がなく、必要な hit 設定がそろい、native pack と multi-GPU split の経路でない場合にトークングラフを capture する。トークングラフが capture された場合、生成ループは `session_run_token` を呼ぶ。この関数でのみ当変数による待機間隔が適用される。条件を満たさず通常の `session_loop` などに進む場合、この設定は参照されない。

CUDA 側の `src/core/session.cpp` にも同じ読み取り・待機処理がある。ただし、この HEAD でリポジトリ内から `session_run_token` を呼んでいる箇所は `sycl/src/program/generate.cpp` の2箇所で、`src/program/generate.cpp` には呼び出しがない。CUDA 側の実装も存在するが、ここで確認した generate の呼び出し経路では利用されていない。

## 実行時の詳細

CUDA/SYCL それぞれの `session_run_token` 内で、関数ローカルの `static const int` として初回初期化時に一度だけ読み取る。同じ関数の後続呼び出しではキャッシュ値が使われるため、初回読み取り後に環境変数を変更しても反映されない。未設定かどうかは null 判定であり、空文字は「未設定」ではなく `atoi("") == 0` として扱う。

各レイヤーで CPU は GPU の doorbell 値を spin 待ちする。指定間隔を超えた確認時には flush カウンターを増やし、CUDA では `cudaStreamQuery`、SYCL では `ext_oneapi_empty()` を使ってキュー状態を調べる。GPU が対象レイヤーの doorbell を鳴らす前にグラフが終了した場合、関数は `session_run_token: layer <番号> never rang (graph finished)` をエラーにする。キュー確認でこの状態を検出できない場合でも、レイヤー待ちは別途20秒で timeout し、`session_run_token: timed out waiting for layer <番号>` を返す。この20秒 timeout は `STRATA_TG_FLUSH_US` の値では変わらない。generate の呼び出し元は失敗時にエラーを `stderr` へ出して終了コード1を返す。

## 根拠

- `src/core/session.cpp:912-952` — CUDA 実装。設定の読み取り、既定値、spin 待ち、キュー再確認、エラーと20秒 timeout。
- `sycl/src/core/session.cpp:1335-1407` — SYCL 実装。設定の読み取りから待機中の状態確認まで。SYCL では追加 flush に `ext_oneapi_empty()` を使う。
- `include/strata/core/session.hpp:399-409` — `TokenGraph` の状態と `flushes` カウンターの説明。
- `sycl/src/program/generate.cpp:5827-5835` — SYCL 側でトークングラフを capture する条件。
- `sycl/src/program/generate.cpp:11822-11833`, `12606-12614` — SYCL generate の両ループで、capture 済みなら `session_run_token`、そうでなければ `session_loop` を選ぶ。
- `src/program/generate.cpp:6169-6176` — CUDA generate 側の capture 条件。トークングラフの実行呼び出しは同ファイル内にない。
- `docs/DETAILS.md` — `STRATA_TG_FLUSH_US` およびトークングラフのこの待機間隔についての説明は見つからなかった。
