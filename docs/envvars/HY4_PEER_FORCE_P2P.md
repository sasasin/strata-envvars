# `HY4_PEER_FORCE_P2P`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の複数 GPU expert 配置で、Strata が通常なら安全性を理由に避ける GPU 間 P2P を試すための上書きです。値が `atoi` で非 0 になると、CUDA ビルドでは Linux の PCIe トポロジー判定による拒否を飛ばし、P2P プローブでは 64 KiB の往復コピーに対する 2.0 ms の時間上限を無視します。ただし、P2P の可否確認、両方向の peer access 設定、プローブ中の API 成功とデータ一致確認は残ります。利用できると判定された peer は実行時に `hipMemcpyPeerAsync` で転送し、それ以外は pinned host bounce 経路を使います（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:680-720,728-785,896-932`、`engine/src/hy4flash/run/hy4_graph.hip.h:3273-3302`）。

## 値と判定

2 箇所とも `getenv` の返り値を `atoi` に渡し、その結果が非 0 かを見ます。文字列全体の検証や `true` / `false` の認識はありません。`atoi` が先頭の符号付き十進数字列を変換するため、未設定・空文字・数字で始まらない文字列は 0 になり、数字の後ろの文字は判定に使われません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:681,783-785`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `HY4_CUDA || HY4_HIP_PEERS` が有効なビルド | 強制なし。通常のトポロジー判定と 2.0 ms 判定を適用 | `1`, `-1`, `2junk`（変換結果が非 0） | 空文字、`0`, `0anything`, `true`, `false`, `junk`（変換結果が 0） |
| それ以外のビルド | 読み取り箇所がコンパイル対象外 | 該当なし | 該当なし |

`atoi` のため、`+1` や先頭空白の後の `1` も非 0 になります。末尾の空白や文字列全体の妥当性は検査されません。整数として表現できない範囲の入力に対する値はこの実装で検査・定義されていません。`HY4_CUDA` は CUDA ビルドで 1、HIP 側では 0 とされ、HIP の `HY4_HIP_PEERS` は既定で 1 です（`engine/src/hy4flash/run/hy4_gpu.h:17-23,324-330`）。

## 有効になる条件

- expert 分割に peer GPU があり、モデルロードが tiered expert loading に進む必要があります。CLI は `--gpus` 等から `peer_devs` を設定し、モデル全体を単一 GPU にロードする経路ではこの変数の P2P 判定を通りません（`engine/src/hy4flash/run/hy4_main.hip.cpp:514-540,657-659`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1436,1486-1501`）。
- サーバーモードも `load_gpu_model` を呼ぶため、peer GPU を指定して tiered loading に進む場合は同じ判定を使います（`engine/src/hy4flash/run/hy4_serve.hip.h:268-296`）。
- ビルド時に `HY4_CUDA || HY4_HIP_PEERS` が必要です。標準定義では CUDA または HIP の peer 実装が対象になります（`engine/src/hy4flash/run/hy4_gpu.h:17-23,324-330`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:676,877`）。
- `HY4_PEER_NO_P2P` が設定され、`atoi` の結果が非 0 の場合、peer 判定ブロック自体を通らないため、この変数では P2P を強制できません。`HY4_PEER_NO_P2P` が未設定または 0 でも、双方向の `hipDeviceCanAccessPeer` が成功して両方とも利用可を返す必要があります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-899`）。
- peer access の有効化が両方向で成功（または既に有効）し、プローブが API エラーやデータ不一致で失敗しないことが必要です。この環境変数が省略するのはトポロジー拒否とプローブの時間上限で、これらの検証は省略しません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:908-932,728-785`）。
- CUDA ビルドでは、変数が 0 のとき Linux 上で native P2P atomic が確認できず、PCI sysfs から両 GPU の共通 PCIe bridge が見つからない場合、トポロジー判定は P2P を拒否します。非 Linux の CUDA ビルドではこの sysfs による拒否処理はありません。HIP ビルドではこの関数内の CUDA 固有判定はコンパイルされず、トポロジー関数は許可を返します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:680-720`）。
- `load_gpu_model` の distributed expert shard 経路は tiered loading より先に戻るため、この P2P 判定は通りません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1409,1486-1501`）。

## 実行時の詳細

値はプロセス起動時に一度保存されるのではなく、tiered loading 中に peer ごとに呼ばれる `p2p_topology_safe` と、peer access 設定後の `p2p_probe_pair` でそれぞれ `getenv` されます。関数内 `static` cache はありません。モデルロード時に判定が終わると、その結果が `g.peers[p].can_p2p` に保存され、後続の推論ではこの状態を使います（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:680-681,783-785,886-932,1145-1154`）。

P2P が許可されれば、peer GPU への activation・expert index・weight の入力と部分出力を peer copy で転送します。許可されなければ pinned host buffer を確保して host 経由で転送します。実行時の `can_p2p` 分岐は同じです（`engine/src/hy4flash/run/hy4_graph.hip.h:1503-1521,3273-3302,3327-3368`）。

## ログと測定値

トポロジー判定が拒否した場合は stderr に次のメッセージを出します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:900-906`）。

```text
hy4: gpu %d <-> gpu %d: GPUs sit behind a PCIe host bridge (PHB/SYS, no shared PCIe switch or NVLink); using portable host-pinned bounce (HY4_PEER_FORCE_P2P=1 overrides)
```

peer access 自体が有効でもプローブが失敗すると、stderr に失敗理由と測定時間を出し、両方向の peer access を無効化して host bounce に戻します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:919-930`）。

```text
hy4: gpu %d <-> gpu %d: peer access enabled but round-trip async P2P probe failed (%.2f ms; PCIe host bridge / ACS); falling back to portable host-pinned bounce
```

P2P 判定の結果は、peer expert が実際に割り当てられて runner が初期化された際、次の stderr ログにカウンタとして現れます（`engine/src/hy4flash/run/hy4_graph.hip.h:1503-1518,1545-1549`）。Strata の資料にこの変数を使った測定値は見つかりませんでした。

```text
[runner] multi-GPU expert-parallel active across %zu GPUs (p2p=%d/%zu, bounce=%zu)\n
```

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:676-720` — ビルド条件と CUDA 時のトポロジー判定、環境変数による拒否の上書き。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:728-785` — 双方向 async P2P コピーによるプローブ、データ一致・時間判定、2 回目の読み取り。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:876-935,1145-1154` — P2P の前提、peer access 設定、失敗時 fallback、判定結果の保存。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1501` — distributed shard / full-load / tiered-load による適用範囲。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1503-1549,3273-3302,3327-3368` — 結果ログと推論時の P2P / host bounce 転送。
- `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-330` — CUDA / HIP peer build macro の定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:514-540,657-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:268-296` — CLI とサーバーから共有のモデルロードへ入る経路。
