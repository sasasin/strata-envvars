# `STRATA_INK_CPU_PROF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA の Inkling2 hybrid engine が、CPU worker の M=1 doorbell 経路について集計した診断値を `stats_total()` の呼び出し時に stderr へ出すためのフラグです。生成・ルーティングの選択を変える設定ではありません。`InkHybridEngine::start_workers()` は値の設定有無を `prof_on` に保存し、row-shared 経路の内訳時間を集めます。M=1 doorbell の訪問時間・job 数・対象 expert の `body_bytes` 合計は、フラグの有無によらずカウンターに加算されています（`engine/src/inkling2/cuda/ink_hybrid.cuh:1406-1409, 1788, 1937-1942, 1969-1975`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` で環境変数の存在だけを判定します。したがって空文字も設定ありです。`0`、`false`、`true`、その他の文字列に意味の差はありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1465, 1788-1789`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA Inkling2 hybrid worker 起動時の内訳タイマー収集 | `prof_on=false`。row-shared 経路の plan / master own / wait / worker busy 時間を記録しない | 空文字、`0`、`1`、`true`、任意の文字列（存在すれば `prof_on=true`） | 値の文字列による無効値はない。環境変数自体が未設定の場合のみ無効 |
| `stats_total()` 呼び出し時の profile 行出力 | profile 行を出さない | 空文字、`0`、`1`、`true`、任意の文字列（その時点で存在する場合） | 呼び出し時点で未設定の場合 |

profile 行は `prof_visits > 0` のときだけ出ます。起動時と stats 呼び出し時の判定は別です。起動時 unset のまま実行中に設定すると行は出ますが、起動時に無効だった内訳タイマー値は記録されていないためゼロ表示になります。起動時に設定して途中で unset すると、値は蓄積されても unset 中の stats 呼び出しでは表示されません。カウンターはプロセス内で初期化され、起動時にリセットする環境変数優先順位や CLI 上書きはありません（同 `:1407-1409, 1465-1471, 1788, 1937-1942`）。

## 有効になる条件

- CUDA Inkling2 hybrid backend であること。この実装は `engine/src/inkling2/cuda/ink_hybrid.cuh` にあります。CPU、SYCL、Metal backend にこの変数を読む実装はありません（同 `:1326, 1788`。他 backend の所在は `engine/src/inkling2/{ink_cpu_backend.cpp,sycl/ink_sycl_backend.cpp,metal/ink_metal_backend.mm}`）。
- `n_host_experts > 0` で `start_workers()` が起動されること。通常のロード経路は host expert がある場合に worker を開始します（`engine/src/inkling2/cuda/ink_runner.cuh:497-503, 622-628, 1374-1382, 1588-1595`）。
- CPU 側で M=1 の doorbell job が実行されること。hybrid launcher は `M == 1 && !hyb.exact_mode` のとき doorbell を発行し、exact mode の M=1 はカード側の staging 経路に入ります。M>1 の batched 経路もこの profile カウンターを更新しません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1969-1975, 2505-2520`）。
- profile 行を観測するには、さらに `stats_total()` が呼ばれる必要があります。inkling2 server の `STATS` コマンドは `backend.stats()` を呼び、CUDA backend はそこで `hybrid.stats_total()` を呼びます（`engine/src/inkling2/ink_serve.h:748-753`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:96-114`）。統計呼び出しがなければ、集計行は出ません。

他の環境変数、CLI 引数、設定ファイルによるこのフラグの上書きはありません。`STRATA_INK_EXACT` などが選ぶ lane は doorbell 経路の有無に関係しますが、この文書のフラグ自体を上書きしません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1788-1793, 2505-2520`）。

## 実行時の詳細

`start_workers()` が worker を開始するときに `prof_on` を一度設定します。M=1 doorbell の master worker は各訪問の開始時刻を取り、処理後に経過時間・訪問数・job 数・選択された job 群に対応する `host_meta[].body_bytes` の合計を atomic counter に加算します。この基本集計は `prof_on` で囲われていません。row-shared 経路の plan / own / wait 時間と、他 worker の row task 実行時間は `prof_on` が true の場合に限って計測します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1407-1409, 1828-1893, 1907-1909, 1937-1942, 1969-1975`）。

`stats_total()` は呼び出しごとに環境変数を再確認し、存在し、かつ訪問が1回以上あれば stderr に2行出します。第1行は thread 数、visits/jobs、平均 jobs/visit、CPU wall time、平均 µs/visit、集計 bytes と換算帯域、平均 MB/expert を出します。第2行は read bell + plan、master own share、他 worker 待ち、他 worker の平均 busy 時間を出します。これらは実装上の集計・換算値であり、性能測定結果を保証するものではありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1457-1471`）。

## ログと測定値

profile 有効時かつ `prof_visits > 0` の stats 呼び出しで、stderr に次の形式で出力します（書式文字列そのものは `engine/src/inkling2/cuda/ink_hybrid.cuh:1465-1471`）。

```text
[InkCpuProf] threads=... visits=... jobs=... (... experts/visit) cpu wall ... s = ... us/visit; ... GB read = ... GB/s aggregate, ... GB/s per thread; ... MB/expert
[InkCpuProf] per visit: read bell + plan ... us, master's own share ... us, then waiting for the others ... us; the other threads busy ... us each (of ...)
```

未設定時や訪問数ゼロではこの2行は出ません。Strata `docs/DETAILS.md` にこの変数固有の測定値や性能主張は見当たりません。ここでは新たな測定はしていません。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1406-1409` — profile counter と起動時フラグ。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1457-1471` — stats 呼び出し時の判定と stderr 出力。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1788` — 起動時の設定有無判定。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1937-1942, 1969-1975` — 条件付き内訳計測と常時更新の基本 counter。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:2505-2520` — exact M=1 と doorbell M=1 の分岐。
- `engine/src/inkling2/ink_serve.h:748-753`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:96-114` — server の STATS から集計への呼び出し。
