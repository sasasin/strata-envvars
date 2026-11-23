# `--kv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--kv` |
| 別名 | なし |
| 値 | `fp16` / `f16`、`q8` / `int8` / `i8` / `k8v8`、または `auto` |

## 役割

推論時の MLA key/value cache の形式を選びます。`fp16` は通常の FP16 cache、`q8` は圧縮 Q8 cache を選択します。Q8 では 1 cache slot あたりの領域が 1152 byte から 656 byte になり、RoPE key は FP16 のまま保持されます。`--kv` は CUDA/HIP runner の root scope です。この文書の調査範囲に Metal runner は含めません（索引では別の `metal/` scope です）。

## 使い方

```sh
# CUDA/HIP runner でモデルを serve し、Q8 KV cache を使う
strata-hy4 --model Hy4-Flash.strata --serve --kv q8

# オフライン実行でも FP16 KV cache を明示する
strata-hy4 --model Hy4-Flash.strata --tokens prompt.txt --kv fp16
```

## 値と既定値

- `fp16` と `f16` は `HY4_KV_Q8=0` を設定します。
- `q8`、`int8`、`i8`、`k8v8` は `HY4_KV_Q8=1` を設定します。
- `auto` はこの環境変数を変更しません。未指定時も parser は設定を変更せず、後段で環境変数が未設定なら FP16 が既定になります。したがって `auto` またはオプション省略時に、呼び出し環境に `HY4_KV_Q8` がすでに設定されていれば、後段の `atoi` 判定（0 以外なら Q8）に従います。
- 値は大文字小文字を区別する文字列比較です。上記以外の値は拒否されます。数値範囲や複数値形式はありません。
- 値がコマンド末尾で省略された場合は `ERR --kv needs a value` を標準出力へ出し、終了コード 2 で終了します。次の引数が別 option でも値として消費され、無効値として拒否されます。
- 複数回指定した場合は各値を左から処理します。有効な `fp16` / `q8` 系の最後の指定が環境変数を上書きします。`auto` は何も変更しないため、その前の指定や呼び出し環境の値を取り消しません。

## 実行時の動作

parser は `--kv` の値を読み、上記 alias を `HY4_KV_Q8` の `0` / `1` に写します。環境変数設定は Windows では `_putenv_s`、それ以外では `setenv(..., 1)` で行われ、既存値を上書きします。`auto` の場合は設定呼び出し自体がありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:471-481`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`）。

モデル初期化側は `HY4_KV_Q8` が存在し、かつ `atoi` の結果が 0 以外なら Q8 を有効にします。未設定または `0` に変換される値では FP16 です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:452-458`）。この値は KV のメモリ見積もりにも使われます（同 `:462`、`:511-512`）。cache 初期化時には形式別 byte 数で領域を確保し（`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1625`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2044-2046`）、書き込み・attention の経路にも Q8 指定を渡します（`engine/src/hy4flash/run/hy4_graph.hip.h:2102-2107`、`engine/src/hy4flash/run/mla_attn.hip.cpp:2178-2184`）。

Q8 cache の書き込み形式は 512 個の int8 値、8 個の FP16 scale、64 個の lossless FP16 RoPE 値で構成されます（`engine/src/hy4flash/run/mla_attn.hip.cpp:153-155`）。起動時の計画表示には `kv=q8` または `kv=fp16` が、runner の cache 表示には `Q8` または `FP16` が出ます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-565`、`engine/src/hy4flash/run/hy4_graph.hip.h:1753-1755`）。

## 適用条件と副作用

- 効果が確認できるのは索引で `strata-hy4` とされる CUDA/HIP runner です。Metal は別スコープであり、この文書の値仕様を適用しません。
- `--kv` はプロセス環境の `HY4_KV_Q8` を設定します。コマンドラインで明示した `fp16` / `q8` は既存環境値を上書きします。`auto` は環境値を保持します。
- Q8 は cache の格納形式とメモリ量を変えます。ソースコメント上、128K context で FP16 と比べ 780 MiB の節約とされていますが、これはソース記載値であり、この調査では実測していません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:452-458`）。
- 有効値の受理後に GPU cache の初期化で失敗した場合の詳細なエラー表示・回復動作は、ここで追跡した option 経路だけからは特定していません。

## 出力とエラー

未知の値は `ERR --kv <値>: expected fp16, q8 or auto` を標準出力に出し、flush 後に終了コード 2 を返します（`engine/src/hy4flash/run/hy4_main.hip.cpp:477-480`）。この parser 断片には未知値を補正する fallback はありません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384` — 引数走査と、値を省略した場合のエラー・終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:471-481` — `--kv` の値、alias、環境変数への写像、未知値の失敗経路。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410` — `HY4_KV_Q8` を上書きする環境変数設定関数。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:452-462` — cache 形式の既定と、容量計画で使う row size。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1625` — 環境値の読み取り、形式別 cache 確保。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:153-155`, `2044-2046`, `2178-2184` — Q8 row の構成、cache byte 数、書き込み kernel の選択。
- `docs/cli/README.md:1277-1283`, `1312` — tool ID、CUDA/HIP root scope、対象 option の索引リンク。

調査対象 checkout は `git rev-parse HEAD` が上記 SHA、`git status --short --branch` が `## main...origin/main` で、未コミット変更はありませんでした。CLI help は実行せず、parser と使用箇所をソースで確認しました。
