# `STRATA_PIPE_HELPER_SIBLING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL verifier の stepped 実行で、CPU expert pool を動かすパイプライン用 helper thread の CPU affinity を変更します。Linux でこの変数を有効にし、呼び出し元スレッドが単一 CPU に pin されている場合、helper をその CPU の SMT sibling に pin します。GPU の次 segment が pool の flag A を待っている間に、pool と host 側の flag-A wait が同じ logical CPU を奪い合う状況を避けるための opt-in です。

## 値と判定

共通 helper `env_on()` は `getenv()` が非 null で、値の先頭文字が NUL でも `'0'` でもない場合に true を返します。文字列全体の parse はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が NUL） |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、`2`、その他先頭が `0` 以外の非空文字列 | 有効 |

値を読むのは `pipe_helper_cpu()` の関数内 static 初期化時です。したがって、実際に stepped pipeline の helper 分岐へ初めて入った時点で判定され、その結果はプロセス内でキャッシュされます。その後の環境変更は反映されません。

## 有効になる条件

- SYCL backend でビルドされた verifier の Linux 実装に限られます。Linux 以外では関数が常に `-1` を返し、affinity を変えません。
- `STRATA_VERIFY_STEPPED` が有効で、all-resident ではなく、`STRATA_VERIFY_EAGER` が未設定であるなど、stepped window が実際に使われる必要があります。
- その stepped run 中に `STRATA_VERIFY_PIPE` が `0` でなく、次の graph segment が split segment である必要があります。`STRATA_VERIFY_PIPE=0` なら pool は helper thread でなく現在のスレッドから実行されます。
- split segment が作られる必要があります。capture 時の `STRATA_VERIFY_SPLIT=0` は split boundary を無効にするため、次 segment が split になる helper 経路は使われません。
- stepped run で `--remote-expert-opt` を使う経路は verifier がエラーとして拒否します。
- Linux で変数が有効でも、host thread の affinity mask がちょうど1 CPUでなければ sibling を選びません。mask の取得失敗または CPU 数が1でない場合、stderr に `strata verify: STRATA_PIPE_HELPER_SIBLING: host thread is not pinned to one CPU; unchanged` を出します。

## 実行時の詳細

有効条件を満たすと、実装は host thread の CPU 番号を取得し、`/sys/devices/system/cpu/cpu<host>/topology/thread_siblings_list` を読みます。例として `0,8` や `0-1` の形式を処理し、host CPU と異なる最初の CPU を sibling として選びます。ファイルを開けない、内容を解釈できない、または他の sibling がない場合は `-1` のままで affinity を変えません。

選んだ CPU 番号は stderr の `strata verify: pipelined pool helper on CPU <sibling> (host thread CPU <host>)` に出ます。sibling が見つからない場合は末尾に `: no SMT sibling, unchanged` が付きます。helper thread の中で `pthread_setaffinity_np()` を呼び、その後に CPU expert pool を実行します。この API の戻り値は検査されないため、ログは affinity 設定成功の保証ではありません。affinity 設定に失敗しても処理を中断したり、別経路へ切り替えたりしません。

この変数は pool helper の配置だけを変えます。pool の計算内容、GPU segment の構成、CPU expert の選択規則はこのコードでは変更しません。pipeline branch 外の helper thread や通常の非-stepped verify には影響しません。

## 根拠

- `sycl/src/core/verify.cpp:92-95`: 値の判定（`env_on`）。
- `sycl/src/core/verify.cpp:105-149`: Linux 限定の判定キャッシュ、host affinity の確認、sysfs からの sibling 選択、ログ。
- `sycl/src/core/verify.cpp:1687-1717,1734-1738`: stepped mode で graph segment を作る条件。
- `sycl/src/core/verify.cpp:1712-1713`: `STRATA_VERIFY_SPLIT` による split boundary の有効・無効。
- `sycl/src/core/verify.cpp:2041-2065`: stepped window と serve 処理の適用条件、および `--remote-expert-opt` の拒否。
- `sycl/src/core/verify.cpp:2090-2117`: `STRATA_VERIFY_PIPE` と split segment による helper thread 起動、および helper 上での affinity 設定と pool 実行。
