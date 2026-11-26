# `STRATA_PF_PEER_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の prefill peer 経路で、P2P が使えない場合の activation と peer 側 weighted sum の host-memory 転送を FP16 にするか選ぶ。設定が有効でも expert の計算や主 GPU 側の MoE combine 全体を FP16 にする指定ではない。`Prefill::set_peer` が保持する `PeerPrefill::f16` に判定を保存し、転送形式・戻り値の合成経路を切り替える（`engine/src/prefill/prefill.cpp:1391-1405, 3472-3477, 3511-3523, 6617-6647, 6972-6979, 7622-7625`）。

この環境変数は `STRATA_PF_PEER_SUMS` が有効な場合に限って読み取られる。sums 経路では peer の各 routed row を routing weight で重み付けした token ごとの合計を返す。FP16 を選ぶと、その合計を FP16 に変換して返し、主 GPU が FP32 に戻して自身の expert rows および shared 成分と合成する（`engine/src/prefill/prefill.cpp:3467-3475, 6664-6669, 6972-6979, 7622-7630`; `engine/src/prefill/kernels.cu:3418-3432, 3448-3450`）。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡し、値が未設定なら true、設定済みなら `atoi(v) != 0` と判定する。その結果に `N % 8 == 0` を AND する（`engine/src/prefill/prefill.cpp:3472-3475`）。文字列全体の妥当性検査はなく、`atoi` が先頭から変換できる整数部分を使う。したがって空文字・数字で始まらない文字列・`0` で始まる文字列（例: `0anything`）は 0 扱いで無効、`1`・`true`・`1anything`・負の非ゼロ整数は非ゼロ扱いで有効候補になる。先頭空白と符号は `atoi` の整数変換規則に従い、大文字小文字は判定対象にならない。未設定時も、後述の幅条件を満たさなければ無効となる。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| sums 経路で `N % 8 == 0` | 有効 | `atoi(v) != 0`。例: `1`, `-1`, `1junk` | `atoi(v) == 0`。例: 空文字, `0`, `0anything`, `false`, `junk` |
| sums 経路で `N % 8 != 0` | 無効 | なし（変数値にかかわらず無効） | すべて |
| sums 経路でない | 読み取られず、適用なし | なし | なし |

ここでの「有効」は FP16 経路を選ぶという意味であり、peer が実際に働く条件も満たす必要がある。`atoi` の整数範囲を超える入力の結果は C ライブラリ仕様上保証できないため、値として扱いを断定しない。

## 有効になる条件

- `strata serve` の prompt path 初期化で、peer が有効かつ `--peer-prefill-rows` が 0 以外であること。正値は指定値、負値は `prefill_chunk * K / 2` 行として扱われる（`engine/src/program/generate.cpp:13143-13150`）。
- peer が有効な prefill 計算経路を持つこと。peer device で利用可能な layer が一つもなければ設定失敗となり、NVFP4 experts は拒否される。Hadamard-folded pack では警告を出して peer 経路を使わずに戻る（`engine/src/prefill/prefill.cpp:3340-3369`）。
- P2P が使えないこと。P2P が使える場合はこの変数による FP16 host transfer 経路にならず、peer 転送は P2P copy を使う（`engine/src/prefill/prefill.cpp:3336-3339, 6645-6647`）。P2P が使えない場合でも、`STRATA_PF_PEER_HOST=0` なら host route を拒否する（同 `3336-3339`）。
- `STRATA_PF_PEER_SUMS` が未設定または `atoi` の結果が非ゼロであること。0 扱いなら `pp->sums` は false のままで、`STRATA_PF_PEER_F16` は読まれず、peer rows を戻す経路になる（`engine/src/prefill/prefill.cpp:3467-3474, 3515-3524`）。
- `N % 8 == 0` であること。満たさない場合は `f16` が false になり、FP32 の host buffers / combine を使う（`engine/src/prefill/prefill.cpp:3474-3475, 3513-3518, 7622-7625`）。
- 他の値による上書きはない。`STRATA_PF_PEER_F16` は CLI option ではなく、CLI の peer prefill 設定は peer path 自体を有効にする条件として働く。

## 実行時の詳細

`Prefill::set_peer` の初期化中、host route が使われる場合に `STRATA_PF_PEER_SUMS` を判定し、sums が有効なら続けて `STRATA_PF_PEER_F16` を一度読み取る。`f16` が true なら peer GPU 用の FP16 sum buffer と、mapped host の FP16 activation / sum buffer を確保する。buffer 確保に失敗した場合、host buffers については `prefill peer: the host route's pinned buffers (<MiB> MiB) do not fit in RAM`、peer device buffers については `prefill peer: the peer's buffers do not fit (raise --peer-reserve-mib or lower --peer-prefill-rows)` をエラーにする（`engine/src/prefill/prefill.cpp:3472-3475, 3511-3537`）。

各 prompt chunk の peer work では、primary の activation を FP16 buffer に device-to-host copy し、peer 側で FP32 に戻して計算する。peer の token sums は `sums_to_f16` で FP16 化して host に戻す。primary 側は `moe_combine_peer16` を使い、FP16 sum を float に変換してから primary の weighted rows と shared 成分に加える。FP16 化はこの転送境界と peer sum に限られる（`engine/src/prefill/prefill.cpp:6621-6647, 6972-6979, 7622-7630`; `engine/src/prefill/kernels.cu:3418-3432, 3448-3450, 3462-3478`）。

値は `PeerPrefill` の初期化時に通常の値として保存され、各 chunk で環境変数を再読込しない。実行中に環境を変更しても既存の prompt path には反映されず、path を再初期化して `set_peer` を呼ぶ場合に再評価される（`engine/src/prefill/prefill.cpp:3472-3475`; path の設定箇所は `engine/src/program/generate.cpp:13143-13169`）。子プロセスへの転送・上書き処理はこの変数について確認できない。

## ログと測定値

peer path の初期化ログは FP16 host route のとき `strata prefill: peer GPU ...; no P2P: through mapped host memory in FP16, one weighted sum per token back` を含む。FP16 無効時は `... through mapped host memory, one weighted sum per token back` と表示される（`engine/src/prefill/prefill.cpp:3538-3545`）。この変数固有の警告ログはない。実測値は `docs/DETAILS.md` および関連 Markdown から確認できなかったため記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:1391-1405` — sums / FP16 状態と関連 buffer。
- `engine/src/prefill/prefill.cpp:3333-3369` — peer route の条件と拒否経路。
- `engine/src/prefill/prefill.cpp:3467-3477, 3511-3537` — sums/F16 判定、buffer 確保と失敗。
- `engine/src/program/generate.cpp:13143-13150` — serve から `set_peer` を呼ぶ条件。
- `engine/src/prefill/prefill.cpp:6621-6647, 6972-6979, 7622-7630` — activation 転送、sum の返送、primary 側 combine。
- `engine/src/prefill/kernels.cu:3418-3432, 3448-3450, 3462-3478` — FP16 sum の float 合成と変換。
