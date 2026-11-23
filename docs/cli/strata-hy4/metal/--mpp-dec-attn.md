# `--mpp-dec-attn`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--mpp-dec-attn` |
| 別名 | なし。無効化する対になるフラグは `--no-mpp-dec-attn` |
| 値 | 値を取らないフラグ |

## 役割

decode と verify の attention で、条件が合えば split-K MPP Flash-MLA kernel を使う設定を有効にします。初期値は有効です。このフラグは既定値を明示的に有効へ戻すためのもので、無効化には `--no-mpp-dec-attn` を使います。フラグ自体は値を受け取りません。

## 使い方

```sh
# decode/verify の MPP Flash-MLA を明示的に有効にして実行する
strata-hy4-metal --model SQ64.strata --tokens ids.txt --gen 32 --mpp-dec-attn
```

## 値と既定値

値は不要です。内部値 `mpp_dec_attn` は初期状態で `true` であり、`--mpp-dec-attn` で `true`、`--no-mpp-dec-attn` で `false` に設定されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:331`, `1490-1491`, `1535-1536`）。両方を指定した場合は引数を走査した順に代入されるため、最後に現れたフラグが有効です（同 `1504-1507`, `1535-1536`）。

## 実行時の動作

parser が値を設定し、Metal runner の設定 `r.mpp_dec_attn` に渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1535-1536`, `1742`）。実行時には `mpp_flash_ok && mpp_dec_attn && NH % 16 == 0` が成立すると、通常の分割 attention kernel の代わりに `mla_flash_mpp_part`、木探索時には `mla_flash_mpp_part_tree` を選びます。結果はどちらも `mla_attend_merge` で統合します（同 `1052-1066`, `1071-1084`）。

通常の非木探索では、入力トークン数 `T` が 8 以下で、さらに `split_max > 0` の場合に分割 decode kernel の分岐へ入ります。`--split` は `split_max` を設定し、初期値は 8 です。したがって `--split 0` では通常経路の split attention 自体が使われず、このフラグによる kernel 選択も起きません（同 `346`, `1071-1086`, `1491`, `1531`, `1739`）。木探索は別分岐で、`split_max` が 0 以下でも分割数 `S` の下限を 1 にして split attention を実行します（同 `1052-1066`）。

speculative verify 側も、`split_max > 0` の場合に `mpp_flash_ok && mpp_dec_attn` を見て `mla_flash_mpp_part` と `mla_attend_part` を切り替えます。ここでは `S` は `min(split_max, 8)` です（`engine/src/hy4flash/metal/hy4_metal_spec.h:313-325`）。

## 適用条件と副作用

MPP Flash kernel は常に使えるとは限りません。初期化時に `--no-mpp` が指定されておらず、`hy4_mppflash.metal` を含む一式のコンパイルに成功した場合に `mpp_flash_ok` が `true` になります。そのコンパイルに失敗すると、runner は MPP Flash なしの一式を再試行し、この設定値が有効でも MPP Flash decode kernel は選ばれません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:527-550`）。head 数 `NH` は 16 の倍数である必要があります（同 `1053`, `1072`）。

この設定は decode/verify の kernel 選択に作用します。`--no-mpp-flash` は `mpp_flash_on` を無効にし、主に prefill の `mla_flash_mpp` 等を選ばないための別設定です。decode/verify の `use_mpp_part` 条件には `mpp_flash_on` が含まれず、このフラグの適用条件は変わりません（同 `330-331`, `1052-1077`）。一方、`--no-mpp` は MPP kernel 全体のコンパイル試行を止めるため、このフラグより優先して結果的に MPP decode kernel を利用不可にします（同 `533-550`, `1729`）。

## 出力とエラー

このフラグ固有の値検証や警告はありません。値を続けて渡すと、その値の文字列は別の引数として扱われ、未知引数として標準出力に `ERR unknown flag ...`、標準エラーに `unknown arg ...` を出して終了コード 2 で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1535-1536`, `1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:331`, `1490-1491`, `1535-1536`: 初期値、parser、反対フラグ。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:527-550`: MPP Flash kernel のコンパイルと利用可能状態。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1086`: decode/tree attention の kernel 分岐と split 条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1729-1742`: MPP 全体の設定と当該値の runner への引き渡し。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:313-325`: speculative verify での kernel 分岐。
