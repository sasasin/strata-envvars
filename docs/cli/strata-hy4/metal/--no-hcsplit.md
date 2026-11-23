# `strata-hy4-metal --no-hcsplit`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--no-hcsplit` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

オフライン推論時に、iHC mix を小さい行数ごとに部分計算してから reduce・norm する分割 dispatch を無効にします。指定しない場合は分割が有効です。主に Metal 実装の計算経路を比較するための切替です。`--serve` ではこの値は serve 設定に渡されず、ソース上で効果を確認できません。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --no-hcsplit
```

この例では、指定したモデル・token 列を用いるオフライン実行で hcsplit 経路を無効にします。`--no-hcsplit` 自体に値は付けません。

## 値と既定値

- 値なしの真偽フラグです。parser は `--no-hcsplit` を見ると内部の `no_hcsplit` を `true` にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1530`）。
- 既定値は有効です。Runner の `hc_split` は初期値 `true` で（同ファイル `:344`）、オフライン Runner への設定は `r.hc_split = !no_hcsplit` です（`:1738`）。
- 数値・文字列の validation はありません。フラグを複数回指定しても同じ真偽値を設定します。引数を付ける構文ではなく、後続の余分な文字列は別引数として処理されます。未知の引数は `ERR unknown flag ...` を標準出力へ、`unknown arg ...` を標準エラーへ出し、終了コード `2` で終了します（`:1604-1608`）。

## 実行時の動作

通常のオフライン経路では、モデル読み込み後に `Runner` が作られ、その `hc_split` にフラグの反転値が設定されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1715-1739`）。`hc_pre_norm` は `hc_split` が有効かつ `T <= 8` のとき `hc_mix_part` と `hc_reduce_norm_acc` を使い、それ以外は `hc_mix` と `hc_reduce_norm` を使います（同ファイル `:964-982`）。したがって `--no-hcsplit` 指定時は小さい行数でも後者の通常経路になります。行数が `T >= 16` の場合は既定でも `hc_mix_blk` 系が使われ、このフラグによる分岐対象ではありません（`:976-982`）。

最終 head の計算にも同じ切替があり、出力行数 `n <= 8` で分割 iHC の `hc_mix_part` / `hc_reduce_norm_acc4` を使う条件を無効化します（同ファイル `:1332-1348`）。`hc_part` 作業バッファ自体は Runner 初期化で確保されます（`:589-590`）。

`--serve` の場合、serve 分岐はオフライン Runner の生成・設定より前に実行されます。そこでは `ServeOpts` にモデルや context 等は設定されますが、`no_hcsplit` は設定されず `hy4_serve_main` へ渡されません（同ファイル `:1635-1674`）。そのため、serve 時に本オプションが hcsplit を切り替えるとは確認できません。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal 実装です。CUDA/HIP と SYCL の同名・類似フラグについてはこの文書の調査対象外です。
- オフライン経路では、各層の iHC 前処理と出力 head の行数がそれぞれ `8` 以下の時に選ばれる分割カーネル経路を抑止します。分割経路の作業用 `hc_part` バッファは引き続き確保されるため、このフラグによる確保量の削減は確認できません（`:343-344,589-590,967-982,1336-1345`）。
- `--serve` は別経路で、当該フラグを serve 側へ渡す処理が見当たりません（`:1635-1674`）。serve 中のカーネル選択への影響は確認できません。
- この切替による速度・メモリ性能の変化は測定していません。

## 出力とエラー

`--no-hcsplit` の受理自体に専用の出力やエラー経路はありません。値なしフラグとして解析されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1529-1531`）。未知の引数に対する出力と終了コードは「値と既定値」に記載したとおりです。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1504-1531`: `no_hcsplit` の初期値と引数 parser。値を消費せず真偽値を設定する。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`: 未知引数の標準出力・標準エラーと終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:343-344,589-590`: Runner の既定値と作業バッファ。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1674,1715-1739`: serve とオフラインの経路分岐、およびオフライン Runner への設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:964-982,1332-1348`: 層内と head の条件分岐、各経路で登録する dispatch。
