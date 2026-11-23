# `HY4S_PEER_PINNED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL Hy4 peer GPU の転送経路を pinned-host bounce buffer に固定する切替用フック。peer GPU と primary GPU 間の P2P probe を始める前に環境変数の先頭文字を確認し、`'1'` なら probe を失敗扱いにして `p2p_ok=false` にする。その結果、peer GPU 自体や peer expert の配置は無効化せず、decode と prefill の入出力転送で GPU 間の直接コピー経路を使わず、host pinned buffer 経由の経路を選ぶ（`engine/src/hy4flash/sycl/sy_peer.h:139-179,231-258,432-478,483-559`）。

対象は SYCL の `SyPeerExperts` 実装であり、HIP/CUDA の peer 経路をこの変数が制御する読み取り箇所はない。通常の `strata-hy4-sycl` 実行と `--serve` はどちらも `setup_experts_unified()` を通して同じ peer helper を初期化する（`engine/src/hy4flash/sycl/sy_main.cpp:282-309`, `engine/src/hy4flash/sycl/sy_serve.h:259-285`, `engine/src/hy4flash/sycl/sy_graph.h:123-153`）。

## 値と判定

`probe_p2p()` が `std::getenv()` で取得し、値が存在し、かつ `force_pinned[0] == '1'` かだけを見る。文字列全体の比較や数値変換はしない。したがって空文字は設定済みでも無効、先頭が `1` なら後続文字を問わず有効で、大文字小文字や後続の空白は判定に影響しない（`engine/src/hy4flash/sycl/sy_peer.h:139-143`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全ての build | P2P probe を実施（対応 build・device 条件を満たす場合） | `1`, `10`, `1anything`（先頭文字が `1`） | 空文字, `0`, `true`, `True`, ` 1`, `01` |

## 有効になる条件

- peer device が実際に選ばれていること。SYCL runner は `HY4_GPUS` を初期値に使い、`--gpus` / `--devices` が指定されればその値で置き換える。peer 列挙は複数 device spec により行われる（`engine/src/hy4flash/sycl/sy_main.cpp:94,105-106,133-136,199-205`; `engine/src/hy4flash/sycl/sy_common.h:115-151`）。
- `setup_experts_unified()` に peer device が渡り、peer init に進むこと。peer 列が空なら初期化は呼ばれず、列挙 GPU が 2 台未満なら peer experts を無効にして戻る。また、peer 用 slot budget が 0 ならその device では probe しない（`engine/src/hy4flash/sycl/sy_graph.h:148-153`; `engine/src/hy4flash/sycl/sy_peer.h:184-194,231-257`）。
- 有効値は P2P 経路を抑止するが、peer expert の配置や演算を止めるものではない。P2P 拡張 macro `SYCL_EXT_ONEAPI_PEER_ACCESS` が未定義の場合や capability/probe が失敗した場合も、同じ `p2p_ok=false` の fallback となる（`engine/src/hy4flash/sycl/sy_peer.h:143-179,256-258`）。

## 実行時の詳細

peer queue の作成と budget 判定後、peer device ごとに `probe_p2p()` が一度呼ばれる。設定値が先頭 `1` なら直ちに `false` を返し、SYCL の peer capability 照会、peer access 有効化、16 byte の round-trip probe を行わない。その他の値では、build macro がある場合に両方向の peer access capability を調べ、有効化後に device allocation と両方向コピーで probe する。能力不足、allocation 失敗、データ不一致、例外は `false` となり、macro がなければ常に `false`（`engine/src/hy4flash/sycl/sy_peer.h:139-179`）。

probe 結果は `PeerDev::p2p_ok` に保存され、後続処理で環境変数を再読込しない。プロセス内で環境を書き換えても、すでに初期化済み peer の経路は変わらない。peer helper を破棄して再初期化すれば再評価される（`engine/src/hy4flash/sycl/sy_peer.h:52-60,109-137,231-258`）。

`p2p_ok=false` では decode 入力を host pinned `z_host_pinned` から peer device に送り、結果を `h_zout` に戻した後 primary GPU に転送する。prefill も primary GPU から `h_pf_z_` にコピーして peer device に送り、peer 結果を host buffer 経由で集約する。`p2p_ok=true` の peer では device-to-device 経路を使う（`engine/src/hy4flash/sycl/sy_peer.h:432-478,483-559`）。この変数を読む helper 内には、同じ設定を上書きする CLI 引数や別環境変数の分岐はない。

## ログと測定値

環境変数が有効であること自体を示す専用の警告・エラーは出さない。peer experts がロードされた場合、stderr の `[peer-sycl] loaded ...` 行に `describe()` の結果が付き、各 peer が `pinned` または `p2p` と表示されるため、選ばれた経路を確認できる（`engine/src/hy4flash/sycl/sy_peer.h:95-106,361-364`）。peer queue 作成例外時は `[peer-sycl] skipping GPU%d (%s): queue creation failed (%s)`、可視 GPU が 2 台未満のときは `multi-GPU peer experts disabled` が stderr に出る（同 `:190-194,240-245`）。

性能値の記載はない。この調査では build・GPU 実行・測定を行っていない。

## 根拠

- `engine/src/hy4flash/sycl/sy_peer.h:139-179` — 環境変数の読み取り、先頭文字判定、P2P probe と失敗時の戻り値。
- `engine/src/hy4flash/sycl/sy_peer.h:231-258` — peer queue ごとの probe 呼び出しと結果の保存。
- `engine/src/hy4flash/sycl/sy_peer.h:432-478,483-559` — decode/prefill の P2P と host pinned fallback。
- `engine/src/hy4flash/sycl/sy_graph.h:123-153` — 通常実行・serve 共通の peer 初期化条件。
- `engine/src/hy4flash/sycl/sy_main.cpp:94,105-106,133-136,199-205,282-309`; `engine/src/hy4flash/sycl/sy_serve.h:259-285` — peer device 選択と両実行モードからの初期化。
- `engine/src/hy4flash/sycl/sy_common.h:115-151` — GPU spec の解析。
