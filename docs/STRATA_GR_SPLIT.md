# `STRATA_GR_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP の gfx906 向け hyper-connection の複数トークン読み取り (`fused_gr_read_multi`) で、down projection を K 軸に分割する実験的な経路を選ぶ。ソースコメントでは、単一トークン読み取りとは加算順が異なるため既定では無効としている。これは複数トークン処理のカーネル選択であり、通常の単一トークン `fused_gr_read` には適用されない。

## 値と判定

| 環境変数の状態 | `split_on` | 動作 |
|---|---:|---|
| 未設定 | false | 通常の複数トークン読み取り経路へ進む |
| 値が文字列として厳密に `1` | true | gfx906 の K-split 経路を試す |
| 空文字、`0`、`01`、`1x` など、それ以外 | false | 通常経路へ進む |

`atoi` や数値 parse は行わず、取得した文字列を `std::string` にして `"1"` と完全一致比較する。判定結果は関数内の `static const bool` に保持されるため、最初にこの判定へ到達した後のプロセス内環境変更は反映されない。

## 有効になる条件

- この分岐は `#if defined(STRATA_HIP_GFX906)` の内側にあり、CMake の `STRATA_HIP_GFX906` ビルドでのみコンパイルされる。通常の CUDA、wave32 HIP (`STRATA_ENABLE_HIP`)、SYCL ビルドにはこの環境変数による分岐はない。
- `fused_gr_read_multi` が呼ばれる必要がある。Strata は検証窓や MTP などでこの複数トークン API を使うが、ハイパーコネクション fused 経路や対応形状が選ばれない場合は到達しない。
- 引数に Q8 down/up 重みがある場合、Q8 読み取りを先に実行して関数から戻るため、この設定は使われない。
- `STRATA_GR_V3` の読み取りが有効で、カード上の必要な共有メモリ設定が通って v3 経路が実行される場合も、そちらが先に戻るため、この設定は使われない。v3 のカード適合判定に失敗して通常経路へ続く場合は、後続の gfx906 split 判定に到達し得る。
- この分岐内の norm/up カーネルは `STRATA_GR_FAST` の値に従う。未設定時は HIP ビルドで fast が選択される。`STRATA_GR_FAST=0` なら通常版 norm/up を使い、down の K-split 自体は残る。

## 実行時の詳細

設定が有効で上記の先行経路に捕まらないと、各トークンの norm を実行し、down 計算を5個の K スライス（各2048要素）に分けて起動する。各 block は8 wavefront分の行を処理し、スライスごとの部分和を device 配列へ保存する。後続カーネルが5個の部分和を固定順に加算し、down 結果の SiLU と inject 結果を作る。その後、`STRATA_GR_FAST` の選択に従って fast または通常の up カーネルを実行する。

この経路は `fused_gr_read_multi` の戻り値を `false` とし、fused read 内で q8_1 出力を書かなかったことを呼び出し元に伝える（コメント上、呼び出し元が量子化する経路）。CUDA エラーが起きると `fused_gr_read_multi: <エラー文字列>` を stderr に出してプロセスを終了する。

`docs/AMD_HIP.md` の表は `gr_down_multi` の K-split について約3%/verify window と記載している。これは資料上の測定説明であり、この調査で再測定した値ではない。同資料は測定環境を同節後半に記載している。正確性についてソースコメントは単一トークン経路と bitwise 一致しないことを有効化しない理由として挙げている。

## 根拠

- `src/kernels/cuda/fused_gr.cu:1273-1345` — gfx906 専用の5スライス down カーネル、部分和の固定順加算と後処理。
- `src/kernels/cuda/fused_gr.cu:1813-1824` — `STRATA_GR_FAST` の parse と HIP 既定値。
- `src/kernels/cuda/fused_gr.cu:1830-1864` — 複数読み取りの引数確認と Q8 経路の先行 return。
- `src/kernels/cuda/fused_gr.cu:1865-1929` — `STRATA_GR_V3` の先行経路と適合判定。
- `src/kernels/cuda/fused_gr.cu:1930-1962` — gfx906 限定、`STRATA_GR_SPLIT` の完全一致判定、分岐後の起動順、既定経路への fallback。
- `CMakeLists.txt:62-71,122-138` — gfx906 ビルドオプションとコンパイル定義。
- `include/strata/kernels/fused_gr.hpp:53-60` — `fused_gr_read_multi` の用途と複数トークン契約。
- `docs/AMD_HIP.md:488-510` — gfx906 向けスイッチ表および測定環境の説明。
