# `HY4_MLA_SPLIT_DIV`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の HIP/CUDA MLA attention で、split-K の分割数をキー範囲から制限する除数です。`choose_splits()` が目標 block 数から求めた暫定分割数 `S` を、`ntiles / div` 以下に制限します。従ってキー範囲が短い場合に過剰な分割数を避ける調整値であり、モデル・attention のキー選択自体は変更しません（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423`）。

このコードは `strata-hy4` 用の GPU ソースとしてビルドされます。CUDA ビルドでは未設定時の既定値が `1`、HIP ビルドでは `2` です（`engine/CMakeLists.txt:884-892`、`engine/src/hy4flash/run/hy4_gpu.h:16-23,325-350`）。

## 値と判定

`getenv()` が null かどうかで未設定を判定し、設定時は `atoi()` で整数化して `std::max(1, ...)` を適用します。文字列全体の数値妥当性検査はありません。空文字や数値に変換できない文字列は `atoi()` の結果が 0 となり、1 に丸められます。先頭の空白・符号は `atoi()` の変換規則に従い、数値の後ろに文字があっても変換可能な先頭部分が使われます（例: `2tail` は 2、`0anything` は 0 から 1）。大文字小文字や `true` / `false` の判定はありません。

| ビルド条件 | unset | 有効になる値（例） | 無効・境界値の例 |
|---|---|---|---|
| CUDA (`HY4_CUDA` が真) | `div = 1` | `2` → 2、`-3` → 1 | 空文字、`0`、`abc` → 1 |
| HIP (`HY4_CUDA` が偽) | `div = 2` | `3` → 3、`1` → 1 | 空文字、`0`、`-3`、`abc` → 1 |

値は `div >= 1` に丸められます。正の数値でも `div` が大きいほど `ntiles / div` は小さくなり、最終的に少ない split 数になります。整数変換後の値はさらに `S <= 128` と `S >= 1` に制限されます。整数型の範囲外の入力に対する `atoi()` の結果はこのコードで規定されず、利用可能な値として扱えません（`engine/src/hy4flash/run/mla_attn.hip.cpp:1414-1423`）。

## 有効になる条件

- `strata-hy4` の GPU MLA 実装が選ばれること。CUDA/HIP で `mla_attn.hip.cpp` がそれぞれの GPU 言語としてビルドされます（`engine/CMakeLists.txt:884-892`）。
- `mla_attend()` が fast path を使う条件（`!g_mla_force_simple`、`NH % 16 == 0`、正の `cache_slots` が 16 の倍数、WINDOW モードなら正の 16 の倍数の ring）を満たすこと。これを満たさない場合は単純 attention kernel に戻るため、`S` による split-K 分割は使われません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2199`）。
- fast path でも、`HY4_CUDA` が偽で `kv_q8` が真の場合は単純 Q8 kernel に戻り、分割数の効果は attention 計算に使われません（`engine/src/hy4flash/run/mla_attn.hip.cpp:2237-2241`）。CUDA の Q8 経路は `S` 個の partial を処理します（同 `2210-2216`）。
- split 数が 1 の場合は partial の結合を行いません。複数 split の計算用 workspace が不足する場合も単純 kernel に fallback します（`engine/src/hy4flash/run/mla_attn.hip.cpp:2200-2208,2230-2253`）。
- 実際の分割数は `M`、head 数 `NH`、最大キー数、`g_mla_target_blocks`、`g_mla_batch_invariant` にも依存します。`--mla-blocks` は目標 block 数を変更し、`--mla-inv` は小さい batch の基準を変えますが、いずれもこの環境変数の値を上書きしません（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423`、`engine/src/hy4flash/run/hy4_main.hip.cpp:440-441`）。

## 実行時の詳細

`choose_splits()` 内の関数ローカル `static const int div` として初回呼び出し時に一度評価され、プロセス内で cache されます。`mla_workspace_bytes()` も `choose_splits()` を呼ぶため、attention kernel の実行前に workspace サイズを求める段階で初期化されることがあります。Hy4-Flash runner の初期化時に decode 用 workspace を計算し、chunk 処理時にも workspace サイズを再計算します（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423,2038-2042`、`engine/src/hy4flash/run/hy4_graph.hip.h:1742-1747,2166-2169`）。そのため、初回評価後に環境を変更しても同プロセスでは反映されません。

計算は `base = (batch-invariant 条件なら 1、それ以外は M) * (NH / 16)` を求め、目標 block 数から `S` を算出します。`base` が目標 block 数以上なら split しません。そうでなければ `S` を `ceil(g_mla_target_blocks / base)` から始め、キー tile 数 `ntiles = ceil(max_keys / FBK)` に対して `floor(ntiles / div)` 以下にし、128 以下、1 以上に制限します（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423`）。`S > 1` のときは partial 結果を workspace に書き、combine kernel で統合します。workspace が足りない場合は単純 kernel に戻ります（同 `1377-1407,2200-2208,2230-2253`）。

## ログと測定値

この環境変数の値、丸め結果、選択された `S` を直接出すログやエラー処理は確認できませんでした。workspace 不足時の fallback にもこの箇所からの専用ログはありません。`docs/DETAILS.md` にこの変数の設定値や条件付き測定値は見つかりませんでした。

## 根拠

- `engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423` — 分割数、環境変数の変換・既定値・丸め・上限。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:2038-2060,2193-2253` — workspace sizing、split 数の利用、fast path と fallback。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1742-1747,2166-2169` — workspace サイズ計算と MLA attention 呼び出し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:440-441` — CLI の `--mla-blocks` / `--mla-inv`。
- `engine/src/hy4flash/run/hy4_gpu.h:16-23,325-350`、`engine/CMakeLists.txt:884-892` — GPU compile 条件。
