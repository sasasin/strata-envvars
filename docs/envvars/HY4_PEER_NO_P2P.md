# `HY4_PEER_NO_P2P`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の tiered expert loading で peer GPU との P2P access 判定を飛ばし、peer GPU 用の入出力を host-pinned bounce buffer 経由にします。peer GPU に expert を配置することや multi-GPU expert-parallel 自体は無効化しません。値の判定は `load_experts_tiered` 内で `peer_p2p` を作るときに行われます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-801,876-899`）。

## 値と判定

`getenv` が非 null の場合に `atoi` の結果が 0 以外なら P2P を強制的に使わない判定になります。文字列全体の検証はなく、数値として読めた先頭部分を使います。従って `1`、`2`、`-1`、` 1tail` は有効、`0`、`0tail`、`true`、空文字は無効です。数値に変換できない文字列も `atoi` の結果が 0 なので無効です。unset の既定値も false（P2P 判定を妨げない）です。`atoi` の値域検証や overflow 対策はありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-899`）。

| 条件（build など） | unset | P2P を無効にする値 | 無効化しない値 |
|---|---|---|---|
| `HY4_CUDA || HY4_HIP_PEERS` が真の build で tiered loading を実行 | P2P 判定を許可 | `atoi(value) != 0`（例: `1`, `-1`, `2`） | `atoi(value) == 0`（例: `0`, `0tail`, `true`, 空文字） |
| 上記 macro 条件が偽 | この読み取りコード自体がない | 該当なし | 該当なし |

この値と CLI 引数や別の環境変数との優先順位はありません。`HY4_PEER_FORCE_P2P` は別に `p2p_probe_pair` の所要時間判定へ使われますが、`HY4_PEER_NO_P2P` が非ゼロなら P2P 判定ブロックに入らないため、その値でこの設定を覆せません（同ファイル `:783-785,897-899`）。

## 有効になる条件

- `load_gpu_model` が expert を tiered loading する経路に入り、`load_experts_tiered` が呼ばれること。通常は expert 全体を一括配置できず tiered loading へ進む場合です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1486-1501`）。
- 実際に peer GPU による挙動差を生むには、`--gpus` または `--devices` で primary GPU 以外の device を選び、その peer に expert が配置される必要があります。CLI の device 一覧から `peer_devs` を作り、モデルへ渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:401-405,514-541,649-659`）。
- 対応する peer 機能が build に含まれること。ソースでは CUDA build または `HY4_HIP_PEERS` build の条件で判定・転送処理を含めます。HIP 側の `HY4_HIP_PEERS` は明示定義がない場合 `1` です（`engine/src/hy4flash/run/hy4_gpu.h:324-330`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-878`）。
- 値が非ゼロなら、GPU 間で双方向の `hipDeviceCanAccessPeer` を問い合わせる条件式を短絡し、`peer_p2p` は初期値 `false` のままです。非ゼロでない場合も、peer access 不可、topology 判定不適合、peer access 有効化失敗、P2P probe の失敗時には P2P にならず host bounce へ進みます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:876-933`）。

## 実行時の詳細

値は `load_experts_tiered` の呼び出しごとに評価され、static cache はありません。通常はモデル load 中の一回ですが、pinned host arena allocation に失敗して CPU expert mode で再試行する経路では同関数が再度呼ばれます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-878,1160-1172`）。実行中の環境変更を追跡する処理はありません。

`peer_p2p[p]` は GPU model の `g.peers[p].can_p2p` に渡されます。peer run の初期化では false の peer にだけ pinned host buffer を割り当てます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1145-1155`; `engine/src/hy4flash/run/hy4_graph.hip.h:1503-1520`）。各 layer の peer 計算では P2P の代わりに primary GPU から activation・index・weight を host 経由で peer GPU へ送り、peer の部分和を host 経由で primary GPU に戻して加算します（`engine/src/hy4flash/run/hy4_graph.hip.h:1126-1154,1161-1178`）。これらのコピーは `hipMemcpyAsync` で enqueue されます。

環境変数が非ゼロでも peer が指定されていない場合、peer loop は空で転送経路に差はありません。値は expert の配分量、他の GPU 上の計算、モデル選択を直接変更しません。

## ログと測定値

この変数専用の警告や設定ログはありません。expert-bearing peer run が作られると、stderr に `[runner] multi-GPU expert-parallel active across %zu GPUs (p2p=%d/%zu, bounce=%zu)` が出るため、P2P peer 数と bounce peer 数を確認できます（`engine/src/hy4flash/run/hy4_graph.hip.h:1505-1513,1545-1548`）。転送・allocation 時の HIP error は `HCK` 経由ですが、この変数専用のエラー文言や終了経路はありません（同ファイル `:1516-1524,1131-1152`）。測定値はありません。

`docs/AMD_HIP.md:218` も `HY4_PEER_NO_P2P=1` を host-pinned bounce への切替として説明しており、実装と一致します。ただし同じ実装の topology 警告文は `HY4_PEER_FORCE_P2P=1 overrides` と述べていますが、`p2p_topology_safe` が false の分岐ではその環境変数を確認せず bounce を選びます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:900-907`; force 変数を調べるのは `:783-785`）。これは対象変数の判定そのものには影響しません。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-801,876-899` — tiered loader、環境値の変換、peer 判定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:900-933,1145-1155` — topology/probe fallback と `can_p2p` の引き渡し。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1126-1154,1161-1178,1503-1524,1545-1548` — transfer fallback、bounce buffer、起動ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:401-405,514-541,649-659` — CLI device selection と peer device の受け渡し。
- `engine/src/hy4flash/run/hy4_gpu.h:324-330` — HIP peer build macro の既定値。
