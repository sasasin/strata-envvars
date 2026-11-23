# `STRATA_CPUEXP_COLD_CACHE_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の CPU expert 処理で、`.strata` ファイルからオンデマンドで読む cold expert の本体を保持する RAM slot cache の容量目安を MiB 単位で指定する。`CpuExperts::Impl::set_cold` は値を slot 数に換算し、`ColdStore` の slot 配列と連続メモリを作る。ジョブで再利用された cold expert は cache hit になり、slot が足りない場合は LRU slot が再利用される。常駐 RAM expert や GPU expert の容量を指定する変数ではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1297-1301, 1438-1454, 2699-2748`）。

| 実行経路 | 読み取りと適用 |
|---|---|
| CUDA/HIP Hy4-Flash | CPU expert mask があり、cold mask もある場合に `set_cold_experts` を呼ぶ。cold API が build に含まれない場合は設定値を読む前に初期化失敗となる（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1573`）。 |
| SYCL Hy4-Flash | cold expert が 1 件以上あり、かつ Windows 以外の場合に `set_cold_experts` を呼ぶ。Windows ではこの呼び出しブロック自体がない（`engine/src/hy4flash/sycl/sy_graph.h:217-227`）。 |

## 値と判定

読み取り箇所は `std::getenv("STRATA_CPUEXP_COLD_CACHE_MB")` の 1 箇所で、値全体の検証ではなく `std::atoi` で整数変換した後に `std::max(1, ...)` を適用する。未設定なら 256。空文字、数字で始まらない文字列、0、負数は `atoi` の結果が 0 以下となり 1 に丸められる。正の整数部分の後ろに文字があれば、その後ろは `atoi` に無視される（例: `16tail` は 16）。先頭空白と符号は `atoi` の変換規則に従う。文字列全体の数値妥当性、大文字小文字、単位接尾辞は検査しない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2725-2734`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・扱い |
|---|---:|---|---|
| cold expert が 1 件以上ある `set_cold` | 256 MiB 相当 | 1 以上の `atoi` 結果。例: `1`, `16`, `16tail` | ``, `abc`, `0`, `-5` は 1 に丸める。値を拒否する入力エラー経路はない。 |
| cold expert が 0 件 | 読み取りなし | なし | `n == 0` で早期 return するため、設定値は参照されず cache も作らない。 |

変換後の `cache_mb` は `max(1, cache_mb)` としてから `(cache_mb << 20) / maxsz` を計算する。ただし slot 数は最低 2 なので、設定が 1 MiBでも実際の cache は最低 `2 * maxsz` バイトとなる。`maxsz` は対象 cold expert の body サイズを 4 KiB 単位に切り上げた最大値。したがって値は上限の厳密なバイト数ではなく、slot 数を決める目安であり、実際の確保量は `nslots * maxsz` になる。起動ログもこの実確保量を表示する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2703-2727, 2734-2748`）。

## 有効になる条件

- Hy4-Flash の GPU/CPU expert 分割で cold mask が作られ、少なくとも 1 expert が `.strata` ファイルから読む cold tier に割り当てられること。CUDA/HIP 側では `HY4_COLD_API` build 条件も必要（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`, `engine/src/hy4flash/run/hy4_graph.hip.h:1564-1573`）。
- SYCL 側は cold expert がある場合でも `#ifndef _WIN32` のブロック内だけで cold cache を初期化する（`engine/src/hy4flash/sycl/sy_graph.h:217-227`）。
- `--ram-experts-gb` や `--ssd-experts` は RAM/cold tier の割り当てに関係し、cold tier を生じさせることがあるが、この変数を直接上書きしない。`--ssd-experts` は RAM 予算と `STRATA_CPUEXP_COLD_IO` を設定するのみ（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-465`）。
- `STRATA_CPUEXP_COLD_READERS` は reader 数、`STRATA_CPUEXP_COLD_IO` は読み取りモードを別々に決める。これらは cache MB 値を上書きしない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2726-2736`）。SYCL では Linux かつ cold bytes が 12,000,000,000 未満で `STRATA_CPUEXP_COLD_IO` が未設定なら、呼び出し前に `buffered` を設定するが、cache 容量には影響しない（`engine/src/hy4flash/sycl/sy_graph.h:221-227`）。
- CLI にこの容量を直接指定する引数は確認できない。プロセス環境から読む値が使われる。

## 実行時の詳細

値は `set_cold_experts` が呼ばれた際に `set_cold` 内で読み取られ、`ColdStore` の生成時に slot 数とメモリ確保量へ反映される。各 cold expert body は 1 slot を占める。ジョブ開始時に resident expert と cache hit を先に処理し、miss は空きまたは最も古い未 pin slot へ読み込み、cache の再利用・追い出しを行う（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2748, 2195-2255, 2471-2513`）。

この関数内に環境値の static cache はないが、初期化済み `ColdStore` の容量はプロセス環境を再読せず維持される。再度 `set_cold` すると既存 store を破棄してから環境値を読み直す。通常のモデル初期化では cold mask 作成後に呼び出すため、その初期化後の環境変更は現在の cache に反映されない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2702, 2725-2736, 2753-2755`）。

cache の open またはメモリ確保に失敗すると `set_cold` は `false` を返し、cold mask 設定を中断する。HIP graph 初期化はそのまま失敗を返し、SYCL の初期化も同様に `false` を返す。Linux で direct IO の open に失敗した場合は buffered + `FADV_DONTNEED` に切り替えて継続を試みるが、これは cache サイズ値の補正ではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1416-1426, 2735-2740`; `engine/src/hy4flash/run/hy4_graph.hip.h:1566-1572`; `engine/src/hy4flash/sycl/sy_graph.h:221-227`）。

## ログと測定値

初期化成功時、stderr に `[cpuexp] cold experts: ... (slot ... MB, ... slots = ... MB cache, ... readers, io=...)` が出力される。表示される cache MB は要求値そのものではなく `nslots * maxsz` から計算した実確保量。Windows では `NO_BUFFERING+OVERLAPPED` または `buffered+OVERLAPPED`、他の環境では `O_DIRECT`、`buffered`、`buffered+fadvise` のいずれかが表示される（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2742-2748`）。cold 読み込み自体が失敗したジョブでは stderr に `[cpuexp] cold: a read from the .strata file failed; results of this job are invalid` が出るが、これは cache 容量設定の妥当性警告ではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2516-2541`）。

この変数の設定値ごとの性能測定値は、確認した Strata 資料に見当たらないため記載しない。

## 根拠

- 値の読み取り、既定値、slot 数算出、成功ログ: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2749`
- slot cache と LRU: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1297-1325, 1434-1466, 2195-2255, 2471-2513`
- CUDA/HIP の初期化条件: `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1573`; cold tier 割当: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`
- SYCL の cold 割当、OS guard、IO 既定値: `engine/src/hy4flash/sycl/sy_graph.h:155-200, 217-227`
- cold tier に関係する CLI オプション: `engine/src/hy4flash/run/hy4_main.hip.cpp:455-465`
