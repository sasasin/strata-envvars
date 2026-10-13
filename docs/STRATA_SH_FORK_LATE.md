# `STRATA_SH_FORK_LATE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の MoE layer で、shared expert の計算を別 GPU stream/queue に開始するタイミングを切り替えます。既定動作（有効）では router と expert plan の計算、および通常経路の doorbell 公開の後に fork します。無効にすると、shared expert 側 stream/queue を layer の先頭で main 側へ依存させ、router などの前から実行可能にします。これは shared expert と GPU 側の初期処理が競合する時間をずらす制御で、router の選択式や計算自体を切り替える設定ではありません。

## 値と判定

CUDA/HIP 共通 verifier と SYCL verifier の両方で、`record_window()` 内の関数ローカル `static const bool` として読みます。値全体を parse せず、`getenv()` の結果の先頭文字だけを見ます。

| 環境変数の状態 | late fork 判定 |
|---|---|
| unset | 有効 |
| 空文字 | 有効（先頭文字は `\0` で `'0'` ではない） |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外の先頭文字 | 有効（例: `1`, `true`, `false`, 空白、任意の文字列） |

大文字小文字、数値としての妥当性、後続文字は検査されません。プロセス内で最初にこの static が評価された後は値が固定され、環境を書き換えても反映されません。CUDA/HIP と SYCL はそれぞれ別の verifier 実装に同じ判定があります。

## 有効になる条件

late fork が実際に選ばれるには、`sh_fork` 自体が有効で、さらに `ar_on()` が false である必要があります。

- `sh_fork` は `STRATA_SH_STREAM` が有効で、profiler が無効であり、shared stream と fork/join event が利用できる場合に成立します。SYCL では加えて `STRATA_VERIFY_STEPPED` が無効で、shared queue が in-order queue とは別であることが必要です。
- `STRATA_SH_STREAM` が unset の場合、CUDA/SYCL 側の `sh_stream_on()` は有効、HIP 側は無効です。同変数を設定すると、先頭文字が `0` なら無効、それ以外は有効です。したがって HIP では通常、`STRATA_SH_STREAM` を有効にしない限り本変数の分岐は実行されません。
- 全 expert が resident の `ar_on()` 経路では late fork は使われず、`sh_fork` が有効なら layer 先頭で fork する側になります。
- 条件が揃わず `sh_fork` が false の場合、`STRATA_SH_FORK_LATE` による stream/queue の順序変更は起きません。

## 実行時の詳細

値が有効で通常の非 all-resident 経路の場合、router による expert 選択と plan/doorbell 公開の後で main stream/queue の event/barrier を記録し、shared expert 用 stream/queue がそれを待つようにします。その後 `shared_expert_multi()` を shared stream/queue に投入し、join event/barrier を記録します。後続の combine 前には main stream/queue が join を待つため、shared expert の出力を使う処理より先に完了する順序を保ちます。

値が無効の場合（または all-resident 経路）は、layer の router より前に fork event/barrier を設定します。shared expert とその後の router/plan 処理が並行して進められる可能性があります。どちらの設定でも fork 自体が有効なら join は combine 前に行います。CUDA/HIP 共通実装では event を使い、SYCL 実装では DPCT event と queue barrier を使います。対象変数について独立したログ出力はありません。

## 根拠

- 値の読み取りと late fork 条件: `src/core/verify.cpp:1418-1429`, `sycl/src/core/verify.cpp:1286-1301`。
- router/plan/doorbell 後の late fork と shared expert 計算: `src/core/verify.cpp:1477-1507,1517-1541`, `sycl/src/core/verify.cpp:1335-1365,1370-1400`。
- combine 前の join wait: `src/core/verify.cpp:1647-1651`, `sycl/src/core/verify.cpp:1495-1501`。
- shared stream の既定と profiler に関する条件: `src/core/verify.cpp:184-202`, `sycl/src/core/verify.cpp:154-172`。
- `docs/DETAILS.md` には `STRATA_SH_STREAM` への関連記述がありますが、`STRATA_SH_FORK_LATE` の挙動や効果を個別に説明する記述は確認できませんでした。
