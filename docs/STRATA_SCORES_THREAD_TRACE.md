# `STRATA_SCORES_THREAD_TRACE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドの QSA prompt block scorer が thread-per-query kernel を実際に選んだとき、stderr に利用状況を示す行を出します。この変数自体は kernel の選択や計算結果を変えません。kernel の選択は主に `STRATA_SCORES_THREAD`、GPU 世代、バッチ条件で決まります。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_SCORES_THREAD_TRACE")` が null かどうかだけで判定されます。

| 状態 | 判定 |
|---|---|
| 未設定 | TRACE は無効（null） |
| 設定済みの任意の値 | TRACE は有効。`1`、`0`、空文字、その他の文字列を区別しない |

TRACE が無効でも `STRATA_SCORES_THREAD` が未設定なら、thread scorer が選ばれた際にログを出します。`STRATA_SCORES_THREAD` が明示設定されている場合は、TRACE が設定されているときに限りログを出します。

## 有効になる条件

この読み取りは `src/kernels/cuda/qsa_select.cu` の `__HIPCC__` 分岐にあります。CUDA ビルドではこの TRACE 判定を通りません。

ログを出すには、thread scorer の選択条件も満たす必要があります。

- `STRATA_SCORES_THREAD` は unset なら `-1`、設定済みなら `atoi` の結果が厳密に `1` のときだけ `1`、それ以外は `0` と判定されます。したがって gfx12 では unset が既定 ON、明示設定値は `atoi(value) == 1` の場合だけ ON です。gfx1100 は `1` のときだけ ON、それ以外は OFF です。
- GPU が gfx12 か、`STRATA_SCORES_THREAD` が上記判定で `1` となる gfx1100。
- `active_blocks` が 16,385 以上で、`max_blocks` 以下。
- query 数 `nq` が 64 以上。
- `STRATA_SCORES_THREAD=0` などで scorer が無効化されていない。

そのため TRACE を設定しただけでは scorer は有効にならず、条件外の短い prompt や decode などではこのログも出ません。HIP scorer の適用条件は `docs/AMD_HIP.md` にも説明されています。

## 実行時の詳細

`qsa_block_scores()` が上記の条件で thread scorer に入ると、まずログ判定を行い、その後 `block_scores_thread_kernel` と `block_scores_tail_kernel` を launch します。ログは次の文字列で、`nq`、live extent の `active_blocks`、容量 `max_blocks` を含みます。

```text
qsa exact thread: the prompt's block scorer runs as the four-lanes-per-query kernel (nq=... active_blocks=... capacity=...; the same scores bit for bit; STRATA_SCORES_THREAD=0 turns it off)
```

`logged` は `static thread_local` なので、ログは scorer を実際に使った各 host thread につき最大1回です。TRACE の getenv 判定は候補 kernel に入るたびに行いますが、既にその thread でログ済みなら再出力しません。ログ判定は kernel 起動より前です。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1747-1774` — HIP 用の scorer 選択、active block/query 条件、TRACE による stderr 出力、1 host thread あたり1回の抑制。
- `docs/AMD_HIP.md:307-319` — gfx1100 opt-in / gfx12 default の概要と、TRACE が scorer の engagement line を出す旨。
- `CMakeLists.txt:405-418` — 任意の HIP parity test の環境に `STRATA_SCORES_THREAD_TRACE=1` を設定する箇所。これはテスト設定であり、通常の engine 動作を定義する根拠にはしていない。
