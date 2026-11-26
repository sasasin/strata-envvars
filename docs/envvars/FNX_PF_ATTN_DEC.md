# `FNX_PF_ATTN_DEC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`sFNX` の prompt 処理で、attention 層の attention 計算に通常の prompt attention ではなく decode 用 `attn()` 経路を使うかを選ぶ。値が 0 以外なら、QSA のブロック選択を `attn_rows()` 単位で行い、各グループの選択結果を使って `attn()` を呼ぶ。通常の経路では `p.qsa_pf_rows` 単位で選択し、prompt attention の `pf_attention()` を実行する。どちらもその後の出力射影 `wo` と prompt 状態のリング集約につながる。これは prompt attention の経路を変える設定であり、decode 時の `attn()` 設定ではない（`engine/src/split/src/prefill.cu:1661-1689,1693-1699`）。

## 値と判定

`prefill_alloc()` が `env_flag("FNX_PF_ATTN_DEC")` を呼ぶ。`env_flag` は `env_int(name, 0) != 0` で、未設定だけが既定値 0 になる。設定値は符号付き base-10 整数として文字列全体を parse し、`long long` の範囲外、数字のない文字列、末尾に余分な文字がある値は受け付けない。空文字や空白を含む値も整数全体にならないため無効で、例外になる。0 は off、0 以外は on（負値も on）であり、真偽文字列の特別扱いや clamp はない（`engine/src/split/src/env.hpp:15-21,33-40,51-52`）。

| 条件 | unset | 有効になる値の例 | 無効値の例 |
|---|---|---|---|
| split engine の prompt buffer 初期化時 | off（0） | `1`, `-1`, `+2` | `0`, `true`, `0x1`, `1x`, 空文字, ` 1`, 整数範囲外 |

無効値は off への fallback ではない。helper は `FNX_PF_ATTN_DEC: '<値>' is not a whole number` という `std::runtime_error` を投げる（`engine/src/split/src/env.hpp:33-39`）。

## 有効になる条件

- `sFNX` の split engine がビルドされ、実行されること。CMake は split を opt-in とする。CUDA では Windows と Apple を除外し、HIP では Apple を除外する条件がある（コメントには Linux CUDA / HIP と記載。`engine/src/split/CMakeLists.txt:1-7,20-25,76-91`）。通常の単 GPU engine のコード経路にはこの読み取り箇所はない。
- engine の prompt buffers が初期化されること。変数は `Engine` 構築中の `prefill_alloc()` で読む（`engine/src/split/src/engine.cu:317-318`; `engine/src/split/src/prefill.cu:854-856,1022`）。
- 対象の prompt 層が `is_attn(l)` であること。設定が true でも、非 attention 層では `attn_dec` 分岐は使われない（`engine/src/split/src/prefill.cu:1651-1658,1673-1689`）。
- QSA の選択に使う各グループの行数は `attn_rows()` が返す値になる。通常の prompt 経路で使う `FNX_PF_QSA_ROWS` の `p.qsa_pf_rows` はこの設定が true のとき選択に使われない（`engine/src/split/src/prefill.cu:1671-1678`; `engine/src/split/src/kernels.cu:1380-1383`）。

この設定を上書きする CLI 引数や設定ファイルは該当コードにない。関連環境変数 `FNX_PF_QSA_ROWS` は通常経路のグループ幅を設定するが、decode attention 経路選択時には使われない。モデルやカードが `attn()` の必要条件を満たさない場合の変数固有 fallback は実装されていない。split engine の構成・対応モデル自体は `engine/src/split/CMakeLists.txt:1-7` に記載される。

## 実行時の詳細

値を読む場所は `Engine::prefill_alloc()` 内の一箇所で、各カードの `Pf` に同じ `attn_dec` 値を設定する。グローバル static cache ではなく、engine 初期化時にカードごとに読み取り、その後は `p.attn_dec` を使うため、初期化後の環境変更は既存 engine に反映されない。新しい engine の構築では改めて読み取る（`engine/src/split/src/prefill.cu:854-856,1013-1023`）。

attention 層では Q/K/V を作り、K/V cache に追加し、QSA index を計算した後、設定が true なら `attn_rows()` ごとに `qsa_select()` を行い、選択セルとセル数を `attn()` に渡す。false の場合は `FNX_PF_QSA_ROWS` 由来の幅で選択し、`pf_attention()` が prompt attention を開始・完了する。どちらの経路も `wo` 出力を `p.bo_a` に書くが、true の場合は `attn()` がその attention 出力を生成するため `pf_attention()` は呼ばれない。overlap が有効な場合の集約条件も `p.attn_dec` に応じて変わり、true の経路では `ring_async()` により出力を集約する（`engine/src/split/src/prefill.cu:1659-1689,1693-1699`; `engine/src/split/src/kernels.cu:1385-1399`）。

## ログと測定値

この変数を有効・無効にしたことを示す専用ログは見つからない。整数でない値は helper の例外文言を伴う失敗経路になる。sFNX の起動時例外処理は `sfnx: failed: <例外文言>` を stderr に出し、`ERR <例外文言>` も出力する（`engine/src/split/src/env.hpp:33-39`; `engine/src/split/tools/sfnx.cpp:1095-1099`）。対応する測定値はこの commit の `docs/DETAILS.md` では確認できなかったため、性能や出力の同一性は記載しない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40,51-52` — 整数 parser、既定値、真偽判定。
- `engine/src/split/src/prefill.cu:362-365,854-856,1013-1023` — `Pf` の状態と初期化時の読み取り。
- `engine/src/split/src/prefill.cu:1651-1689,1693-1699` — prompt attention 経路とリング集約。
- `engine/src/split/src/kernels.cu:1380-1399` — decode attention の行数と実装呼び出し。
- `engine/src/split/src/engine.cu:317-318`; `engine/src/split/CMakeLists.txt:1-7,20-25,76-91` — 初期化順と split build 条件。
- `engine/src/split/tools/sfnx.cpp:1095-1099` — 起動時例外の出力。
