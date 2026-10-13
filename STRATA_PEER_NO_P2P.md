# `STRATA_PEER_NO_P2P`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--peer-device N` で作る第2 GPU の expert tier について、CUDA が報告する device 0 と peer device 間の P2P 可否にかかわらず、Strata 内部では P2P なしとして扱わせる診断用フックです。`PeerExperts::open()` が双方向の `cudaDeviceCanAccessPeer()` を呼んだ後、この変数が非ゼロなら一方向の可否 `a` を 0 にし、`p2p_` を false にします。そのため peer access の有効化処理は行われません。

## 値と判定

値は `std::atoi()` で整数変換され、変換結果が 0 かどうかだけを判定します。文字列全体の検証はありません。

| 値 | 効果 |
|---|---|
| unset | 強制なし。CUDA の双方向 P2P 可否を使う |
| 空文字、数値に変換できない文字列、先頭の数値部分が 0 | 強制なし（`atoi` が 0 を返す） |
| `1`、その他 `atoi` が非ゼロを返す文字列 | P2P なしを強制する。例: `-1`, `2`, `1tail` |

先頭空白や符号は `atoi` の変換規則に従います。大文字小文字の比較はありません。値は `open()` のたびに読みます（`static` cache ではありません）。したがって、同一プロセス内でも次回の `open()` より前に環境を変更すれば、その呼び出しには新しい値が使われます。

根拠: `src/core/peer_experts.cpp:81-83,97-110`。

## 有効になる条件

- `strata generate` の `--peer-device N` を指定し、expert profile と expert cache が有効な場合に `PeerExperts::open()` が呼ばれます。条件不足なら `generate.cpp` がエラーを出して終了し、この変数の判定には到達しません。
- この変数は `cudaDeviceCanAccessPeer()` の戻り値そのものを変更せず、CUDA の device capability を変更しません。Strata が `p2p_` に保存する結果だけを強制的に false にします。
- unset または変換結果 0 の場合は、device 0→peer と peer→device 0 の双方が対応するときだけ peer access の有効化を試みます。有効化のどちらかが失敗した場合も `p2p_` は false です。
- 値が非ゼロでも第2 GPU の expert tier 自体を無効にはしません。decode 用 `PeerExperts::launch()` は `p2p_` を参照せず、peer 用の計算を続けます。
- prompt peer 経路が有効で `--peer-prefill-rows` が 0 でないとき、`Prefill::set_peer()` が `p2p_` を参照します。P2P なしなら既定で mapped pinned host memory 経由の経路を選び、compact 経路を強制します。別変数 `STRATA_PF_PEER_HOST` が非ゼロでない値なら set-up を拒み、呼び出し側は prompt path を primary GPU に残します。

根拠: `src/program/generate.cpp:5450-5459,7298-7303`; `src/core/peer_experts.cpp:97-110,188-254`; `src/prefill/prefill.cpp:1643-1697`。

## 実行時の詳細

`PeerExperts::open()` は device 0 と peer device の双方向アクセス可否を調べます。`STRATA_PEER_NO_P2P` が非ゼロなら `a = 0` とし、`p2p_ = a && b` は false になります。false のとき `cudaDeviceEnablePeerAccess()` の2回の呼び出しを飛ばします。既定では、両方向が可能な場合に device 0 から peer、peer から device 0 の順に有効化し、既に有効だった場合はその CUDA error をクリアして成功扱いにします。

prompt 経路では `p2p_ == false` のとき、peer の入力活性と結果行を mapped pinned host buffers 経由で扱います。`STRATA_PF_PEER_HOST` が unset または非ゼロならこの経路を許可し、初期化ログに `no P2P: through mapped host memory`（条件により FP16 や weighted sum の説明を含む）が出ます。`STRATA_PF_PEER_HOST` が 0 または `atoi` で 0 になる値なら `Prefill::set_peer()` は `prefill peer: the two GPUs cannot access each other (no P2P)` を返し、`generate.cpp` は `- the prompt path stays on the primary GPU` を stderr に出して peer prompt 経路を使いません。

`docs/SECOND_GPU.md` は peer tier が通常 NVLink または P2P 経由で活性と結果を移すこと、peer tier の要件を説明しています。`docs/MULTI_GPU.md` は別の layer-split helper が P2P なしで mapped host memory を使う経路と、その構成の測定値を説明していますが、`STRATA_PEER_NO_P2P` の効果や測定値としては記載していません。環境変数を強制設定した場合の挙動は、調査対象 HEAD のソースから確認したものです。

根拠: `src/core/peer_experts.cpp:97-110,227-254`; `src/prefill/prefill.cpp:1643-1667,1691-1697,1797-1806`; `src/program/generate.cpp:7298-7303`; `docs/SECOND_GPU.md:131-173`; `docs/MULTI_GPU.md:85-97`。
