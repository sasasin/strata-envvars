# `strata-hy4-metal --no-mpp-flash`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--no-mpp-flash` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Metal runner が利用可能な場合に選ぶ MPP Flash-MLA 経路を抑え、通常の prefill attention では simdgroup-matrix Flash-MLA へ切り替えるための比較・切り分け用フラグです。MPP Flash-MLA のカーネルをビルド・初期化しない指定ではありません。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32 --no-mpp-flash
```

## 値と既定値

値は不要です。フラグを指定すると parser 内の `no_mpp_flash` が `true` になり、runner の `mpp_flash_on` に `false` が設定されます。未指定時は `no_mpp_flash` が `false` で、`mpp_flash_on` は既定で有効です。指定を繰り返しても同じ真偽値を設定するだけで、逆向きに戻す効果はありません。値の validation はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1534,1741`）。

## 実行時の動作

- 通常の非 tree attention では、Flash-MLA が有効で、MPP Flash カーネルが利用可能、トークン数 `T >= 16`、head 数 `NH` が 16 の倍数の場合に選ばれる `mla_flash_mpp` を、このフラグで選択対象から外します。その条件下では次の `mla_flash_sg16` 経路に進みます。Flash-MLA 自体を無効にする指定ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1067-1070`）。
- attention の query 準備と value up-projection でも、MPP Flash 対応カーネルの選択条件に `mpp_flash_on` が含まれます。`T >= 32` の場合、指定時はそれぞれ `mla_prep_q_mm`、`mla_vup_mm` が選ばれます（同 `:1016-1024,1093-1101`）。
- tree attention、および `T <= 8` の split attention が使う `mla_flash_mpp_part_tree` / `mla_flash_mpp_part` の選択条件には、このフラグの状態が含まれません。これらは `mpp_flash_ok`、`mpp_dec_attn`、head 数などで決まります。したがって `--no-mpp-flash` だけでは、これらの MPP split attention 経路は無効になりません（同 `:1052-1066,1071-1084`）。
- `--no-flash` は別の設定です。こちらは通常の非 tree attention における Flash-MLA 分岐そのものを無効にします。一方、query 準備・value up-projection の MPP カーネル条件は `flash_on` を参照しないため、`--no-flash` だけではそれらの MPP 選択は止まりません（同 `:334,1016-1024,1067-1070,1093-1101`）。
- MPP Flash の利用可否は、`--no-mpp` と Metal カーネルの compile 成功にも依存します。`--no-mpp` がなければ初期化時に MPP Flash を含めて compile を試し、失敗時は MPP Flash なしの kernel 群へ fallback します。このフラグはその compile 試行を抑止しません（同 `:533-550,1527,1729`）。さらに `mpp_flash_ok` の場合、初期化時の pipeline 準備では MPP Flash カーネル群を参照します（同 `:724-730`）。

## 適用条件と副作用

対象は索引上の Metal 実装 `engine/src/hy4flash/metal/hy4_metal_main.cpp` です。効果は MPP Flash kernel が利用可能で、対応する分岐条件が成立するときに現れます。MPP の compile が失敗している場合や分岐条件を満たさない場合、この指定による追加の経路変更はありません。

このフラグ固有のファイル・ネットワーク出力や GPU 側の状態変更は確認できません。推論自体は通常どおり GPU runner で実行されます。MPP Flash の compile に失敗したときの stderr 警告と fallback はフラグ固有ではなく、MPP 初期化の共通処理です（同 `:533-556`）。

## 出力とエラー

フラグ自体に対する validation、警告、専用のエラー経路はありません。未知の引数は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 になりますが、このフラグは parser に登録されているため未知引数扱いにはなりません（同 `:1534,1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1534,1741` — フラグの初期値、引数 parser、runner 設定への反映。
- 同 `:328-334` — MPP Flash の compile 可否、選択設定、通常 Flash-MLA の状態。
- 同 `:533-550,724-730` — MPP kernel の compile 試行・fallback と初期化時の MPP Flash pipeline 準備。
- 同 `:1016-1024,1052-1084,1067-1070,1093-1101` — query 準備、attention、value up-projection それぞれの実行時分岐。
- 同 `:1604-1609` — 未知引数の出力と終了コード。
