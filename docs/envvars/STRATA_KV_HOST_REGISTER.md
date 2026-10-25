# `STRATA_KV_HOST_REGISTER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部 CUDA ランタイムやドライバー内部の動作は含めない。

## 役割

QSA の KV streaming が使うホスト側 K/V コピーについて、ページロック・デバイスマップ可能な領域を確保する際、最初に試す方法を選びます。`1` は通常メモリを `mmap` して `cudaHostRegister` する方法を先に試し、`0` は `cudaHostAlloc` を先に試します。最初の方法が失敗したときは、もう一方を fallback として試します。

これは KV streaming 自体を有効化するスイッチではありません。KV streaming が選ばれ、QSA state の host K/V 領域を割り当てる経路でだけ参照されます。

## 値と判定

| 環境変数の状態 | POSIX 側での最初の確保方法 |
|---|---|
| 未設定 | `/dev/dxg` が存在すれば `cudaHostRegister`、なければ `cudaHostAlloc` |
| 先頭文字が `1` | `cudaHostRegister` |
| 先頭文字が `0` | `cudaHostAlloc` |
| 空文字、または先頭文字が `0`/`1` 以外 | `/dev/dxg` の有無で自動判定 |

文字列全体の parse や比較はありません。たとえば `10` は `1` と同じ扱い、`0abc` は `0` と同じ扱いです。`true`、空白から始まる値、空文字は明示指定として解釈されず、自動判定になります。大文字小文字や後続文字は判定しません。

Windows (`_WIN32`) では `kv_host_alloc()` が環境変数を読む分岐に入らず、常に `cudaHostAlloc` を試します。したがって Windows ではこの変数は無効です。

## 有効になる条件

- `src/core/layer.cpp` の `kv_plan()` が QSA state を非 resident mode にした場合に、`qsa_state_init()` がホスト K/V コピーを割り当てます。通常は `--kv-resident` が正数で、最小 resident cell 数を適用した後の slot 数が全ページ数より少ない場合です。`--kv-resident 0` は全 K/V を VRAM に置く設定です。
- resident 指定があっても、指定値（最小値 20480 cells を下限とする）が context の全ページを収める場合は streaming mode にならず、この変数は使われません。`STRATA_KV_RING_OFF` や `STRATA_KV_MAIN_OFF` によって対象 state が resident に戻る経路もあります。
- 確保方式の判定は `kv_host_alloc()` 内の function-local `static const bool` に保存されます。最初の呼び出し後に環境変数や `/dev/dxg` の状態を変えても再判定しません。

## 実行時の詳細

`cudaHostAlloc` 方式は `cudaHostAllocMapped | cudaHostAllocPortable` を指定します。登録方式は匿名 `mmap` を作り、`cudaHostRegister` に `cudaHostRegisterPortable | cudaHostRegisterMapped` を渡します。登録が失敗すると、その `mmap` 領域を `munmap` して null を返します。どちらの方式も、選ばれた方が失敗するともう一方を試します。

登録方式で確保に成功したときは、プロセス中で最初の成功時に stderr に次の行を出します。登録方式を最初に試して失敗し、`cudaHostAlloc` に fallback した場合、この行は出ません。

```text
strata: KV streaming: the host copy is pinned with cudaHostRegister
```

両方の確保が失敗した場合、または確保後の `cudaHostGetDevicePointer()` が失敗した場合、QSA state 初期化は失敗します。main QSA layer (`mode == 1`) では `cannot pin ...` の診断を stderr に出し、呼び出し元は `session_init failed` として扱います。`cudaHostGetDevicePointer()` の失敗時には、別方式での再確保は行いません。

## 根拠

- `src/core/layer.cpp:523-530,531-568`: 自動判定、値の先頭文字判定、Windows 分岐、二方式の fallback、登録成功ログ。
- `src/core/layer.cpp:684-701,715-718`: KV plan が streaming mode を選ぶ条件、resident 下限 20480 cells。
- `src/core/layer.cpp:739-755,849-883`: QSA state 初期化で非 resident mode の場合に host K/V コピーを割り当てる処理。
- `src/program/generate.cpp:811-813,2336-2338,2981-2985`: `--kv-resident` の CLI 説明、解析、負値拒否と設定反映。
- `docs/DETAILS.md:86`: WSL2 では登録方式を先に使い、他の環境では通常 `cudaHostAlloc` を先にする設計説明。文書は Tesla P100 で `STRATA_KV_HOST_REGISTER=1`, `--kv int8 --kv-resident 32768` を実行した例に触れ、「answers and decode speed unchanged」と記載しています。これは同資料の報告であり、ここで独立に再測定した結果ではありません。
