# `STRATA_PF_PEER_SUMS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

P2P を使えない peer GPU の prompt prefill で、peer が計算した expert の結果を主 GPU に返す形式を選ぶ。値が非ゼロ（または未設定）なら peer 側で routing weight を掛けた token ごとの和を作って返し、0 なら expert row ごとに返す。どちらも peer が担当する expert と計算結果自体は同じで、変わるのは host 経由で戻すデータの形式と主 GPU 側の combine 経路である（`engine/src/prefill/prefill.cpp:1387-1391, 3467-3471, 6883-6904, 6972-6980, 7617-7625`）。

変数を読むのは serve の prompt path 初期化から呼ばれる `Prefill::set_peer()` の CUDA peer tier 初期化だけである。CUDA device を使う `--peer-device` の prompt prefill 向けで、通常の単一 GPU 経路、peer tier を使わない実行、layer split の stage helper ではこの変数を読まない（`engine/src/prefill/prefill.cpp:3333-3339, 3467-3471`; `engine/src/program/generate.cpp:13146-13150`）。

## 値と判定

`std::getenv` で取得し、未設定なら `sums=true`、設定されていれば `std::atoi(v) != 0` を使う。文字列全体の検証や値域チェックはしない。`atoi` が先頭から整数に変換できる部分を読むため、空文字・数値で始まらない文字列・`0anything` は 0、`1anything` や `-1` は非ゼロになる。先頭空白と符号は `atoi` の整数変換に従う。大文字小文字の区別はなく、`true` / `false` は整数として読めずどちらも 0 扱いとなる（`engine/src/prefill/prefill.cpp:3467-3471`）。

| 条件 | unset | 和を返す値（例） | 行を返す値（例） |
|---|---|---|---|
| `set_peer()` が非 P2P の compact peer を初期化 | 和を返す | `1`, `2`, `-1`, `1tail` | `0`, 空文字, `true`, `0anything`, `abc` |
| P2P peer / peer prefill を使わない | 読み取りなし | 該当なし | 該当なし |

整数として表せないほど大きな数値に対する `atoi` の範囲外動作はこのコードで検査・処理されない。未設定時の既定は和モードで、CLI 引数による上書きはない（同: `3467-3471`; CLI の peer prefill 行数は `engine/src/program/generate.cpp:922-924, 4205-4209`）。

## 有効になる条件

- `--peer-device N`（`N >= 1`）で peer tier が開かれ、prompt peer の設定が実行されること。`--peer-prefill-rows 0` なら設定呼び出し自体が省かれる。行数の既定 `-1` は chunk × top-k の半分を使う（`engine/src/program/generate.cpp:918-924, 10211-10223, 13146-13150`）。
- 2 GPU 間で P2P が使えないこと。peer が有効でも P2P 経路なら `!pp->p2p` が偽となり、この変数を読み取らず row 転送経路を使う（`engine/src/prefill/prefill.cpp:3373-3376, 3467-3471`）。P2P 判定は `STRATA_PEER_NO_P2P` や peer access の確認・試験コピーで決まる（`engine/src/core/peer_experts.cpp:208-234`）。
- 非 P2P route が `STRATA_PF_PEER_HOST` で拒否されないこと。`STRATA_PF_PEER_HOST` が `0` に変換されると `set_peer()` は失敗し、呼び出し元は「prompt path stays on the primary GPU」と出して peer prompt 処理を取り下げる（`engine/src/prefill/prefill.cpp:3336-3339`; `engine/src/program/generate.cpp:13146-13153`）。
- compact buffer が使われること。非 P2P では `STRATA_PF_PEER_COMPACT=0` を指定しても `!pp->p2p` が真なので compact は強制される（`engine/src/prefill/prefill.cpp:3411-3415`）。
- 和モード内の転送型は `STRATA_PF_PEER_F16` と次元 `N` による。未設定または `atoi` 非ゼロかつ `N % 8 == 0` なら FP16、0 扱いまたは `N % 8 != 0` なら FP32。和を作る kernel は `STRATA_PF_PEER_GATHER` が未設定または非ゼロなら group gather、0 扱いなら expert row ごとの scatter になる（`engine/src/prefill/prefill.cpp:3472-3485, 6883-6893, 6972-6978`）。
- 対応する peer prompt kernel とモデル状態があること。`set_peer()` は対応層がない場合や NVFP4 expert の場合にエラーで断り、APR pack では警告を出して peer prompt を使わない（`engine/src/prefill/prefill.cpp:3340-3369`）。

## 実行時の詳細

`Prefill::set_peer()` が peer buffer を設定するたび、非 P2P かつ compact の場合に環境を読み、その `bool` を `PeerPrefill::sums` に保存する。static cache はなく、token/request ごとには読み直さない。prompt path の再初期化で `set_peer()` が再度呼ばれれば、その時点の値で再評価される（`engine/src/prefill/prefill.cpp:3333-3339, 3373-3377, 3467-3471`; `engine/src/program/generate.cpp:13101-13103, 13143-13150`）。

和モードでは主 GPU から routing weight と peer row の token/top-k 対応を host buffer に渡し、peer が和 buffer をゼロ初期化する。peer の各 expert row の結果に対応する routing weight を使い、`STRATA_PF_PEER_GATHER` の設定に応じて group gather または row scatter で token ごとの和を作る。和（`T × N`）を mapped host memory にコピーし、主 GPU は `moe_combine_peer()`（`STRATA_PF_PEER_F16` が有効な場合は `moe_combine_peer16()`）で主 GPU 側の expert 結果と合わせる（`engine/src/prefill/prefill.cpp:6621-6628, 6664-6669, 6883-6893, 6972-6980, 7617-7625`）。

行モードでは peer rows を mapped host memory の `host_rows` にコピーし、主 GPU がその rows を `Dm` に戻して通常の `moe_combine()` に渡す（同: `3522-3524, 6895-6904, 7617-7630`）。この変数は転送形式を切り替えるもので、CLI の peer row 配分を変更しない。

## ログと測定値

peer の初期化成功時、和モードでは次のいずれかの説明が `stderr` の `strata prefill: peer GPU ...` 行に含まれる。

- `, no P2P: through mapped host memory, one weighted sum per token back`
- FP16 transfer も有効なら `, no P2P: through mapped host memory in FP16, one weighted sum per token back`

`STRATA_PF_PEER_SUMS=0` 相当の row mode では `, no P2P: through mapped host memory` と表示される。バッファ確保に失敗した場合は `prefill peer: the host route's pinned buffers (... MiB) do not fit in RAM` または `prefill peer: the peer's buffers do not fit (raise --peer-reserve-mib or lower --peer-prefill-rows)` が `err` に入り、serve 側で主 GPU のみの prompt path に戻る。変数固有の測定値は確認できない（`engine/src/prefill/prefill.cpp:3527-3545`; `engine/src/program/generate.cpp:13149-13153`）。

## 根拠

- 候補名は envvar 索引にあるが、実際の読み取りは `engine/src/prefill/prefill.cpp:3467-3471` の一箇所（索引: `docs/envvars/000_envvers.md:1710`）。
- peer tier / prompt peer の CLI 条件: `engine/src/program/generate.cpp:918-924, 10211-10223, 13146-13150`。
- P2P / host route の選択: `engine/src/core/peer_experts.cpp:208-234`; `engine/src/prefill/prefill.cpp:3336-3339, 3411-3415`。
- 和と行の計算・返送・combine: `engine/src/prefill/prefill.cpp:6621-6628, 6664-6669, 6883-6904, 6972-6980, 7617-7630`。
- 関連資料 `docs/SECOND_GPU.md:70-103` は peer tier と host route の概要を記載するが、この環境変数の値規則や和モードの測定値は示していない。
