# `STRATA_PF_PEER_COMPACT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--peer-device` で prompt の MMQ 経路を補助 GPU に分担させるとき、補助 GPU 上の中間バッファを layer 全体の行数分確保するか、最大 16 expert の group ごとに処理するかを選びます。compact 経路は group ごとの一時バッファと二重化した結果行バッファを使い、行数上限を `T_max * K` にします。非 compact 経路は `--peer-prefill-rows` などから渡された上限行数分の layer サイズのバッファを使います。compact によって helper GPU のメモリ使用量が減るという説明は実装コメントにありますが、ここではソースの説明として扱い、性能・容量の測定結果とは見なしません。

対象は `src/prefill/prefill.cpp` の CUDA/HIP 系 `Prefill::set_peer()` と `sycl/src/prefill/prefill.cpp` の SYCL 実装です。これは通常の `--peer-device` 用設定です。layer-split の stage helper 経路は `set_stage_helper()` 内で compact を直接 `true` にしており、この環境変数を読みません。

## 値と判定

両実装とも `std::atoi()` の結果が 0 かどうかで判定します。文字列全体の厳密な比較ではなく、先頭の空白の後にある符号付き十進数部分を変換し、数字でない文字に達したところで止まります。

| 値 | compact 判定 |
|---|---|
| unset | 有効 |
| `0`、空文字、`false`、数字で始まらない文字列 | 無効（`atoi` が 0） |
| `1`、`-1`、`2`、`1tail`、` 1tail` | 有効（`atoi` が非 0） |

大小文字は判定に関係しません。無効値専用の警告や fallback はありません。判定は `set_peer()` が peer と MMQ prompt 経路を確認した後、バッファを確保する際に行われます。`set_peer()` を呼び出した時点の値でその `PeerPrefill` の設定が決まり、各 layer や chunk のたびには読み直しません。

## 有効になる条件

- peer が有効であり、MMQ prompt 経路があること。満たさない場合は `set_peer()` が peer 設定を作らず、この変数は効果を持ちません（`src/prefill/prefill.cpp:1649-1658`, `sycl/src/prefill/prefill.cpp:1689-1695`）。
- CUDA/HIP 系で P2P が使えない場合、`STRATA_PF_PEER_HOST=0` で host route を拒否しない限り、`STRATA_PF_PEER_COMPACT=0` でも compact が強制されます。layer サイズ経路は P2P コピー用と実装されています（`src/prefill/prefill.cpp:1652-1655,1697-1699`）。
- SYCL では P2P がない場合、compact の判定に進む前に peer 経路自体が拒否されます（`sycl/src/prefill/prefill.cpp:1692-1695`）。
- `set_stage_helper()` の peer streaming は値に関係なく compact 固定です（`src/prefill/prefill.cpp:1544-1554`, `sycl/src/prefill/prefill.cpp:1531-1541`）。
- compact が有効なら行上限は `T_max * K` に置き換わります。無効なら渡された `cap_rows` を使い、上限を超える peer expert の行は peer に送らず primary 側に残します（`src/prefill/prefill.cpp:1660-1662,1700-1702,3251-3258`; SYCL: `1697-1699,1756-1759,3370-3377`）。

## 実行時の詳細

compact 経路は最大 `T_max` 行単位の quantize / expert intermediate buffers と、結果行用の `Dm_b[2]` を確保します。peer が担当する expert を最大 `MMQ_GROUP` 個かつ合計 `T_max` 行以下の group に分け、group ごとに MMQ 計算し、結果を二重化バッファ経由で戻します（`src/prefill/prefill.cpp:593-603,1700-1710,3450-3471`; SYCL: `552-562,1756-1767,3535-3557`）。非 compact 経路では `cap_rows` に応じた単一セットの `Xq`, `Hq`, `GU`, `H`, `Dm` バッファを確保します（CUDA/HIP: `1729-1735`; SYCL: `1795-1801`）。

どちらの経路も設定内容は stderr の `strata prefill: peer GPU ...` 行に出ます。compact 時は `compact group buffers` が表示され、peer の prompt 実行後には `strata prefill timing (peer GPU, ms): ... rows/layer ... of ... cap ... over the cap ...` が出ます（CUDA/HIP: `1800-1812,4183-4189`; SYCL: `1814-1832,4648-4654`）。非 compact の場合に上限を超えた行があると `over the cap` が増えます。

関連する注意点として、両 backend の `set_peer()` は `STRATA_PF_PEER_OUT_PIPE` を読む時点で `PeerPrefill::compact` の初期値 `true` を参照し、その後で `STRATA_PF_PEER_COMPACT` を反映します。そのため `STRATA_PF_PEER_OUT_PIPE=0` でも `out_pipe` は true のままで、compact を無効にしてもこの呼び出し順では group 出力コピーの pipeline は無効になりません（CUDA/HIP: `src/prefill/prefill.cpp:597,1680-1687,1697-1699`; SYCL: `sycl/src/prefill/prefill.cpp:556,1719-1733,1753-1755`）。

## 根拠

- `src/prefill/prefill.cpp:593-603,1649-1709,1729-1735,3251-3258,3450-3471,4183-4189` — CUDA/HIP 系の設定判定、バッファ選択、row cap、group 処理とログ。
- `sycl/src/prefill/prefill.cpp:552-562,1689-1801,3370-3377,3535-3557,4648-4654` — SYCL の対応実装。no-P2P の扱いが異なる。
- `src/prefill/prefill.cpp:1544-1554`, `sycl/src/prefill/prefill.cpp:1531-1541` — stage helper は環境変数を読まず compact を固定。
- `docs/MULTI_GPU.md:85-99` は idle stage helper による prompt 分担を説明しますが、この環境変数の値や `--peer-device` の compact buffer 選択は説明していません。`docs/DETAILS.md` にもこの変数の記載は見つかりませんでした。
