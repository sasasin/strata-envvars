# `--kv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--kv` |
| 別名 | なし |
| 値 | 次の引数を1個消費する。Metal runner では値の形式・範囲を検証せず、値を利用しない |

## 役割

Metal runner は `--kv` と値を受け取りますが、`not used by the Metal runner` という警告を stderr に出すだけで、KV cache の形式や設定を変更しません。同じ `strata-hy4` の CUDA/HIP runner には同名の実動作するオプションがありますが、Metal では KV cache の指定として機能しません。

## 使い方

```sh
# `--kv q8` は警告だけを出し、Metal runner の KV cache 設定には反映されない
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --kv q8
```

Metal runner の実行に KV cache の値を指定する目的では使用できません。例のモデル・入力ファイル名は説明用です。

## 値と既定値

- `--kv` の直後の argv 要素を文字列として1つ読み取ります。`nxt()` は `argv[++i]` を返すだけで、数値変換や値の検査はしません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1603`）。
- この runner では受理値の一覧や既定値は定義されていません。どの値を渡してもその値は保存・転送されず、同じ警告経路に入ります（同 `:1603`）。
- 繰り返し指定した場合は、指定ごとに値を1つ消費して警告を1行出します。設定値を上書きする状態はありません（同 `:1504-1506,1603`）。
- 値を省略した場合の引数不足チェックはありません。`nxt()` が argv 範囲を検査しないため、欠落時の結果はソースから安全に特定できません（同 `:1504-1506,1603`）。

## 実行時の動作

parser は `--kv` を `--gpu`、`--vram-experts-gb`、`--ram-experts-gb`、`--engram-cache-mib` と同じ分岐で処理し、値を消費した後に stderr へ `[args] --kv <値>: not used by the Metal runner` を出します。`--kv` 固有の状態変更や後続処理への値の引き渡しはありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）。

値の引数はオプション名かどうかを調べずに消費します。そのため、たとえば `--kv --load-only` と並べると `--load-only` が `--kv` の値として扱われ、`--load-only` の分岐には到達しません（同 `:1504-1507,1603`）。

この scope は Metal runner に限ります。比較対象の CUDA/HIP runner は `--kv fp16` / `f16`、`q8` / `int8` / `i8` / `k8v8`、`auto` を別途解釈し、`HY4_KV_Q8` を設定します。Metal runner の `--kv` にその値規則や効果を適用することはできません（`engine/src/hy4flash/run/hy4_main.hip.cpp:471-482`）。

## 適用条件と副作用

Metal runner の parser に限って警告付きで受理されます。値は KV cache に適用されず、`--kv` 分岐自体は警告以外の副作用を持ちません。オプションがなければこの警告は出ません。後続のモデル読み込み・推論などは通常の引数とモデル状態に従って実行されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1629`）。

## 出力とエラー

- 値がある場合、指定ごとに警告を stderr に出して parser を続行します。警告分岐自体はエラー終了コードを返しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）。
- 必須の `--model` が最終的に指定されていない場合は usage を stderr に出して `2` で終了します。モデル読み込み失敗は `load: ...` を stderr に出し `1` で終了します。これらは `--kv` の検証結果ではなく、後続の通常処理です（同 `:1611-1622`）。
- `--kv` に値がない場合は明示的なエラー処理がありません。欠落時の具体的な出力・終了コードは記載できません（同 `:1504-1506,1603`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506` — Metal CLI の argv ループと値取得 lambda。値取得時に引数数を検査しない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608` — `--kv` を含む未使用オプション群の警告、および未知フラグのエラー経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1629` — model 必須チェックと、通常のモデル読み込み・失敗時の出力と終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:471-482` — CUDA/HIP runner における同名オプションの値規則と `HY4_KV_Q8` 設定。Metal の動作根拠ではなく、scope の違いを示す比較。
- `docs/cli/README.md:1358-1387` — 索引上の `strata-hy4-metal` scope と `--kv` の配置。
