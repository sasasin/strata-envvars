# `STRATA_KV_WIDE_HOST`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL 実装の prompt KV append で、host KV copy と staging pool への書き込みをまとめて行う経路を選びます。通常の要素ごとの書き込みに対し、この経路はローカルメモリ上で値をまとめ、32-bit store で隣接要素を書きます。対象は host/staging buffer の書き込みであり、GPU の resident KV pool への書き込み方法や INT8 値の計算方法を選ぶ設定ではありません。

## 値と判定

`std::getenv()` で得た文字列の先頭文字だけを見ます。数値変換や文字列全体の比較はありません。

| 環境変数の状態 | `wide` |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（先頭文字は `\0`） |
| 先頭文字が `0` | 無効。例: `0`, `0anything` |
| それ以外 | 有効。例: `1`, `false`, `anything`, 空白始まりの文字列 |

## 有効になる条件

- `sycl/src/prefill/kernels.dp.cpp` の `strata::prefill::kv_append()` が使われる SYCL 実装に限られます。同名環境変数への他の読み取り箇所は、Strata 所有ソース内で見つかりませんでした。
- `T <= 0` の呼び出しは環境変数を評価せずに戻ります。正の `T` で `kv_append()` が呼ばれた場合に初期化される関数内 `static const bool` に判定が保存され、以後プロセス内で環境変数を変更しても反映されません。
- 値が有効でも、対応する host または staging buffer が渡されていなければ、まとめ書きの分岐には入りません。
- 16-bit pool 経路では `k_pool != nullptr` かつ host/staging の `k_pool` が存在するときにまとめ書きが使われます。呼び出し元は INT8 KV の場合 `k_pool` / `v_pool` に `nullptr` を渡すため、この経路ではなく後述の量子化経路になります。
- INT8 経路では host/staging の `k_q` が存在するときにまとめ書きが使われます。K/V の値は各64要素グループで scale を計算して `[-127, 127]` に丸めた後、4要素ずつ32-bit値に詰めて host/staging に書きます。scale も対応する場所へ保存します。
- `kv_q4` は呼び出し側で `kv_append_q4()` に分岐するため、この環境変数の対象ではありません。HIP の `STRATA_KV_HOST_DMA` が有効な staging 経路では host pointer を渡さず、後段の DMA で host copy を作るため、直接 host へまとめ書きする分岐は適用されません。

## 実行時の詳細

判定箇所は `kv_append()` の冒頭です。判定値は GPU kernel 起動時に値渡しされ、各 workgroup の `kv_append_kernel()` が K/V の token・head・64値グループを処理します。16-bit 経路では2つの16-bit値を1つの32-bit値にまとめ、INT8 経路では4つの8-bit値を1つの32-bit値にまとめます。どちらも host copy と、渡されている場合は prompt staging pool に書き込みます。GPU pool がある場合の resident page への書き込みは、この分岐の前に従来どおり行われます。

実装コメント（`sycl/src/prefill/kernels.dp.cpp:1965-1967`）は、B70 で pinned host KV への従来の1-byte store が約30 MB/s、4,096 token 分の layer append が161 ms、4K prompt が約2秒となり、同じデータを4-byte storeにすると数msだったと記しています。これは実装コメントにある測定の記述であり、他環境の性能値を示すものではありません。`docs/INTEL.md` は KV streaming の大枠を説明していますが、この環境変数や上記store幅の測定条件を個別には説明していません。

## 根拠

- 環境変数の読み取り、既定値、kernel への引き渡し: `sycl/src/prefill/kernels.dp.cpp:2168-2203`
- 16-bit host/staging store と従来経路: `sycl/src/prefill/kernels.dp.cpp:1946-1988`
- INT8 host/staging store、scale 保存と従来経路: `sycl/src/prefill/kernels.dp.cpp:2011-2053`
- prompt append からの呼び出し、INT8時の pool pointer、Q4および host DMA の分岐: `sycl/src/prefill/prefill.cpp:2948-2989`
- draft KV append の呼び出し: `sycl/src/prefill/prefill.cpp:1467-1481`
- KV streaming の概要: `docs/INTEL.md:354-360`
