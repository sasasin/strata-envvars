# `HY4S_DISCARD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL エンジンの共有キュー `hy4s::Q()` を作るとき、環境変数が有効ならキューへ `sycl::ext::oneapi::property::queue::discard_events()` プロパティを指定します。Strata のソースコメントは、この設定では `submit` / `memcpy` が返すイベントを待たず、ホスト側フラグまたは `q.wait()` を使う想定としています。カーネルやモデル計算の選択自体を変える分岐はありません（`engine/src/hy4flash/sycl/sy_common.h:154-179`）。

この読み取りは `STRATA_ENABLE_SYCL` で構成される別個の実験的 Intel Arc SYCL エンジンの共有コードにあります。通常の CUDA/HIP/CPU エンジンの設定としては参照されません（`engine/CMakeLists.txt:23-32`）。

## 値と判定

`std::getenv` で取得し、値が存在して `d[0] == '1'` の場合だけ有効です。文字列全体の解析・数値変換はしません。したがって空文字、未設定、先頭が `1` 以外の値は無効で、`1`、`10`、`1anything` は有効、`0`、`01`、`true`、` 1` は無効です。大文字小文字や数値としての妥当性は検査されません（`engine/src/hy4flash/sycl/sy_common.h:161-163`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `HY4S_PROF` が先頭 `1` ではない場合 | discard-events プロパティなし | `1`、`10`、`1anything` | 空文字、`0`、`01`、`true`、` 1` |
| `HY4S_PROF` の先頭が `1` の場合 | discard-events プロパティなし | 該当なし（この分岐では参照されない） | `HY4S_DISCARD` の値にかかわらず discard-events は選ばれない |

## 有効になる条件

- SYCL エンジンが `hy4s::Q()` を初期化すること。`Q()` は GPU 選択経路と `HY4S_CPU_DEVICE` が先頭 `1` の CPU 選択経路の両方で、同じ `make_props()` を使います（`engine/src/hy4flash/sycl/sy_common.h:157-175`）。
- `HY4S_PROF` が未設定、空、または先頭が `1` 以外であること。`HY4S_PROF` の先頭が `1` なら profiling 用プロパティを返すため、`HY4S_DISCARD` は判定されません（`engine/src/hy4flash/sycl/sy_common.h:158-163`）。
- コマンドライン引数による `HY4S_DISCARD` の上書きはこの読み取り箇所にはありません。実際にキューを使わない処理では `Q()` の初期化もこの設定の適用もありません。

## 実行時の詳細

`Q()` 内の関数ローカル `static sycl::queue q` を初めて初期化するときに評価され、その後は同じキューを返します。そのため、初回 `Q()` 呼び出し後にプロセス環境を変更しても、既存キューのプロパティは変わりません。環境変数を子プロセスへ転送・設定する処理は、この変数の読み取り経路にはありません（`engine/src/hy4flash/sycl/sy_common.h:154-176`）。

有効時もキューには `in_order()` が併せて指定されます。無効時は `in_order()` のみです。共有ヘルパー `wait()` はキュー全体に `wait_and_throw()` を呼びます（`engine/src/hy4flash/sycl/sy_common.h:162-179`）。

ソースコメントは discard-events 設定時、`submit` / `memcpy` が返すイベントを待たないよう記しています。しかし、共通キューを使う実装には返却イベントを `.wait()` する箇所も残っています。例としてモデル重みコピー（`engine/src/hy4flash/sycl/sy_model.h:121-128`）、MoE レイヤー処理（`engine/src/hy4flash/sycl/sy_graph.h:1236-1243`、`1361-1367`）、GPU への peer 結果コピー（`engine/src/hy4flash/sycl/sy_peer.h:535-537`）があります。設定コメントとこれらの呼び出しの整合性、および実行時に起きる結果はソースだけでは確定できません。これらの経路での失敗や終了状態は推測しません。

## ログと測定値

この変数の判定に伴う `printf` / `fprintf`、警告、エラー出力はありません。ソースコメントには「cheaper launches」とありますが、測定条件や数値は示されていないため、性能向上は確認済みの測定値として記載しません（`engine/src/hy4flash/sycl/sy_common.h:155-163`）。

## 根拠

- 読み取り・値判定・`HY4S_PROF` との優先関係・キュー初期化・cache: `engine/src/hy4flash/sycl/sy_common.h:154-179`
- SYCL が別 backend として構成される条件: `engine/CMakeLists.txt:23-32`
- 返却イベントを待つ実装例: `engine/src/hy4flash/sycl/sy_model.h:121-128`、`engine/src/hy4flash/sycl/sy_graph.h:1236-1243`、`engine/src/hy4flash/sycl/sy_graph.h:1361-1367`、`engine/src/hy4flash/sycl/sy_peer.h:535-537`
