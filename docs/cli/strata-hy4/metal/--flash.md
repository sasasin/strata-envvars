# `--flash`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--flash` |
| 別名 | なし。無効化側の別オプションは `--no-flash` |
| 値 | 値を取らないフラグ |

## 役割

Metal 版 HY4 runner の通常の非 tree attention で、prefill の大きな chunk に使う K-streamed Flash-MLA を有効にする。既定ですでに有効であり、主に先行する `--no-flash` をコマンドライン上で打ち消す場合に指定する。Metal 4 の MPP Flash-MLA が利用可能ならその実装を選び、そうでなければ simdgroup の Flash-MLA を選ぶ。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --flash
```

`--flash` 自体は値を取りません。引数は左から順に処理されるため、両方を指定した場合は後にある方が有効になります。

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --no-flash --flash
```

## 値と既定値

- 値・数値範囲・validation はありません。parser はフラグを見つけると `no_flash` を `false` にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1495,1532-1534`）。
- `no_flash` の初期値は `false` なので、オプションを省略した場合も Flash-MLA は有効です（同 `:1490`）。
- `--no-flash` は同じ状態を `true` にします。順次解析されるため、重複時は最後に指定した `--flash` / `--no-flash` が状態を決めます（同 `:1504-1506,1532-1534`）。

## 実行時の動作

parser の後で `Runner::flash_on` に `!no_flash` を渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1738-1742`）。通常の非 tree attention では、chunk の token 数 `T` が16以上で、attention head 数 `NH` が16の倍数の場合に Flash 経路の対象になります。MPP Flash-MLA がコンパイル済みかつ `mpp_flash_on` の場合は `mla_flash_mpp` を dispatch し、それ以外では `mla_flash_sg16` を dispatch します（同 `:1067-1070`）。

この選択には次の条件・相互作用があります。

- `--no-mpp-flash` は MPP Flash-MLA だけを無効にします。上記の条件を満たす通常経路では simdgroup Flash-MLA が引き続き使われます（同 `:329-334,1067-1070`）。
- `T < 16`、`NH` が16の倍数でない場合、または `--no-flash` が有効な場合は、この Flash 経路を選ばず、条件に応じて split attention または通常の `mla_attend` に進みます（同 `:1071-1086`）。
- `T <= 8` かつ `split_max > 0` の分岐は `flash_on` の判定より後段にあり、この条件を満たすと split attention を選択します。MPP Flash-MLA が利用可能で `mpp_dec_attn` も有効なら `mla_flash_mpp_part` が選ばれることがあります（同 `:1071-1084`）。したがって `--no-flash` はこの分岐の MPP split attention まで一律に無効化するスイッチではありません。
- `is_tree` の分岐は `flash_on` を参照せず、tree 専用の split attention を先に組み立てます（同 `:1052-1066`）。このため `--flash` は tree attention 経路を切り替えません。

このオプションが直接変更するのは Runner の経路選択フラグです。ファイルやネットワークの操作は parser および当該設定代入からは確認できません。実際の GPU kernel 実行条件は上記の chunk・head 数・実行経路に依存します。

## 出力とエラー

`--flash` 単独による出力や値のエラー処理はありません。誤記した別のオプション名は未知引数として stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出し、終了コード `2` で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1495,1504-1506,1532-1534` — CLI 状態の初期値、引数走査、および `--flash` / `--no-flash` の parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:329-334,1738-1742` — Runner の Flash 状態と MPP Flash 状態の初期値・設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1086` — tree、Flash-MLA、split attention、通常 attention の dispatch 条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知引数時の出力と終了経路。
