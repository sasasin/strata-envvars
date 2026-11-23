# `--split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--split` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

Metal 版 HY4 の attention で、decode / verify 時に key 範囲を分担する split-K の分割数を指定する。各分割が部分結果を書き、merge kernel がまとめる。設定は speculative tree verify にも共有されるが、通常 decode と tree verify では値の補正方法が異なる。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens ids.txt --gen 32 --split 4
```

`--split` を省略した場合は 8。別の `--split` を複数回指定した場合は、引数走査中に同じ変数へ順次代入されるため最後の値が使われる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1504-1532`）。

## 値と既定値

- 既定値は `8`（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491`）。
- 値は `atoi` で整数に変換され、`split_arg` から runner の `split_max` に渡される（同 `1531,1738-1740`）。専用の範囲検証やエラー分岐は確認できない。
- 通常の非 tree attention では `split_max > 0` のときだけ split-K 経路に入り、0 以下ではこの経路を使わない（同 `1071`）。数値に変換できない文字列は `atoi` の結果 0 として扱われる。
- 指定値が大きい場合、実際の分割数 `S` は経路ごとに上限が適用される（次節）。

## 実行時の動作

通常の非 tree attention では、`T <= 8` かつ `--split` の値が正の場合に partial attention kernel と `mla_attend_merge` を dispatch する。Metal 4 の MPP Flash-MLA が利用可能で、`--mpp-dec-attn` が有効、かつ head 数 `NH` が 16 の倍数なら `S = min(16, split_max * 2)`。それ以外は `S = min(split_max, NH == 32 ? 8 : 4)` となる。`T > 8` ではこの分岐に入らず、当オプションは通常 attention の kernel 選択に影響しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1067-1084`）。

tree attention の経路では通常 attention の `T <= 8` 条件とは別に tree 用 partial kernel と merge を組み立てる。このとき MPP 経路の `S` は `split_max <= 0` なら 2（値を 1 とみなして 2 倍）、それ以外は `min(16, split_max * 2)`。MPP 以外では `split_max <= 0` を 1 とみなし、最大 8（`NH != 32` なら最大 4）に補正する。したがって `--split 0` は通常 decode の split-K を止めるが、tree verify では MPP 経路なら 2、MPP 以外なら 1 の分割で partial/merge 経路が残る（同 `1052-1066`）。

runner は attention workspace を固定サイズで確保し、split 数に応じた割り当て変更はこの箇所では確認できない（同 `345-346,589`）。通常の split kernel は `nk` を `S` 分割し、MPP split kernel は 64-key tile を `S` に分けて部分結果を書き、merge が `S` 個の部分結果を合成する（`engine/src/hy4flash/metal/hy4_split.metal:19-27,63-79,82-98`、`engine/src/hy4flash/metal/hy4_mppflash.metal:248-274`）。

## 適用条件と副作用

- split-K の通常 attention 経路は `T <= 8` が条件。tree verify は別分岐で、指定が 0 以下でも MPP 経路なら 2、MPP 以外なら 1 分割を使う。
- MPP か通常 Metal kernel かは、`mpp_flash_ok`、`mpp_dec_attn`、head 数の条件で決まる。`--split` 自体は Metal/MPP 機能を有効化しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1084`）。
- 値は attention dispatch と workspace 上の部分結果数に影響する。ファイルやネットワークに対する副作用はこのオプションの使用箇所では確認できない。

## 出力とエラー

`--split` の値に対する専用の警告・エラー出力は確認できない。数値変換後に前述の条件分岐と上限補正へ進む。オプション引数の欠落時や不正な入力形式を専用に拒否する処理も確認できないため、その場合の安定した失敗動作は断定しない。未知のフラグは別経路で stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 となる（同 `1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1531,1738-1740` — 既定値、parser、runner への値の受け渡し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:345-346,589` — workspace と `split_max` の既定状態。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1084` — tree / 通常 attention の適用条件、MPP 条件、`S` の計算、partial / merge dispatch。
- `engine/src/hy4flash/metal/hy4_split.metal:19-27,63-79,82-98` — 通常 partial kernel の key 分割と merge。
- `engine/src/hy4flash/metal/hy4_mppflash.metal:248-274` — MPP partial kernel の tile 分割。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知フラグの出力と終了コード。
