# `FNX_PF_QSA_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の CUDA/HIP prompt prefill で、QSA の block selection を一度に処理する行数を指定する。既定値は 256 行で、設定値は `MAXT`（16 行）の倍数にする。`prefill.cu` の `qsa_select` 呼び出しをこの行数のグループに分け、QSA score 用バッファも少なくともその行数分確保する。QSA 自体を有効化するスイッチではない（`engine/src/split/src/prefill.cu:386-387, 903-904, 1666-1678`、`engine/src/split/src/model.hpp:43`）。

このソースは split engine のソース一覧に含まれ、ビルド設定に応じて CUDA または HIP としてコンパイルされる（`engine/src/split/CMakeLists.txt:76-91`）。ここで確認した読み取りは prompt prefill 経路にあり、通常の decode 側の QSA 呼び出しには使われていない（`engine/src/split/src/prefill.cu:1670-1689`、decode 側の `engine/src/split/src/engine.cu:1104-1113, 1191-1198`）。

## 値と判定

`prefill_alloc()` 内の attention 用 arena 設定時に `std::getenv` で読み、未設定なら `qsa_pf_rows` の初期値 256 を使う。設定時は `std::strtol(..., 10)` で 10 進整数として読み、変換できた文字がなく、文字列が最後まで消費されない、値が 16 未満、または 16 の倍数でない場合に `std::runtime_error` を送出する（`engine/src/split/src/prefill.cu:387, 896-903`、`engine/src/split/src/model.hpp:43`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の値域 | 256 | `16`, `32`, `256`, `+16`, ` 16` | 空文字、`0`, `15`, `-16`, `17`, `16x`, `0anything` |

`strtol` の後に `*end == '\0'` を要求するため、末尾の文字や空白は許されない一方、`strtol` が読み飛ばす先頭空白と符号 `+` は許される。`errno` は検査していない。値は `long` から `int` にキャストされるが、`int` の上限を明示的に検査するコードはないため、`INT_MAX` を超える入力のキャスト結果は移植可能な範囲として保証できない（`engine/src/split/src/prefill.cu:897-902`）。

## 有効になる条件

- split engine の CUDA または HIP ビルドで prompt prefill が初期化されること（`engine/src/split/CMakeLists.txt:76-91`、`engine/src/split/src/engine.cu:318`）。
- QSA 選択が実行される attention layer であること。行数は `prefill.cu` の各 attention layer の QSA index と selection のグループ化に使われる（`engine/src/split/src/prefill.cu:1658-1678`）。
- `FNX_PF_ATTN_DEC` が未設定または `0` であること。この変数が非ゼロなら `AR` は `attn_rows()` になり、`FNX_PF_QSA_ROWS` は QSA 選択のグループ幅には使われない。ただし `FNX_PF_QSA_ROWS` の読み取り・値検査と score バッファサイズ計算はそのまま行われるため、無効値ならこの経路でも初期化が失敗する（`engine/src/split/src/prefill.cu:903, 1022, 1671-1682`）。`FNX_PF_ATTN_DEC` は `env_flag` を通じて整数を読み、未設定時は 0、整数の 0 以外なら true になる（`engine/src/split/src/env.hpp:33-40, 51-52`）。

## 実行時の詳細

`Engine` 初期化中に `prefill_alloc()` が呼ばれ、その中の `attn_set` が各カードの prompt 用バッファを組み立てる。このとき設定値を読み、`qsa_pf_rows` に保存する。arena のサイズ見積もりと実領域設定の両方で `attn_set` が呼ばれるため、通常の初期化では各カードについて同じ値を読み直す。prompt 実行のたびに環境を読み直すコードはない（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-856, 896-904, 919-934`）。

prompt の各 attention layer で QSA index を作成した後、`AR` 行ずつ `qsa_select` に渡す。`FNX_PF_ATTN_DEC` が無効なら `AR = qsa_pf_rows`、有効なら `AR = attn_rows()` である。各グループの先頭行から対応する `gctl` を選び、行数 `Tg` とともに selection に渡す。`FNX_PF_ATTN_DEC` 有効時には、その selection の結果を同じグループの prompt attention にも渡す（`engine/src/split/src/prefill.cu:1670-1682`）。

無効値の場合は `prefill_alloc()` 中に `FNX_PF_QSA_ROWS: a positive multiple of <MAXT>, not '<入力値>'` という文言の `std::runtime_error` を送出する。`prefill.cu` 内ではこの例外をログ出力に変換していないため、利用者側での表示方法は呼び出し元に依存する（`engine/src/split/src/prefill.cu:896-900`）。

## 根拠

- `engine/src/split/src/prefill.cu:386-387, 896-904` — 既定値、環境読み取り・検査、score バッファ確保。
- `engine/src/split/src/prefill.cu:1658-1689` — prompt の QSA index、グループ幅の選択、selection と attention への受け渡し。
- `engine/src/split/src/env.hpp:33-40, 51-52` — 関連する `FNX_PF_ATTN_DEC` の整数フラグ判定。
- `engine/src/split/src/model.hpp:43` — `MAXT = 16`。
- `engine/src/split/CMakeLists.txt:76-91` — split prefill ソースの CUDA/HIP ビルド設定。
- `engine/src/split/src/engine.cu:318` — engine 初期化から `prefill_alloc()` を呼ぶ箇所。
