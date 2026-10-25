# `STRATA_GR_UP_ILP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の fused hyper-connection read にある up projection で、T token の dot product を計算してから、token ごとの warp butterfly reduction を段階ごとに交互に進めるカーネルを選びます（T は1の場合もあります）。既定経路は token ごとに dot product と butterfly reduction を完了してから次の token に進みます。ILP 経路では計算順序を token 間で交互にしますが、各 token 内の butterfly の順序は同じです。ソースコメントは同じ bit pattern になるとしています。性能向上の保証や測定値は、この環境変数について確認できる資料にありません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

文字列全体や数値としての妥当性は調べず、`getenv()` の戻り値が存在し、先頭文字が `'1'` かだけを確認します。`gr_up_ilp()` 内の `static const bool` に初回評価結果を保存するため、同じプロセス内でその後環境を変更しても再評価されません。既定値は無効です。CLI 引数や設定ファイルによる上書きはありません。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:845-848`。

## 有効になる条件

- SYCL の fused hyper-connection read 実装を使う必要があります。このカーネルは `sycl/src/kernels/cuda/fused_gr.dp.cpp` にあります。
- 通常の multi-token up launch に到達する必要があります。`STRATA_GR_MORE_GROUPS` による more-groups 経路は `gr_up_multi_kernel<..., false, true>` を直接起動するため、この変数を参照しません。
- `STRATA_GR_LARGE_GRF` による large-GRF 経路が有効な場合も、`grf` 分岐で通常カーネルを起動して return するため、この変数を参照しません。
- generate 側では fused hyper-connection read 自体が `--gr-native-mmvf` 有効、`--no-fused-gr` 無効、GPU stages / layer・half dump / stage timing 無効の条件で選ばれます。これらの条件外ではこの経路を通りません。

関連する more-groups / large-GRF の既定値は Alchemist GPU 世代を基準に判定され、それぞれ `STRATA_GR_MORE_GROUPS` / `STRATA_GR_LARGE_GRF` で変更されます。従って `STRATA_GR_UP_ILP=1` だけでは ILP カーネルが必ず選択されるとは限りません。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:625-649,803-833,860-865,2038-2044`; `sycl/src/program/generate.cpp:2911-2920`。

## 実行時の詳細

通常経路では `launch_gr_up_cols()` が `gr_up_ilp()` を評価し、有効なら `gr_up_multi_kernel<C, true>`、無効なら `gr_up_multi_kernel<C>` をキューに投入します。`C` は `STRATA_GR_UP_COLS` に応じて選ばれますが、この変数は ILP の有効・無効を決めません。ILP 経路は各 token の dot product を先に算出し、xor offset `16, 8, 4, 2, 1` の butterfly 段階ごとに token を交互に加算します。既定経路は各 token に対して同じ段階順の `warp_sum()` を行ってから次の token に進みます。出力の epilogue はどちらも各 token の lane に適用されます。

値を読む際のログ出力はありません。この変数が直接変えるのは SYCL カーネルの選択と演算スケジュールです。Strata の `docs/DETAILS.md` に、この変数固有の説明や測定値は確認できませんでした。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:750-778,840-875,2038-2044`。

## 根拠

- 値の読み取りと初回評価のキャッシュ: `sycl/src/kernels/cuda/fused_gr.dp.cpp:845-848`。
- 2つの演算スケジュールと token ごとの reduction 順序: `sycl/src/kernels/cuda/fused_gr.dp.cpp:750-778`。
- more-groups 経路では ILP を false に固定: `sycl/src/kernels/cuda/fused_gr.dp.cpp:823-833,2038-2044`。
- large-GRF と ILP の分岐順序、および通常経路の launch: `sycl/src/kernels/cuda/fused_gr.dp.cpp:849-875`。
- fused hyper-connection を generate 側で有効化する条件: `sycl/src/program/generate.cpp:2911-2920`。
