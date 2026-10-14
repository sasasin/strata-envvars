# `STRATA_METAL_PARTIAL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal decode window の GDN 状態更新を部分 commit 方式に切り替えます。有効時、head を持つ複数 token の検証窓は最初の行の GDN 状態と convolution history を窓の実行中に in-place で確定し、後の `commit(n_keep)` では採用 prefix の残り `n_keep - 1` 行だけを畳み込みます。無効時は窓の実行中に状態を書かず、commit 時に `n_keep` 行を畳み込みます。

これは Metal 実装の `Window` にある分岐です。CUDA/HIP/SYCL の verifier や外部ライブラリの挙動を制御しません。`docs/MAC.md` は測定した decode variant として `--spec 2` に言及しますが、実装側に `--spec 2` の値を検査する条件はなく、複数 token の Metal 窓で分岐します。

## 値と判定

`Window` のメンバー初期化時に `getenv("STRATA_METAL_PARTIAL")` の値全体を文字列 `"1"` と比較します。数値変換や前方一致ではありません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `01`, `10`, `true`, ` 1`, `1 `、その他 | 無効 |

この値は `Window` オブジェクトごとに構築時に読み取られます。Metal engine はプロセス内で `Window` を一つ保持し、初回作成後はそれを再利用するため、実行中に環境を書き換えても既存 object には反映されません。object を破棄して作り直した場合は再評価されます。CLI 引数や設定ファイルによる上書きは見つかりません。

## 有効になる条件

- Metal backend (`STRATA_GPU_METAL`) の verifier が `metal_engine::window_*` に処理を渡す経路で使われます。
- `Tn > 1` の窓で GDN 部分 commit の差が生じます。1 token 窓は既存どおり GDN kernel がその token の終了時に状態を確定し、`commit()` のこの処理も `last_T_ > 1` の場合だけ実行されます。
- `head` を持つ窓では kernel に `0x100 | 1` を渡し、GDN kernel が窓の全 token の出力を計算しながら最初の token の後で GDN state と convolution history を書き戻します。
- `head` を持たない窓では kernel に `1` を渡し、その窓の全 token 後に状態を確定します。これは prompt の headless 窓についての実装コメントと一致します。後続の `commit()` で全行が採用されない場合は `metal window: a prompt window commits all its rows` で失敗します。

## 実行時の詳細

`Window::layer()` は各 GDN layer で、窓サイズが 1 なら `cm = 1`、部分 commit が無効なら複数 token 窓で `cm = 0`、有効なら head の有無に応じて `cm = 0x101` または `cm = 1` を組み立てます。`gdn_step` の契約では `0` は状態を書かない検証、`1` は最後の token の後に状態を確定、`0x100 | k` は最初の `k` token の後に状態を確定する指定です。ここでは `k = 1` です。

窓の完了時、有効なら history ping-pong の index `hp_` を切り替えます。後続の `Window::commit(n_keep)` は head 窓について `nf = n_keep - 1` を選び、`nf > 0` のときその残り行をすぐ fold するか、`STRATA_METAL_LAZY_FOLD` の既定動作により次窓の先頭まで `pend_fold_` に保留します。無効時は `nf = n_keep` です。headless 窓では既に全行を実行中に確定するため、`n_keep == last_T_` を要求し、追加 fold は行いません。

この環境変数専用のログ、警告、値エラーはありません。`docs/MAC.md` の switch 表は `STRATA_METAL_PARTIAL=1` を decode variant として挙げ、「同じ token で、この環境では速くなかった」と記載しています。実装コメントは M5 Max の `--spec 2` 測定で 0.3–0.8% 遅く、各窓での in-place state write のコストが、draft を一つも採用しない場合に省ける fold を上回ったという説明です。これは資料に記載された条件の測定値であり、他環境の速度を示すものではありません。

## 根拠

- `metal/src/engine/window.cpp:230-235` — 部分 commit の設計コメントと値の完全一致判定。
- `metal/src/engine/window.cpp:2455-2471` — プロセス内で一つの `Window` を作成・保持・破棄する lifecycle。
- `metal/src/engine/window.cpp:657-688` — token 数と `partial_` / `win_head_` から GDN commit mode を構成。
- `metal/kernels/gdn.metal:22-24,70,150-158` — commit mode の解釈と state/history の書き戻し箇所。
- `metal/src/engine/window.cpp:1319-1334,1442-1469` — 窓完了後の history index と採用 prefix の fold。
- `src/core/verify.cpp:70-78,577-581,2235-2241,2645-2648` — Metal build で verifier の init/run/commit を Metal window へ委譲。
- `docs/MAC.md:183-194` — switch 表と同じ token / 測定環境での位置づけ。
