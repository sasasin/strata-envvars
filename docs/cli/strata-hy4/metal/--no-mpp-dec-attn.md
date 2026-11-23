# `strata-hy4-metal --no-mpp-dec-attn`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend、サブコマンドなし） |
| オプション | `--no-mpp-dec-attn` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

decode/verify および Tree-8 の attention で、利用可能な場合に使う split-K MPP Flash-MLA 部分計算 kernel を無効にします。分割計算そのものを無効にするフラグではなく、Metal の通常の部分 attention kernel に切り替えて A/B 比較する用途です。対象は `strata-hy4-metal` の Metal 実装です。

## 使い方

```sh
# 同じモデル・入力で MPP decode attention を使わずに実行する
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 1 --no-mpp-dec-attn
```

## 値と既定値

値は不要です。parser は起動時に `mpp_dec_attn` を `true` で初期化し、`--no-mpp-dec-attn` が現れると `false` にします。既定では有効です。値の検証はなく、同一コマンドラインで `--mpp-dec-attn` と併用した場合は後に解析された方が有効になります（両フラグは同じ変数を設定します）。`--mpp-dec-attn` は反対側の設定を明示するフラグです。（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1535-1536`）

## 実行時の動作

parser の値は Runner の `mpp_dec_attn` に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1740-1743`）。モデル実行時、Tree-8 では `mpp_flash_ok` とこのフラグが有効で、head 数が16の倍数なら `mla_flash_mpp_part_tree` を選びます。このオプションを指定すると `mla_attend_part_tree` に切り替わります。いずれも部分 attention の後に `mla_attend_merge` を実行します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1066`）。

Tree-8 以外では、`T <= 8` かつ `--split` の値が正の場合に split-K 経路へ入り、MPP が利用可能で head 数が16の倍数なら、有効時は `mla_flash_mpp_part`、無効時は `mla_attend_part` を使い、続けて `mla_attend_merge` を実行します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1071-1084`）。`--split 0` ならこの通常の decode split-K 経路自体が選ばれません。Tree-8 側は `--split 0` でも `S` を最低1として部分計算経路を使います（同:1052-1066）。

DFly2 speculative 実行の attention も、`split_max > 0` なら同じフラグを参照し、MPP が利用可能な場合に `mla_flash_mpp_part` と通常の `mla_attend_part` を切り替えます（`engine/src/hy4flash/metal/hy4_metal_spec.h:313-325`）。DFly2 自体は生成条件やモデル内 drafter の有無などで実行されない場合があります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1760-1762`）。

## 適用条件と副作用

- MPP Flash-MLA kernel がコンパイル可能であることが切り替えの条件です。初期化時に `--no-mpp` が指定されていない場合、Metal 実装は MPP Flash-MLA を含む kernel 群のコンパイルを試み、成功時に `mpp_flash_ok` を有効にします。失敗時は MPP Flash-MLA なしの kernel 群を試し、利用できなければ通常の kernel 群へ進みます。そのため MPP が利用できない場合、このオプションによる kernel 選択差はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:527-552`）。
- `--no-mpp` は MPP kernel の試行自体を止めるため、このオプションの切り替え先は元から通常 kernel になります（同:533-550、Runner への設定は同:1735-1743）。
- `--no-mpp-flash` は prefill の `mla_flash_mpp` 選択に使う `mpp_flash_on` を切ります。一方、decode/Tree-8 の MPP 部分 kernel の条件は `mpp_flash_ok && mpp_dec_attn` であり、`mpp_flash_on` を参照しません。したがって `--no-mpp-flash` だけでは、ここで扱う decode/Tree-8 kernel は無効になりません（同:330-331,1052-1077）。
- このフラグ自体はファイルやネットワーク設定を変更せず、GPU 実行時に選択する kernel と dispatch 構成を変えます。性能や数値差の一般的な保証はソースから確認できません。ソースコメントには A/B 用途と特定条件の測定・一致の記述がありますが、調査では測定を再実施していません（同:331）。

## 出力とエラー

対象フラグを受理した際の専用メッセージや validation error はありません。parser は引数を順に処理し、認識しない別の引数については `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード `2` を返します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1603-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1535-1536` — parser の既定値とフラグ登録。値なしで `bool` を変更し、正側フラグとの併用は後勝ち。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1740-1743` — parser の設定を Runner に渡す箇所。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:527-552` — Metal MPP Flash-MLA kernel のコンパイル試行と fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1084` — Tree-8 と通常 decode の split-K kernel 選択。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:313-325` — DFly2 speculative attention の kernel 選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608` — 未知引数の出力と終了経路。
