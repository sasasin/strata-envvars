# `STRATA_CPUEXP_COLD_READERS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`.strata` ファイルに残した cold expert を CPU 側で読み込む `ColdStore` の reader thread 数を指定する。cold expert の本数・配置、キャッシュ容量、I/O モードや演算スレッド数はこの変数では変わらない。`CpuExperts::Impl::set_cold` が cold expert を 1 件以上登録するときに値を読み、`ColdStore::open` と `TwoPriorityExpertScheduler::start` に渡す（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2737,1387-1433`）。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `std::atoi` で整数変換した後、`std::max(1, ...)` を適用する。unset の既定値は 8。空文字、数値に変換できない文字列、0、負数は `atoi` の結果が 0 以下となり 1 reader になる。`atoi` は先頭の空白と符号を許し、数字の後の文字を検査せず、数字列の後ろは読み飛ばす。したがって `4extra` や `  +4` は 4、`true` や `0tail` は 1 になる。大文字小文字の比較はない。正の値に上限 clamp はない。`atoi` の整数範囲を超える入力は C の仕様上扱いを保証できず、コードにも検査・エラー処理はない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2725-2736`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・縮退する値 |
|---|---:|---|---|
| `set_cold` で cold expert が 1 件以上ある | 8 readers | `2`, `4extra`, `+4` → 2、4、4 readers | 空文字、`0`, `-2`, `true`, `0tail` → 1 reader |
| cold expert が 0 件 | 読み取らない | 該当なし | 値は使われない（`n == 0` で先に return） |

## 有効になる条件

- cold expert の登録処理が実行されること。`set_cold` は mask から cold record を数え、0 件なら環境変数を読む前に成功 return する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2705-2729`）。
- HIP 実行経路ではモデルの tier 配置に cold expert ができ、`g.cold_mask` が空でなく、`HY4_COLD_API` が有効であること。tier 3 はホスト RAM 予算を超えて SSD に残る expert として設定され、graph 初期化から `set_cold_experts` が呼ばれる。API macro は `hy4_gpu.h` で既定 1（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1084-1110,1227-1236`; `engine/src/hy4flash/run/hy4_graph.hip.h:1566-1574`; `engine/src/hy4flash/run/hy4_gpu.h:12-15`）。
- Linux SYCL の unified expert setup では cold mask があり、`_WIN32` でない場合に `set_cold_experts` が呼ばれる。SYCL の Windows 経路はこの呼び出しをコンパイル時に除外する（`engine/src/hy4flash/sycl/sy_graph.h:173-200,217-228`）。
- HIP の `--ssd-experts` は RAM expert 予算を 0 にすることで cold tier ができる構成を指定し、cold I/O を `direct` に設定するが、この CLI 引数は reader 数を上書きしない。別の reader 数 CLI 引数は確認できない（`engine/src/hy4flash/run/hy4_main.hip.cpp:460-466`）。
- cold cache を開く際に reader 数は最低 1 に再 clamp され、scheduler 起動時の reader thread 数になる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1428-1433`）。環境変数値を使う他の環境変数や設定ファイルの優先経路はない。

## 実行時の詳細

環境変数を読むのは `set_cold` の呼び出しごとで、プロセス起動時の固定 cache や関数 `static` への保存はない。通常の HIP / Linux SYCL の初期化では cold mask 設定中に呼ばれるため、その呼び出し時点の値がその `ColdStore` の reader pool に使われる。プロセス実行中に環境変数を変更しても、既に起動した pool の数は変わらない。再度 `set_cold_experts` を呼べば再読込され、既存 cold store を reset して reader を join した後に新しい store を開く（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2703,2725-2755`）。

cold mask が作られるかは別の配置処理で決まり、この変数はその後の cold-store reader 並列度だけを決める。HIP の tier 3 は host expert RAM budget を超えた cold tail。Linux SYCL では RAM 予算超過のほか、adaptive VRAM cache からの on-disk fallback が cold mask に含まれる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1090-1110,1227-1236`; `engine/src/hy4flash/sycl/sy_graph.h:162-200`）。

cold store の open が成功すると reader 数を含む状態が stderr に出る。開けない場合や cache 割当て失敗では `set_cold` が false を返し、cold record を解除する。HIP は `init: <error>` を出して status 1 で終了し、SYCL は `experts: <error>` を出して status 1 で終了する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1413-1425,2735-2740`; `engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`; `engine/src/hy4flash/sycl/sy_main.cpp:298-306`）。

## ログと測定値

open 成功時、stderr に次の形式で実際に採用された reader 数が出る（`%d readers` 部分）。

```text
[cpuexp] cold experts: <件数> (slot <サイズ> MB, <slot数> slots = <cache容量> MB cache, <reader数> readers, io=<方式>)
```

このログは環境変数名や入力文字列ではなく、clamp 後の reader 数を示す。該当変数について Strata の資料に記載された測定値は確認できなかった（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2742-2749`）。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2755` — cold mask 登録、0 件時の早期 return、環境変数の読み取り、reader pool 初期化とログ。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1387-1433` — cold-store open と reader 数を使った scheduler 起動。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1084-1110,1227-1236` — HIP の RAM budget 超過による cold tier 形成。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1566-1574`, `engine/src/hy4flash/run/hy4_gpu.h:12-15` — HIP graph からの登録と `HY4_COLD_API` の既定値。
- `engine/src/hy4flash/sycl/sy_graph.h:173-228` — SYCL の cold mask と Linux 限定の登録呼び出し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:460-466`, `engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`, `engine/src/hy4flash/sycl/sy_main.cpp:298-306` — `--ssd-experts` の設定および初期化失敗時のログと終了。
