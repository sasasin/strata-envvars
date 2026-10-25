# `--no-host-worker`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` で、調査開始時の作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数 parser） |
| オプション | `--no-host-worker` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

CPU expert pool の各処理フェーズで、GPU 側の処理を進行させるホストスレッド自身が expert の drain 作業も行う動作を止めます。既定ではホストスレッドも worker と同じ共有 queue から仕事を取ります。このフラグは、その既定構成との A/B 比較用として help に説明されています（`src/program/generate.cpp:1023-1025`）。

## 使い方

エンジンの通常引数とともに指定します。たとえば、token ID を使う実行では次のように指定できます。

```sh
strata --no-host-worker --tokens 1,2,3
```

`--tokens` は tokenizer を含まない build で必要な入力の例です。実際のモデルや実行条件に応じた他の engine 引数は別途指定してください。

## 値と既定値

- 値・引数は不要です。CPU parser はフラグを認識すると `no_host_worker = true` にします。既定値は `false` です（`src/program/generate.cpp:534`, `src/program/generate.cpp:2550`）。
- SYCL 側の parser も同じく値なしで受理し、既定値は `false` です（`sycl/src/program/generate.cpp:511`, `sycl/src/program/generate.cpp:1870`）。
- 同じフラグを複数回指定しても、いずれも同じ真値を設定するだけです。反対に戻す CLI フラグはこの parser にありません。
- このオプション固有の値 validation はありません。値を後置してもこのフラグの値にはなりません。後置値が別の引数として認識されなければ、未知引数として失敗します。

## 実行時の動作

CPU engine は `ExpertPool` に `host_works = !o.no_host_worker` を渡して pool を作ります。指定時はホストスレッドによる pool 仕事の drain を無効にします（`src/program/generate.cpp:5971-5974`）。SYCL engine でも同じ反転値を pool に渡します（`sycl/src/program/generate.cpp:4457`）。

pool は通常の worker とホストスレッドで同じ `head_` を使って仕事を取得する設計です。`host_works_` が真ならホスト側も queue を drain し、完了を待ちます。フラグ指定時はこのホスト側 drain を行わず、worker 群が仕事を処理します（`src/kernels/cpu/pool.cpp:1416-1435`, `src/kernels/cpu/pool.cpp:1280-1287`）。したがって、推論対象や出力形式を選ぶオプションではなく、CPU pool の仕事を実行するスレッド構成を変える指定です。

`--pool-workers` と組み合わせる場合も、このフラグは worker 数の設定を変更せず、ホスト参加だけを切り替えます。自動タスク数は `3 * (workers + host参加時の1)` で計算され、明示された `--pool-tasks` は同じ pool の task 数として使われます（`src/program/generate.cpp:5973-5978`, `src/kernels/cpu/pool.cpp:1300-1317`）。`--pool-affinity measure` を使う CPU build では、比較用 pool にもこのフラグの状態が渡されます（`src/program/generate.cpp:5971-5974`, `src/program/generate.cpp:2088-2089`, `src/program/generate.cpp:2125-2128`）。

## 適用条件と副作用

効果があるのは CPU expert pool の仕事を実行する経路です。SYCL 版にも parser と pool 構築時の適用箇所があります。CPU pool を使わない構成では、指定しても該当する drain 動作は発生しません。特に `--no-pool` は pool callback を無効にする別オプションであり、両方指定した場合はこのフラグによる pool 仕事の分担変更は実処理に使われません（`src/program/generate.cpp:6928-6936`; SYCL 側 `sycl/src/program/generate.cpp:5445-5453`）。

指定しない場合はホストスレッドが pool に参加します。指定すると参加 thread 数と自動 task 数の算出からホスト分が除かれ、エンジンは stderr に表示する参加 thread 数や「ホストも drain する」表示をその状態に合わせて変えます（`src/program/generate.cpp:5975-5978`, `src/program/generate.cpp:5998-6002`）。CPU pool 内では仕事の取得順序・完了待ち自体は共有 queue のままで、ホストが仕事を取らないことが主な動作差です（`src/kernels/cpu/pool.cpp:1416-1435`）。性能の優劣はこのソース調査だけでは断定できません。

## 出力とエラー

このフラグ単独に対する validation error や専用警告は確認できません。エンジンの一般 parser は認識できない引数を `unknown argument: ...` と stderr に出し、usage を表示して終了コード `2` を返します（`src/program/generate.cpp:2787-2792`）。フラグを値付きオプションのように使った場合、余分な値が別の有効引数でなければこの経路に入ります。

## 調査範囲

対象 revision の CPU 実装 `src/program/generate.cpp`、pool 実装 `src/kernels/cpu/pool.cpp`、および SYCL 実装 `sycl/src/program/generate.cpp` を確認しました。Release 配布物や実機上の性能差は調べていません。索引が定める `strata-engine` の parser 範囲と照合し、同 revision の parser 定義を根拠にしています。CLI `--help` は実行していません。
