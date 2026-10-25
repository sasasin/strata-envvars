# `STRATA_MTP_STAGE0`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

複数 GPU の layer split で `--pipeline-windows 2` が使われるとき、MTP drafter を最後の stage の GPU ではなく最初の stage の GPU に置くかを指定します。最後の GPU で decode window と draft chain が同じカードを使うのを避け、最初のカードが window を終えて空いている間に draft chain を走らせる配置です。これは MTP の配置を選ぶ変数であり、pipeline 自体を有効にする設定ではありません。

## 値と判定

`src/program/generate.cpp` は `std::getenv("STRATA_MTP_STAGE0")` が返す文字列に `std::atoi` を適用し、結果が 0 でなければ最初の stage を選びます。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | backend と GPU による既定値を使う |
| 空文字、数字に変換できない文字列（例 `true`） | `atoi` が 0 を返すため、最後の stage |
| `0`、`00`、`0anything` | 0 と変換され、最後の stage |
| `1`、`2`、`-1`、`1suffix` | 先頭の整数部分が 0 でないため、最初の stage |
| ` 1`、`+1` | `atoi` が 1 と変換するため、最初の stage |

数値の後ろに続く文字は無視されます。整数に変換できない入力は 0 扱いです。整数範囲を超える入力について、呼び出し側に個別の範囲検査はありません。

未設定時は CUDA build では OFF、HIP build では現在のデバイスが AMD gfx1200 または gfx1201 の場合に ON、それ以外は OFF です。HIP の既定値判定はデバイス名を取得できない場合も OFF になります。`STRATA_MTP_STAGE0` を設定すると、この既定値を上書きします。

## 有効になる条件

値が非 0 でも、次のすべてを満たす場合にだけ最初の stage 配置が選択されます。

- `--mtp` が指定され、`--spec` が 2 以上。
- `STRATA_MTP_FULL_HEAD` が未設定、または設定値の先頭文字が `1` 以外。先頭文字が `1` なら `mtp_first_ok` が偽になり、この配置は使われません。
- draft vocabulary ファイルが存在する。`--mtp-draft-vocab FILE` を指定した場合はそのファイル、指定しない場合は `<mtp>/draft_vocab.bin` が調べられます。ここではファイルの存在だけを確認し、内容の妥当性は後続の MTP load 処理が扱います。
- `--pipeline-windows` の実効値が 2 以上で、layer split の後段 stage が存在する。
- `--batch` が 0。

`--pipeline-windows` は `--serve` でのみ使えます。自動設定の場合もありますが、`STRATA_MTP_STAGE0` 自体は pipeline の自動有効化判定ではなく、条件を満たして `mtp_first` を決める段階で読み取られます。たとえば `STRATA_MTP_STAGE0=1` だけでは pipeline は有効になりません。反対に、自動設定の二段 split で pipeline が有効になった後に `=0` を指定すれば、drafter は最後の stage に残ります。

SYCL 側の `sycl/src/program/generate.cpp` にはこの名前の読み取りがありません。この設定の実装対象は `src/program/generate.cpp` の CUDA/HIP 経路です。

## 実行時の詳細

判定は generate の初期化中に `mtp_first` として一度行われます。HTTP リクエストごとには再評価されないため、稼働中にプロセス環境を変更しても配置は変わりません。

最初の stage を選んだ場合、MTP drafter は最初の GPU 上で load されます。draft vocabulary が使われ、主モデルの head が別 GPU にある場合は、主 head の token subset の行を head 側 GPU で gather し、その subset を drafter 側へ一度コピーします。pipeline の row buffer も drafter の GPU に確保されます。MTP の K/V state や snapshot の紐付けも最初の stage 側に切り替わります。`=0` または既定 OFF のときは従来どおり最後の GPU に置かれます。

この変数専用の有効・無効ログは見つかりませんでした。pipeline 自体が自動で有効になった場合は `--pipeline-windows 2 is on by default for a layer split of ... stages` が stderr に出ます。MTP head のロード時には token 数とサイズのログが出ますが、配置モードを示すものではありません。

## 文書との照合

`docs/MULTI_GPU.md` は 0.1.44 の gfx12 測定を説明し、draft chain と最後の stage の競合を避ける配置、および `STRATA_MTP_STAGE0=0` による従来配置への切り戻しを記載しています。同文書の exact-flags A/B、5 組では、2 枚構成の code decode は 103→125 tok/s（+21%）、3 枚構成は code +19%、4 枚構成は code +22% でした。prompt の 4K はそれぞれ +8%、+12%、+15%、prose は同率、+2%、+4% と記載されています。これは文書にある R9700 構成の測定値であり、今回の調査で再測定したものではありません。

## 根拠

- `src/program/generate.cpp:1630-1648` — HIP の既定値判定と gfx12 対象（`include/strata/kernels/gfx_arch.hpp:30`）。
- `src/program/generate.cpp:3498-3505` — MTP、spec、full-head 環境変数、draft vocabulary ファイルによる適用条件。
- `src/program/generate.cpp:3644-3654` — stage 数、pipeline、batch 条件と `STRATA_MTP_STAGE0` の `atoi` 判定。
- `src/program/generate.cpp:4621-4629, 5141-5146, 7924-7930` — drafter の device、load、VRAM 見積もり、pipeline row buffer の配置。
- `src/core/mtp.cpp:690-735` — vocabulary subset の行を head 側から drafter 側 GPU にコピーする処理と失敗時エラー。
- `src/program/generate.cpp:8242-8249, 10995-11009` — conversation checkpoint / snapshot で MTP K/V state を持つ stage の切り替え。
- `docs/MULTI_GPU.md:257-264` — 配置の説明と記載測定値。
