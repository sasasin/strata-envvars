# `STRATA_PIPE_HELPER_SIBLING`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL verifier の stepped serve で、CPU pool を実行する helper thread を、verifier の host thread が pin されている論理 CPU の sibling CPU に移そうとします。対象コードは SYCL backend の verifier にあり、CUDA/HIP 側の `src/core/verify.cpp` にはこの変数の参照がありません。コメントでは Arc A-series 向けの stepped mode の opt-in とされていますが、この変数自体に GPU 世代の判定はありません。

## 値と判定

`env_on()` は環境変数が未設定、空文字、または先頭文字が `0` の場合に false、それ以外は true とします。文字列全体や数値としての妥当性は調べません。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | 無効 |
| `0`、`0abc` | 無効 |
| `1`、`true`、`abc`、先頭が空白の ` 0` | 有効 |

## 有効になる条件

変数が有効でも、次の経路に入らない場合は sibling CPU の選択は行われません。

- SYCL backend の verifier である。
- `STRATA_VERIFY_STEPPED` が有効で、all-resident 経路ではなく、`STRATA_VERIFY_EAGER` が未設定で、実行対象 window に segment がある（`stepped_run`）。
- `STRATA_VERIFY_PIPE` が有効（未設定時は有効）で、次の segment が split segment である。
- Linux である。非 Linux では helper CPU は常に `-1` となり、affinity の変更を試みない。

`stepped_run` が remote expert optimization と併用されると serve は `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` で失敗するため、その経路では helper CPU の選択に進みません。

## 実行時の詳細

Linux では初回の pipelined split で `pipe_helper_cpu()` が呼ばれると、現在の host thread の affinity mask を読みます。mask がちょうど1 CPUでない、または読み取りに失敗した場合は `strata verify: STRATA_PIPE_HELPER_SIBLING: host thread is not pinned to one CPU; unchanged` を stderr に出して `-1` を返します。1 CPUに pin されている場合は `/sys/devices/system/cpu/cpuN/topology/thread_siblings_list` を読み、host CPU 以外の最初の CPU 番号を選びます。ファイルが読めない場合や他の CPU が見つからない場合も sibling は `-1` です。

選択結果は `pipe_helper_cpu()` の function-local `static` に保存されます。値は helper CPU の初回選択時に読み取られ、その後の環境変更では再評価されません。sibling 探索後は `strata verify: pipelined pool helper on CPU %d (host thread CPU %d)` を stderr に出し、sibling がない場合は `: no SMT sibling, unchanged` が付きます。split segment の serve は `std::thread` を作り、選択 CPU が非負なら helper thread 内でその CPU への `pthread_setaffinity_np()` を呼びます。戻り値は確認していないため、設定失敗をこのコードが検出・報告するとは言えません。CPU を設定しない場合、新しい thread は生成元から継承した affinity mask のままです。

関連する `STRATA_VERIFY_STEPPED` は翻訳単位の global `const` として初期化時に読まれます。`STRATA_VERIFY_PIPE` は最初の serve 呼び出し時に function-local `static` として読まれます。`STRATA_PIPE_HELPER_SIBLING` はそれらとは異なり、上記 helper CPU 選択が初めて必要になる時点で読み取られます。

## 根拠

- `sycl/src/core/verify.cpp:93-96` — env 判定（空文字と先頭 `0` を無効とする）。
- `sycl/src/core/verify.cpp:102-149` — stepped mode の説明、Linux 条件、affinity mask・sysfs sibling 探索、キャッシュとログ。
- `sycl/src/core/verify.cpp:2065-2084` — stepped run の条件と remote expert optimization のエラー。
- `sycl/src/core/verify.cpp:2114-2145` — `STRATA_VERIFY_PIPE`、split segment の条件、helper thread 作成と affinity 設定。
- `sycl/CMakeLists.txt:252-260,274-276` — この `verify.cpp` を含む SYCL engine と `strata` executable の構成。

`docs/DETAILS.md` と他の Strata docs を検索しましたが、この変数に関する追加の説明や測定値は見つかりませんでした。性能効果はコードだけからは確認できないため記載していません。
