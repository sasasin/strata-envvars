# `STRATA_DOORBELL_CHECK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL backend の doorbell で、GPU がホスト共有メモリへ発行した activation (`x`) と expert ID (`ids`) の内容をチェックサムで照合し、GPU の ring が見えてから payload が揃うまでホスト側で待つ機能を有効にします。さらに、residency table を使う `doorbell_publish_res` 経路では、有効時に expert が全て VRAM resident でも `x` を含む全 payload を発行し、同じチェックに使うチェックサムを作ります。

## 値と判定

両方の判定箇所で `std::getenv()` の結果が null でないことと、先頭文字 `v[0] == '1'` だけを調べます。文字列全体や数値としての parse はしません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが先頭文字が `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| その他（例: `0`, `true`, ` 1`, `01`） | 無効 |

`doorbell_publish_res()` と `doorbell_wait_payload()` はそれぞれ関数内 `static const bool` に判定結果を保存します。各関数の初回呼び出し後は、その関数についてプロセス環境を書き換えても再評価されません。2箇所は別々に初回評価されます。

## 有効になる条件

この変数を読む実装は `sycl/src/kernels/cuda/elementwise.dp.cpp` にあります。したがって、ここで説明する制御は Strata の SYCL 実装に対するものです。CUDA の `src/kernels/cuda/elementwise.cu` の `doorbell_publish_res()` にはこの判定がなく、CUDA/HIP に同じ効果があるとは確認できません。

実行時に residency-aware な `doorbell_publish_res()` が選ばれるかは、SYCL verifier の分岐によります。`remote_opt_` または `always_publish_` の場合は通常の `doorbell_publish()` を使い、そうでなく `lean` でない場合に `doorbell_publish_res()` を呼びます。`lean` の場合は doorbell を発行しません（`sycl/src/core/verify.cpp:1351-1359`）。

## 実行時の詳細

`doorbell_publish_res()` は初回呼び出し時に値を判定し、結果を SYCL publish kernel に渡します。有効なら kernel は `d_res` の residency にかかわらず `x` と `ids` をホスト共有領域へコピーし、その全要素から位置を混ぜた32-bitワードの折り返し加算チェックサムを作り、ring とともに記録します。無効なら、従来どおり expert の miss があるときだけ `x` をコピーします。全 expert が resident の場合は `x` をコピーせず、payload checksum は `0` になります（`elementwise.dp.cpp:666-709,790-816`）。

`doorbell_wait_payload()` も初回に独立して値を判定します。無効なら直ちに `true` を返し、ring に対するホスト側 payload 検査を行いません。有効なら `doorbell_payload_ready()` が ring tag を確認してから acquire fence を置き、ホスト側の `x` と `ids`（および通常 publish 経路では weights も）のチェックサムを比較します。一致しない場合は一致するまで最大 `timeout_ms` 待ち、待機中は64回ごとに pause 命令を実行します。既定 timeout は2,000 msです（`elementwise.dp.cpp:571-589,819-843`; `include/strata/kernels/elementwise.hpp:131-144`）。

SYCL session と verifier の通常・pipelined window は、ring を確認した後、CPU expert pool が共有 payload を読む前にこの wait を呼びます（`sycl/src/core/session.cpp:995-1019`; `sycl/src/core/verify.cpp:2255-2269,3774-3788`）。有効時に payload が timeout までに揃わないと、session は `session_loop: layer ... rang but its payload never arrived whole`、verifier は `verify: layer ... rang but its payload never arrived whole` をエラーとして返します。無効時はこの関数による timeout は起きません。

この変数が有効でも、他の doorbell publish 経路すべてで `x` が無条件コピーされるわけではありません。明示的な全 payload 発行の変更は `doorbell_publish_res()` に限られ、通常の `doorbell_publish()` はもともと `x`、`ids`、weights とチェックサムを発行します。

## 文書との照合

`docs/DETAILS.md` と `docs/INTEL.md` に `STRATA_DOORBELL_CHECK` の説明は見つかりませんでした。実装コメントは Arc A750 (i915) でホスト側の全 payload checksum が decode の15–20%を要したと記していますが、当該 commit の資料にこの測定条件や手順の詳述は見当たらないため、一般的な性能値としては扱いません（`sycl/src/kernels/cuda/elementwise.dp.cpp:831-834`）。`sycl/CMakeLists.txt:366-369` は `sycl_payload_pairs` テストにこの変数を `1` で設定しますが、これはテストの実行条件であり、製品実行時の既定値を示しません。

## 根拠

- 読み取り箇所と kernel への値渡し: `sycl/src/kernels/cuda/elementwise.dp.cpp:790-816,829-843`
- 値が publish kernel に及ぼす分岐: `sycl/src/kernels/cuda/elementwise.dp.cpp:666-709`
- チェックサム計算: `sycl/src/kernels/cuda/elementwise.dp.cpp:571-589,819-827`
- SYCL verifier の publish 選択と wait 呼び出し: `sycl/src/core/verify.cpp:1351-1359,2255-2269,3774-3788`
- SYCL session の wait とエラー経路: `sycl/src/core/session.cpp:995-1019`
- wait の宣言・既定 timeout: `include/strata/kernels/elementwise.hpp:131-144`
- CUDA 実装との比較: `src/kernels/cuda/elementwise.cu:385-391`
