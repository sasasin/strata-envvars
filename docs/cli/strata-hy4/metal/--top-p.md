# `strata-hy4-metal --top-p`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--top-p` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で読み取る値 |

## 役割

確率サンプリング時に、確率の高い候補から累積確率が指定値に達するまでを残す nucleus sampling の閾値を設定する。Metal runner の `SampleOpts` では既定値は `1.0` で、値が `1.0` 未満の場合に top-p の候補切り詰めが実行される（`engine/src/hy4flash/metal/hy4_metal_spec.h:15-23, 82-94`）。

## 使い方

```sh
# speculative decode で確率サンプリングを有効にして、候補の累積確率を 0.9 までに絞る
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 128 --draft dfly2 --temp 0.8 --top-p 0.9
```

この例で確率サンプリングを有効にする `--temp` と、speculative decode の条件を満たす `--draft` は別オプションである。Metal CLI の parser はそれぞれの値を `cli_samp` と設定へ格納する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1501-1503, 1548, 1567-1571`）。

## 値と既定値

- 値は `atof` の戻り値を `float` にして格納する。parser に明示的な範囲検証や補正はない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1503-1506, 1567-1570`）。
- 省略時は `SampleOpts::top_p = 1.f`。top-p の条件分岐は `top_p < 1.f` のときだけ行われるため、`1.0` 以上の値ではこの段階の切り詰めは行われない（`engine/src/hy4flash/metal/hy4_metal_spec.h:15-23, 82-90`）。
- `0` 以下の値を確率サンプリング経路で使うと、累積確率は最初の候補で条件を満たし、少なくとも候補 1 個を残す実装になっている（`engine/src/hy4flash/metal/hy4_metal_spec.h:82-94`）。
- 無効な文字列、範囲外の値、重複指定に対する専用エラー・検証は parser にない。重複時は引数を順に読み、後の指定が `cli_samp.top_p` を上書きする（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506, 1567-1569`）。

## 実行時の動作

確率サンプリング経路では、候補を最大 `top-k` 個に絞り、温度を適用した確率を正規化し、`min-p` の後に top-p を適用する。top-p は確率降順の候補を累積し、指定値に到達した候補までを残した後、その残存候補の確率を再正規化する（`engine/src/hy4flash/metal/hy4_metal_spec.h:49-94`）。同じ順序と条件は通常の serve sampler にも実装されている（`engine/src/hy4flash/metal/hy4_metal_serve.h:175-205`）。

オフライン CLI では適用経路に条件がある。

- `cli_prob` は温度が greedy 条件（`temperature <= 0`）でないか、sampling penalty がある場合に限り真になる。top-p 単独では確率モードを有効にしない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1818-1819`; `engine/src/hy4flash/metal/hy4_metal_spec.h:15-23`）。
- speculative decode が成立した場合、その sampler に `cli_samp` が渡るのは `cli_prob` が真のときだけである。speculative decode は生成数が正、draft が `off` でなくモデルに drafter があり、runner の chunk が 16 以上、`--all-logits` でなく、画像入力がない場合に有効になる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1760-1762, 1911-1912, 1935-1937`）。
- `--serve` 経路では CLI の `cli_samp` は `ServeOpts` に渡されない。各リクエストの `GEN` 行で `top_p=<値>` を指定すると、そのリクエストの `SampleOpts` に読み込まれる。ただし `GEN` の `temperature` が省略時の `0` 以下なら greedy 分岐で返るため、top-p は適用されない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`; `engine/src/hy4flash/metal/hy4_metal_serve.h:91-100, 121-138, 175-180, 193-200`）。
- speculative decode を使わない通常の `--gen` 経路は argmax で次 token を選択するため、そこでは `--top-p` は使われない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1966`）。

## 適用条件と副作用

このオプション自体は候補分布を変えるだけで、ファイル操作やネットワーク操作を行わない。結果として生成 token が変わる可能性がある。greedy 条件では sampler が top-p の処理に入らず、top-p 単独では `cli_prob` も有効にならない（`engine/src/hy4flash/metal/hy4_metal_spec.h:23, 63-66, 82-90`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1818-1827`）。

## 出力とエラー

`--top-p` 固有の範囲エラーや警告を出す分岐は確認できない。未知の引数は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード 2 で終了するが、これは未知オプション全般の処理である（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。引数値を省略した場合の専用検査も parser に見当たらず、安全なエラー挙動はソースから確認できない（同 `:1504-1506, 1567-1569`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1501-1506, 1567-1571` — sampling 設定の生成、CLI parser、top-p 値の格納。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674` — serve 経路で `cli_samp` を渡さず `ServeOpts` を構成する箇所。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1760-1762, 1818-1844, 1911-1937, 1944-1966` — speculative の有効条件、確率モード判定、値の引き渡し、通常生成経路。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:15-23, 30-95` — 既定値、greedy 条件、top-p を含む確率分布の構築。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:91-138, 162-205` — serve リクエスト値の parse と sampler の top-p 処理。
