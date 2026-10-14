# `STRATA_PREFILL_ISSUER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

長い prompt chunk の expert を GPU へ転送する際、host 側で copy を発行する処理を layer kernel の投入スレッドから分離するか選びます。既定では発行専用の host thread を起動します。専用 thread が unpinned blob の stager 完了待ちをしている間も、layer kernel を投入する thread は処理を続けられます。`STRATA_PREFILL_ISSUER=0` にすると、同じ expert のコピーを従来どおり layer 処理側の thread が順番に発行します。

対象実装は CUDA と SYCL の batched prefill です。変数はコピーの発行場所を切り替え、expert の列挙順や ring slot の使用順はどちらの経路でも同じです。ソースコメントは「same results」と説明していますが、数値的な同一性をこの調査で実行検証したものではありません。

## 値と判定

CUDA / SYCL とも `std::getenv()` の値に `std::atoi()` を適用し、結果が 0 以外なら有効です。文字列全体の妥当性検査や範囲制限はありません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| `0`、`00`、`false`、空文字、整数として先頭に数字のない文字列 | 無効（`atoi` 結果が 0） |
| `1`、`-1`、`2` | 有効（`atoi` 結果が 0 以外） |
| `1junk`、`-2x` | 有効（`atoi` が先頭の整数部分を変換） |
| ` 1`、`+1` | 有効（先頭空白と符号を含む整数変換） |

空文字は「未設定」ではなく、明示設定された値ですが、`atoi("") == 0` となるため無効です。`0junk` も先頭の整数部分が 0 なので無効です。数値変換不能の文字列も 0 として扱われます。

## 有効になる条件

値判定が有効でも、専用 thread を使うのは batched prefill の対象 chunk で `stream_all` が true の場合だけです。実装上の条件は、expert staging ring の slot 数 `m.ring` が `STAGE`（8）より大きいこと、chunk の token 数 `T` が `stream_all_min()` 以上であること、expert source `m.src` が存在することです。通常の CUDA 実装では `stream_all_min()` の既定は 1,024 tokens で、`STRATA_PREFILL_STREAM_MIN` または CPU share の設定により変わる経路があります。実際の ring slot 数も planner が決めるため、token 数だけでは専用 thread の使用を確定できません。

この関数内の `issuer_on` は関数ローカル `static const` です。初回評価後は同一プロセスで環境を書き換えても再評価されません。`issuer_on` は `stream_all` と組み合わせて `threaded_issue` を決める前に評価されるため、最初にこの処理へ入った chunk が短くても、その時点の値が後続 chunk に使われます。CUDA と SYCL の各実装は個別に同じ判定を持ちます。

## 実行時の詳細

`stream_all` のとき、batched prefill は layer ごとの非 resident expert を列挙し、各 expert を ring の `idx % m.ring` slot に割り当てます。threaded issuer が有効なら発行用 `std::thread` を起動します。CUDA ではその thread は補助 CPU affinity に設定され、対象 device を current にします。SYCL では対象 device を current にして処理します。発行 thread は、前の使用が終わるまで ring slot の再利用を待ち、安定 blob または stager が用意した blob を copy queue/stream に転送し、コピー完了 event/barrier を記録します。

layer kernel 側は `wait_issued()` で必要な expert の発行を確認してから進み、消費済み slot を `give_back()` で返します。threaded issuer が無効なら thread は起動せず、layer 側が `issue_until()` を呼び、同じ ring を使ってコピーを発行します。したがって、この変数は「expert を転送するか」ではなく、長い chunk の転送発行を kernel 投入 thread と独立させるかを切り替えます。

発行 thread が joinable の場合、chunk 終了時に join し、その thread が計測した発行時間・expert 数・DMA 数を prefill stats に加算します。この変数専用のログや警告は見つかりません。失敗時の挙動は使用する copy API や周辺の prefill error handling に従い、この変数固有の fallback はありません。

## 根拠

- `src/prefill/prefill.cpp:122,164-168,2341` — ring の小 chunk 用 slot 数、stream-all 閾値（既定 1,024）、有効条件。
- `src/prefill/prefill.cpp:2455-2477,2478-2502` — 既定 ON の `atoi` 判定、threaded issuer の起動と CUDA copy 発行。
- `src/prefill/prefill.cpp:2506-2514,3102,3120,3989-4012,4148-4154` — consumer 側との同期、inline 経路、chunk 終了時の統計反映。
- `sycl/src/prefill/prefill.cpp:105,121-126,2462,2616-2637,2638-2677,2681-2689,3285,3305,4414-4419` — SYCL 側の同等実装と条件。
- `docs/DETAILS.md:1926-1939` — prompt chunk の expert を GPU に stream する構成と chunk/ring planner の説明。`STRATA_PREFILL_ISSUER` 自体の説明や、この変数を切り替えた測定値はこの資料にはありません。
