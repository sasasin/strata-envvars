# `STRATA_PF_PEER_GATHER`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

P2P 接続を使えない peer GPU の prompt 処理で、peer が計算した expert 出力を token ごとの重み付き和へまとめる方法を選びます。有効時は各 MMQ expert group の出力行を一度の gather kernel で token ごとの和へ加算します。無効時は expert ごとに scatter-add kernel を呼びます。どちらも peer 側で集約してから、token ごとの和を mapped host memory 経由で primary GPU に返す経路です。

## 値と判定

`Prefill::set_peer()` 内で `std::getenv()` と `std::atoi()` を使い、結果が 0 かどうかを判定します。変数が未設定なら gather は有効です。

| 環境変数の状態 | `gather` |
|---|---|
| 未設定 | 有効（既定値） |
| `1`、`-1`、`2` など、`atoi` が 0 以外を返す値 | 有効 |
| `0`、空文字、数字で始まらない文字列 | 無効 |
| 数字の後ろに文字が続く値（例: `1abc`） | 数字部分で判定され、有効 |

`atoi` は先頭の空白と符号を許し、数字列の後ろは判定に使いません。したがって文字列全体の妥当性検査ではありません。設定変更は `set_peer()` が次に呼ばれたときに反映されます。層ごと・token ごとに再読込する処理や、環境変数自体への書き戻しはありません。

根拠: `src/prefill/prefill.cpp:1741-1755`。

## 有効になる条件

この変数を読むのは、peer GPU が有効で、次の条件を満たす経路に限られます。

- P2P が使えず、mapped host memory を通る経路である。`STRATA_PF_PEER_HOST=0`（`atoi` の結果が 0）なら `set_peer()` は peer 設定を拒否するため、この処理に進みません。
- prompt の MMQ 経路が利用可能である。MMQ が使えなければ `set_peer()` は失敗します。
- no-P2P 時は compact group buffers が強制されます。`STRATA_PF_PEER_COMPACT` の値にかかわらず compact です。
- no-P2P かつ compact の場合、`STRATA_PF_PEER_SUMS` が未設定または `atoi` で非 0 なら token ごとの和を使います。`STRATA_PF_PEER_SUMS=0` 相当なら `STRATA_PF_PEER_GATHER` は読まれず、行を返す経路になります。

P2P が使える場合は `sums` が有効にならないため、この変数は読み取られず、peer 出力行の転送経路にも影響しません。通常の単一 GPU prompt 経路にも適用されません。別の layer-split stage-helper 経路では `set_stage_helper()` が peer buffers を結び付けますが、この変数を読む箇所はありません。

根拠: `src/prefill/prefill.cpp:1584-1647,1649-1656,1736-1755`。

## 実行時の詳細

`set_peer()` の初期化時に `gather` を決めます。有効なら GPU 側の `adds` 領域を確保し、host route の場合は対応する pinned `host_adds` 領域も確保します。容量は `3 * cap_rows + 2 * n_expert + 64` 個の `int32_t` です。割り当てに失敗すれば peer prompt buffers の初期化が失敗し、呼び出し元は prompt path を primary GPU に残します。

各 layer では、host 上で peer の各出力行に対応する routing pair から token ごとの行リストを作り、`adds` に `[token IDs | 各 token の開始位置 | 行 ID]` の形で転送します。各 expert group の出力計算後、`gather` が有効なら `peer_gather_add()` を一度呼び、その group に属する各 token の行を routing weight (`wk[pair[r]]`) で重み付けして `P.sum` に加えます。無効なら group 内の expert ごとに `peer_scatter_add()` を呼びます。その後の和の返送はどちらも mapped host memory 経由で、FP16 または FP32 です。転送精度は別変数 `STRATA_PF_PEER_F16` と `N % 8 == 0` の条件で決まり、この変数は精度を切り替えません。

この選択による性能差や数値差の測定は、調査対象ソースおよび確認した `docs/DETAILS.md` の記述からは確認できません。該当する環境変数名を含む資料上の説明も見つかりません。

根拠: `src/prefill/prefill.cpp:1745-1755,1777-1791,3482-3516,3575-3585,3658-3667`; `src/prefill/kernels.cu:2077-2085,2101-2115,2136-2142`。

## 根拠

- `src/program/generate.cpp:7368-7373` — `--peer-prefill-rows` が有効で peer GPU がある場合に、prompt path の `set_peer()` を呼び出す。
- `src/prefill/prefill.cpp:1649-1656` — P2P 可否、`STRATA_PF_PEER_HOST`、MMQ 条件による peer 設定可否。
- `src/prefill/prefill.cpp:1736-1755` — no-P2P compact route における sums と gather の既定値・読み取り。
- `src/prefill/prefill.cpp:3482-3516,3575-3585` — group の token/row table 作成と gather/scatter の分岐。
- `src/prefill/kernels.cu:2077-2085,2101-2115,2136-2142` — scatter/gather の重み付き加算処理と CUDA kernel 起動。
