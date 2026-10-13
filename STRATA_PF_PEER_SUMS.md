# `STRATA_PF_PEER_SUMS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

CUDA の prompt prefill で、P2P 接続できない peer GPU が計算した expert の結果を、expert ごとの行列で主 GPU に戻す代わりに、token ごとの重み付き合計にまとめてから戻すかを選ぶ。まとめると戻すデータは `peer rows × N` 要素から `T × N` 要素になる。これは Strata の `--peer-device` による peer prefill のうち、P2P が使えず mapped host memory を経由する経路だけに関係する。

## 値と判定

| 環境変数の状態 | `pp->sums` | 動作 |
|---|---:|---|
| 未設定 | ON | token ごとの重み付き合計を戻す |
| `atoi` の結果が 0 | OFF | peer の結果行を戻す |
| `atoi` の結果が非 0 | ON | token ごとの重み付き合計を戻す |

実装は `std::atoi` を使うため、文字列全体の厳密な数値検査ではない。空文字、数字で始まらない値、`"0"` は 0 になり OFF。`"1"` や負の非ゼロ値は非 0 になり ON。数値の後ろの文字列も `atoi` の変換結果には影響しない。無効値を検出したり警告を出したりする処理はない。

## 有効になる条件

- CUDA の `Prefill::set_peer` が有効な peer を受け取り、peer prefill が構成されること。呼び出し元では `peer` が有効で、`--peer-prefill-rows` 相当の値が 0 でない場合に設定する。
- CUDA 実装では P2P がないとき `STRATA_PF_PEER_HOST` が 0 でない（または未設定）であること。無効なら `set_peer` は失敗し、`strata serve` は prompt path を primary GPU に残す。
- MMQ prompt path が利用可能であること。peer prefill 自体が MMQ を必要とする。
- `sums` の読み取りは `!pp->p2p && pp->compact` の場合に限られる。compact は既定で有効であり、P2P がない場合は `STRATA_PF_PEER_COMPACT=0` でも強制的に有効になる。P2P がある場合、この変数は読まれず結果行を P2P で戻す。
- SYCL の `Prefill::set_peer` は P2P がない peer を拒否するため、この変数による mapped-host の sums 経路は SYCL では使われない。

## 実行時の詳細

`set_peer` の peer buffer 構成時に値を読み、`PeerPrefill` に保存する。token/chunk ごとには再読しない。したがって、その `PeerPrefill` を使っている間にプロセス環境を変えても設定は切り替わらない。初期化に失敗して作り直す場合や、別の `set_peer` を呼ぶ場合は、その構成時の環境値が使われる。

ON の場合、primary GPU から routing weight と peer rows の routing pair を host buffer 経由で peer GPU に渡し、peer GPU 側で row と routing weight を掛けて token ごとに加算する。group 単位の gather 加算が既定で、`STRATA_PF_PEER_GATHER=0` なら expert ごとの scatter 加算を使う。合計値を host memory にコピーし、primary GPU は local expert の合計に peer の合計と shared expert の結果を加えて MoE 出力を作る。`STRATA_PF_PEER_F16` が有効なら、合計値を FP16 に変換して転送し、primary 側で float に戻してから combine する。これらの関連変数は本書の対象外だが、転送形式や加算方法に影響する。

OFF の場合、peer の結果行を mapped host buffer にコピーし、primary GPU が `Dm` に読み込んで通常の MoE combine に使う。どちらの経路でも mapped host buffer の確保に失敗すると `set_peer` は失敗し、コード上のエラーには pinned buffer 不足が記載される。

構成時には stderr に peer GPU の処理内容を出す。sums 有効時は `no P2P: through mapped host memory` と、FP16 使用時には `in FP16`、および `one weighted sum per token back` が表示される。sums 無効時は `no P2P: through mapped host memory` のみとなる。`docs/DETAILS.md` にこの環境変数の個別説明は見つからず、効果と既定値は以下の実装に基づく。

## 根拠

- `src/prefill/prefill.cpp:640-658`: sums mode の目的、既定値の説明、peer buffer 状態。
- `src/prefill/prefill.cpp:1649-1672`: peer 経路の設定、no-P2P 時の host-route 条件と MMQ 条件。
- `src/prefill/prefill.cpp:1697-1699,1736-1755`: compact 条件、`STRATA_PF_PEER_SUMS` の唯一の読み取り箇所、`atoi` 判定、および関連 buffer の確保。
- `src/prefill/prefill.cpp:1767-1797`: host-route buffer の確保と失敗時のエラー。
- `src/prefill/prefill.cpp:1803-1812`: 構成時の stderr 表示。
- `src/prefill/prefill.cpp:3410-3449,3575-3595,3658-3674,3938-3948`: routing data の転送、sum または rows の返送、primary 側の combine。
- `src/prefill/kernels.cu:2062-2114,2130-2163`: peer の重み付き加算と primary 側の合成カーネル。
- `src/program/generate.cpp:7368-7373`: peer prefill 設定の呼び出しと失敗時の fallback。
- `sycl/src/prefill/prefill.cpp:1689-1695`: SYCL 実装は no-P2P peer を拒否する。
