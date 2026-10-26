# `DS4_IQ_MAX_SMS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の GGUF 低ビット expert カーネルが CUDA で使う persistent grid の大きさを、GPU の SM 数以下に制限します。実機の SM 数を超えて指定しても増加しません。この上限は `resident_ctas()` が計算する常駐 block 数に反映され、persistent kernel の grid の block 数を通じて処理の分割を変えます。ソースコメントでは小さいカードを想定したベンチマーク用とされています。

## 値と判定

読み取りは `std::getenv()` と `std::atoi()` です。文字列全体の検証はなく、`atoi` が先頭の空白と符号に続く数字を変換し、数字の後ろは無視します。数字として読めない値は 0 になり、後段の `max(1, ...)` で 1 に丸められます。

| 値 | `sms` に対する処理 |
|---|---|
| 未設定 | GPU から取得した SM 数をそのまま使う |
| 空文字、数字で始まらない文字列 | `atoi` が 0 を返し、上限 1 として扱う |
| 正の整数 `N` | 実 SM 数と `N` の小さい方を使う |
| `0` または負の整数 | 上限 1 として扱う |
| 数字の後ろに文字がある値（例: `8xyz`） | 数字部分を変換し、実 SM 数と比較する |

変数は SM 数を増やせません。`atoi` の整数範囲を超える入力については、実装に明示的な検査がありません。

## 有効になる条件

- CUDA ビルドで `resident_ctas()` の CUDA 側が使われる必要があります。HIP ビルドでは同関数は大きな定数を返す分岐になり、この環境変数を読みません。
- カーネルの型が persistent grid 対象である必要があります。コードでは codebook が 8 KiB 以上となる型（IQ2_S、IQ1_S、IQ1_M）が対象です。その他の型は通常の tile/grid launch を使い、この上限を参照しません。
- その型の gate/up、down、または条件を満たす light-set 経路が実際に呼ばれる必要があります。light-set 経路は `max_rows <= 4` の場合だけ persistent grid を選びます。形状検査や他の経路選択で別 kernel に進む場合、この変数は作用しません。

## 実行時の詳細

初めて該当する `resident_ctas<Kernel>()` が呼ばれたとき、GPU の SM 数と CUDA occupancy API から kernel あたりの active block 数を取得します。環境変数が設定されていれば、SM 数を `min(実 SM 数, max(1, atoi(値)))` に制限し、`sms * max(per, 1)` を resident block 数として保存します。grid は work item 数と resident block 数の小さい方（最低 1 block）です。各 persistent block は grid-stride で複数の work item を処理します。

結果は `resident_ctas` のカーネル特殊化ごとに、GPU index ごとの `static std::atomic<int> cache[16]` に保存されます。そのため同じ kernel/GPU で最初の計算が済んだ後に環境変数を変更しても再評価されません。該当経路に入らなければ値は読み取られません。Strata 側からこの変数に関するログや警告は出しません。

## 根拠

- `src/dsv41/ds4_iq.cu:518-526`: persistent grid の型条件と HIP での無効化。
- `src/dsv41/ds4_iq.cu:1120-1140`: GPU ごとの occupancy 計算、環境変数の変換・上限適用・cache。
- `src/dsv41/ds4_iq.cu:1142-1161,1230-1240`: resident block 数を使った persistent grid と light-set 条件。
- `src/dsv41/ds4_iq.cu:1399-1425`: 型 dispatch と light-set の条件。
- `src/dsv41/ds4_gguf.cu:1266-1279,1293-1312,1352-1373`: GGUF 低ビット expert の gate/up・down から IQ kernel への呼び出し。

`docs/DETAILS.md` を含む docs 内に、この環境変数の具体的な説明や測定値は見つかりませんでした。性能上の効果はこのコード調査では確認していません。
