# `--mtp-hnorm`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--mtp-hnorm` |
| 別名 | なし |
| 値 | `pooled` または `stream` |

## 役割

MTP draft layer の hidden input（`pre_fc_norm_hidden`）に使う RMS normalization の単位を選びます。`pooled` は4つの hyper-connection stream をまとめて1回正規化する既定値、`stream` は各 stream を個別に正規化します。後者を選ぶと、hidden projection に渡す draft 側の計算経路が変わります（`engine/src/program/generate.cpp:1176-1178,4127-4134`、`engine/include/strata/core/mtp.hpp:68-71`）。

## 使い方

```sh
# MTP を使う推論で、hidden input を stream ごとに正規化する
strata --pack MODEL.pack --mtp MTP_DIR --spec 4 --mtp-hnorm stream
```

## 値と既定値

- `pooled`: hidden input 全体（4 stream）に1回の weighted RMS normalization を適用します。`Options::mtp_hnorm_stream` の初期値は `false` であり、未指定時と `pooled` はこの経路になります（`engine/src/program/generate.cpp:1176-1178,4127-4134`、`engine/src/core/mtp.cpp:1217-1220`）。
- `stream`: stream ごとにRMSを計算し、各 stream に対応する weight slice でスケールします（`engine/include/strata/kernels/native_qsa.hpp:24-27`）。
- それ以外の値は受理されません。値を省略すると `--mtp-hnorm needs a value` を stderr に出して終了コード `2` で終了します。未知の値では `strata generate: --mtp-hnorm takes pooled or stream` を stderr に出し、終了コード `2` を返します（`engine/src/program/generate.cpp:3844-3847,4127-4132`）。SYCL parser も同じ値検証とエラーを行います（`engine/sycl/src/program/generate.cpp:1884-1887,2101-2107`）。
- 同じ引数を複数回指定した場合、parser は各指定のたびに設定値を代入するため、最後に指定した値が残ります（`engine/src/program/generate.cpp:3842-3847,4127-4134`）。

## 実行時の動作

parser は `stream` のときだけ `mtp_hnorm_stream` を `true` にします。MTP path が有効な場合、engine は load/capture の前にこの値を `MtpDrafter::set_hnorm_per_stream` へ渡します（`engine/src/program/generate.cpp:8243-8252`）。draft の hidden input は `stream` なら grouped RMS、`pooled` なら4 stream分をまとめる weighted RMS を通してから hidden projection に入ります（`engine/src/core/mtp.cpp:1217-1225`）。バッチ draft と prompt prefill にも同じ選択が使われます（`engine/src/core/mtp.cpp:2377-2384`、`engine/src/prefill/prefill.cpp:3131-3138`）。SYCL 側にも同等の分岐があります（`engine/sycl/src/core/mtp.cpp:925-932`、`engine/sycl/src/prefill/prefill.cpp:2008-2011`）。

## 適用条件と副作用

- 実際に効くのは MTP drafter が有効な場合です。`--mtp` が指定されても `--spec` が2未満なら、engine は MTP を無視して path をクリアし、この設定を drafter に渡しません（`engine/src/program/generate.cpp:8243-8252`）。`--mtp-hnorm` 自体には `--mtp` の同時指定を求める parser validation はありません。
- MTPを使わない実行では、このフラグは設定値を保存するだけで normalization 経路を変更しません。DFlash2のみでMTP layerをロードしない経路も同様です（`engine/src/program/generate.cpp:8243-8252`）。
- このオプションによるファイル・ネットワーク操作は確認できません。ソースからは性能差や生成品質への影響量を判断できません。

## 出力とエラー

正常な値の指定自体は出力しません。省略値・未知値のエラー文と終了コードは「値と既定値」を参照してください。ソース上、このオプション固有の警告やファイル出力は確認できません。

## 根拠

- `engine/src/program/generate.cpp:1176-1178,4127-4134`: CUDA/HIP 側 parser 用設定の既定値と値検証。
- `engine/src/program/generate.cpp:8243-8252`: MTP / `--spec` の条件と drafter への設定反映。
- `engine/include/strata/core/mtp.hpp:68-71`: 設定 setter とその適用意図。
- `engine/src/core/mtp.cpp:1217-1225,2377-2384`、`engine/src/prefill/prefill.cpp:3131-3138`: draft・batch draft・prefill の normalization 分岐。
- `engine/include/strata/kernels/native_qsa.hpp:24-27`: grouped normalization の行と weight slice の対応。
- `engine/sycl/src/program/generate.cpp:2101-2107`、`engine/sycl/src/core/mtp.cpp:925-932`、`engine/sycl/src/prefill/prefill.cpp:2008-2011`: SYCL parser と適用箇所。
