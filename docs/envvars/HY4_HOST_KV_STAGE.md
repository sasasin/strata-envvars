# `HY4_HOST_KV_STAGE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA build の Hy4-Flash MLA attention で、FP16 KV cache を処理する際に `k_attend_host_kv<false>` を使うか選びます。`1` はこの経路を強制し、`0` 以上の他の値は使わない指定、未設定または負値は query batch と cache のメモリ種別を使う自動選択です。選択経路は 16 行単位で KV を shared memory にロードして attention を計算します（`engine/src/hy4flash/run/mla_attn.hip.cpp:1162-1168,1269-1278,2218-2235`）。

これは生成結果や KV 配置を直接設定する変数ではなく、attention kernel の選択に作用します。通常の推論呼び出しは graph executor の `mla_attend`（`engine/src/hy4flash/run/hy4_graph.hip.h:2166-2169`）を通ります。

## 値と判定

値は `getenv` で取得し、設定されていれば `atoi` の結果を使います。文字列全体の検証や明示的な clamp はありません。`atoi` は先頭の空白と符号を許し、先頭の整数部分だけを変換するため、`1tail` と `+1` は `1`、`2tail` は `2`、`true`・空文字・空白だけは `0` になります。大文字小文字の比較はありません。`int` に収まらない数値の変換結果はこのコードで規定されていません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2218-2220`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA build、FP16 KV、fast path が利用可能 | `-1` として自動選択 | `atoi(value) == 1`。例: `1`, `+1`, `1tail` | `atoi(value) >= 0` かつ `!= 1`。例: `0`, 空文字, `true`, `2`, `2tail` |
| CUDA build、FP16 KV、fast path が利用可能 | — | 自動選択: `atoi(value) < 0`。例: `-1`, `-2`, `-1tail` | — |
| CUDA build 以外、または Q8 KV / fast path 不成立 | 値を読まない | この変数による有効化なし | この変数による無効化なし |

自動選択では `M <= 16` なら host-KV kernel を選びます。`M > 16` なら `cudaPointerGetAttributes` が成功し cache が `cudaMemoryTypeHost` と判定された場合に選びます。失敗時は選びません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2220-2228`）。

## 有効になる条件

- CUDA build で `HY4_CUDA` 分岐がコンパイルされていること。共通 GPU header は CUDA コンパイル時に `HY4_CUDA` を `1`、HIP 側を `0` にします（`engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327`）。
- この判定箇所に OS 固有の条件はありません。また、この値を上書きする CLI 引数や別の環境変数は同じ分岐では読まれていません。ただし `g_mla_force_simple` が true なら `fast_ok` が false となり、この環境変数の読み取りより先に simple kernel へ戻ります（`engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2199,2218`）。
- `mla_attend` の fast path 条件を満たすこと: `g_mla_force_simple` が偽、`NH` が 16 の倍数、`cache_slots > 0` かつ 16 の倍数、さらに window mode なら `ring > 0` かつ 16 の倍数であること（`engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2199`）。条件外では simple kernel に戻るため、この変数は参照されません。
- attention workspace が複数 split に必要なサイズを満たすこと。`S > 1` で workspace が null または不足なら simple kernel に戻り、環境変数の判定にも進みません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2200-2209`）。
- `a.kv_q8` が false であること。Q8 KV は環境変数を読む前に `k_attend_host_kv<true>` を起動して戻るため、この変数の指定に関わらずその分岐です（`engine/src/hy4flash/run/mla_attn.hip.cpp:2210-2218`）。
- 通常の推論では graph executor が MLA decode 呼び出しを行うこと。環境変数が設定されていても、該当する `mla_attend` 呼び出しがなければ効果はありません（`engine/src/hy4flash/run/hy4_graph.hip.h:2145-2169`）。

## 実行時の詳細

読み取り箇所は `mla_attend` の CUDA / FP16 / fast path / workspace 条件を通過した後だけ実行されます。関数内の `static const int` に初期化結果を保存するため、最初の該当呼び出しで一度読み、その後の呼び出しでは同じ値を使います。プロセス起動後でも初回該当呼び出しより前の変更は反映されますが、初期化後の環境変更は反映されません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2218`）。

`atoi(value) == 1` は `use_host_kv` を true にします。負値では自動選択し、0 以上で 1 以外なら false のままです。false の場合は CUDA FP16 用の後続経路（`HY4_MMA` が有効なら `k_attend_wmma`）を使います。true の場合は `k_attend_host_kv<false>` を起動し、split 数 `S > 1` なら部分結果を `k_combine` で統合します（`engine/src/hy4flash/run/mla_attn.hip.cpp:2218-2250`）。

自動選択で pointer 属性取得が成功しない場合は host-KV 経路を選びません。失敗時には `cudaGetLastError()` を呼んで状態を消費し、その後は通常の CUDA FP16 経路に進みます（`engine/src/hy4flash/run/mla_attn.hip.cpp:2224-2235`）。

## ログと測定値

この環境変数の判定や kernel 選択を知らせる専用ログ、エラー、終了経路はありません。ソースコメントには host-KV staging の性能比較がありますが、測定条件が示されていないため、測定値としては記載しません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2221-2223`）。

## 根拠

- 読み取り、値の分岐、fallback: `engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2250`
- host-KV kernel と shared-memory staging: `engine/src/hy4flash/run/mla_attn.hip.cpp:1162-1180,1221-1278`
- CUDA/HIP build macro: `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-327`
- 通常の graph executor からの呼び出し: `engine/src/hy4flash/run/hy4_graph.hip.h:2145-2169`
