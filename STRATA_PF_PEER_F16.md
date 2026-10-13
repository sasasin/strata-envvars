# `STRATA_PF_PEER_F16`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリや GPU ドライバーが読む環境変数の動作は含めない。

## 役割

P2P 接続のない GPU peer を使う prompt prefill で、peer が計算した expert の weighted sum を mapped host memory 経由で返すときの転送形式を FP16 にします。FP32 の sum を FP16 に丸めてから host に転送し、primary GPU で FP32 に戻して local expert の結果と合成します。

この選択は戻り値だけでなく、primary から peer へ送る activation にも適用されます。FP16 が有効な場合は `mixed_h`（`mixed` の half 形式）を host へコピーし、peer 上で FP32 に戻してから expert 計算に使います。したがって、FP16 経路では peer が受け取る activation も FP16 精度です。関連箇所: `src/prefill/prefill.cpp:3410-3427,3660-3665,3943-3946`、`src/prefill/kernels.cu:2116-2127`。

## 値と判定

`Prefill::set_peer()` の初期化時に `std::getenv()` で値を読み、`std::atoi(v) != 0` で判定します。`atoi` は数値文字列全体の厳密な検証ではなく、先頭の空白と符号の後から数値部分を読みます。空文字・数値で始まらない文字列・`0` で始まる値は 0 になり無効、非ゼロの整数として読める値は有効です（例: `1`, `-1`, `2tail`）。未設定は既定で有効です。ただし `N % 8 != 0` のときは、値が有効でも実装上 FP16 を選びません。

| 値 | `N % 8 == 0` のとき | `N % 8 != 0` のとき |
|---|---|---|
| 未設定 | 有効 | 無効（FP32 経路） |
| `atoi` の結果が非 0 | 有効 | 無効（FP32 経路） |
| `atoi` の結果が 0 | 無効 | 無効 |

根拠: `src/prefill/prefill.cpp:1741-1744`。設定を読む箇所はこの一箇所で、各 peer prefill の `set_peer()` 初期化時に `pp->f16` に保存します。リクエスト単位では読み直しません。

## 有効になる条件

この変数が効くには、peer prompt prefill の host route と weighted-sum 経路が選ばれる必要があります。

- `--peer-device` が有効で、`--peer-prefill-rows` が 0 ではなく、peer が有効であること。serve の初期化は `peer.valid()` と `o.peer_prefill_rows != 0` のとき `set_peer()` を呼びます（`src/program/generate.cpp:7368-7373`）。
- peer 間の P2P が使えないこと。`STRATA_PF_PEER_HOST=0` 相当で host route が拒否されると `set_peer()` はエラーを返し、呼び出し元は prompt path を primary GPU に残します（`src/prefill/prefill.cpp:1649-1656`, `src/program/generate.cpp:7370-7373`）。
- MMQ prompt path が有効であること。`mmq_plan().any` が偽なら `set_peer()` は失敗します（`src/prefill/prefill.cpp:1656-1657`）。
- host route では `compact` が強制的に有効です（`!pp->p2p` の場合。`src/prefill/prefill.cpp:1697-1699`）。この経路で `STRATA_PF_PEER_SUMS` が未設定または `atoi` 非 0 なら weighted sums が有効になり、そこで初めて `STRATA_PF_PEER_F16` が参照されます（`src/prefill/prefill.cpp:1736-1746`）。`STRATA_PF_PEER_SUMS=0` なら peer の各 row を FP32 で返す経路になり、この変数は使われません。
- モデル幅 `N` は 8 の倍数である必要があります。そうでない場合は `pp->f16` が偽となり FP32 に fallback します（`src/prefill/prefill.cpp:1742-1744`）。

P2P が利用できる経路では `pp->sums` は設定されず、peer 結果は P2P で row 単位に戻ります。そのため、この変数による FP16 化は行われません（`src/prefill/prefill.cpp:1736-1740,3587-3595,3650-3655`）。また SYCL 側の `sycl/src/prefill/prefill.cpp` にはこの変数の読み取りがなく、今回確認した SYCL 実装にはこの切替はありません。

## 実行時の詳細

`pp->f16` が真の場合、初期化時に peer device 用 `sum16` と、host route 用 mapped pinned buffers `host_x16` / `host_sum16` を確保します。確保失敗時は peer の buffers または host route の pinned buffers に関するエラーとなり、peer prompt path の設定に失敗します（`src/prefill/prefill.cpp:1741-1745,1767-1797,1800-1803`）。初期化ログには `, no P2P: through mapped host memory in FP16, one weighted sum per token back` と出ます（`src/prefill/prefill.cpp:1804-1811`）。

実行時は primary が `mixed_h` を mapped host buffer にコピーし、peer が FP16-to-FP32 変換 kernel で `P.mixed` に展開して MMQ 計算へ渡します。peer の行ごとの weighted accumulation 自体は FP32 の `P.sum` で行い、戻す直前に `sums_to_f16()` が各要素を half に変換します。primary はイベント待ちの後 `moe_combine_peer16()` を使い、FP16 sum を half-to-float 変換して local rows の weighted sum と足し合わせ、shared expert の寄与も加えます（`src/prefill/prefill.cpp:3410-3427,3575-3585,3658-3667,3938-3948`; `src/prefill/kernels.cu:2086-2099,2116-2127,2143-2152`）。

## 文書との照合

`docs/MULTI_GPU.md:85-97` は P2P なしの mapped-host peer prefill と、その対象条件や測定例を説明していますが、`STRATA_PF_PEER_F16` の値判定・FP16 転送・数値精度の影響は記述していません。`docs/SECOND_GPU.md:131-170` は `--peer-device` の一般的な P2P 経路を説明しています。性能値や出力の同一性について、この環境変数の FP16 経路に固有の測定根拠は確認できなかったため記載していません。

## 根拠

- `src/prefill/prefill.cpp:640-658` — weighted-sum mode と `f16` の状態。
- `src/prefill/prefill.cpp:1649-1657,1695-1700,1736-1755` — peer 初期化、host route、適用条件、値の判定。
- `src/prefill/prefill.cpp:1767-1812` — host buffers、初期化エラーとログ。
- `src/prefill/prefill.cpp:3401-3427,3575-3585,3658-3667,3938-3948` — 入出力転送と合成の呼び出し。
- `src/prefill/kernels.cu:2086-2099,2116-2127,2143-2152` — FP16 sum の変換と combine。
- `src/program/generate.cpp:7368-7373` — serve の peer prefill 初期化と失敗時の扱い。
- `docs/MULTI_GPU.md:85-97`, `docs/SECOND_GPU.md:131-170` — 関連する設計説明との照合。
