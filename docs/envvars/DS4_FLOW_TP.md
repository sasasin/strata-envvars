# `DS4_FLOW_TP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 のファイル上に置いた expert を読み込む chunked prompt 経路で、tensor-parallel（TP）グループにも「flow」方式を許可します。通常、この方式は各 GPU が単独で layer を持つ場合に限られます。変数を有効にすると、対応する MXFP4 の TP layer でも、CPU 側の expert データを staging に読み込み、GPU へ順次 DMA しながら計算する flow 経路を設定できます。

この変数は、単独 GPU / TP の選択自体や tensor-parallel 構成を設定しません。既に構成された TP グループの flow eligibility にだけ関与します。

## 値と判定

`DS4_FLOW_TP` は `std::getenv()` で読み、`std::atoi()` の結果が 0 以外なら有効です。数値文字列全体の厳密な検証はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、`0`、`0abc`、数値に変換できない文字列 | `atoi` が 0 を返すため無効 |
| `1`、`-1`、`2abc` など、先頭の整数変換結果が 0 以外 | 有効 |

`atoi` の変換規則により、先頭空白と符号は許容され、数字の後ろにある文字は判定に使われません。整数として表現できない値の結果は C ライブラリの `atoi` の仕様範囲外であり、ここでは保証できません。

環境変数の値はモデルの load 中、file-backed expert の chunk 設定時に一度読みます。load 後に環境を書き換えても、そのモデルに対する判定は変わりません。

## 有効になる条件

値が有効でも、次の条件が必要です。

- DS4 が chunked prompt 用の設定を行い、expert がファイルを source とする経路であること（`file_experts` が真）。GGUF は load 時にこの経路になります。その他の形式では mmap 指定やメモリ状況などで決まります。
- `DS4_FLOW` が flow を許可していること。`DS4_FLOW` 未設定時は許可、設定時は `atoi` が 0 以外なら許可です。`DS4_FLOW=0` は `DS4_FLOW_TP` が有効でも flow を止めます。
- 当該 device に割り当てられたすべての非 MTP layer が MXFP4 であること。
- TP layer では、`g.ff / l.nm` が down expert tensor の block 幅で割り切れること。ここで `l.nm` は当該 layer の TP group member 数です。コードは block 幅として `max(1, gg::type_block(gg::expert_type(l.lay, 2)))` を用います。

非 TP layer（`l.nm == 1`）では `DS4_FLOW_TP` は条件に使われず、他の条件が揃えば既定の flow 判定で有効になり得ます。適格性を満たさない layer が一つでも device 上にあれば、その device の `fl` は false のままになり、flow 用の queue / event 等を初期化しません。変数が無効でも、既定 flow の対応条件を満たす非 TP 構成では flow が使われます。

## 実行時の詳細

load 時、device ごとに対象 layer を走査し、TP なら `DS4_FLOW_TP` と down tensor の block alignment を含む条件で flow 適格性を決めます。適格な device では chunk に `flow` を設定し、I/O queue、staging slot と ring の event などを用意します（`src/dsv41/ds4_model.cu:2694-2750`）。

flow は chunk の各 layer で、その chunk が選択した expert を読み込みます。次 layer の有力候補を前の layer の routing 中に先読みし、残りの選択分も routing 後に読みます。I/O queue がファイルから staging に読み、DMA で ring に送り、データが到着した分から計算します（同ファイル `:563-580,3240-3258,3537-3589`）。TP で有効にした場合もこの既存 flow 経路を使います。なお、短い prompt も chunked path の対象にする既定 `chunk_min=2` は、全 device が flow の場合に設定されますが、`DS4_CHUNK_MIN` が設定されているとこの既定変更は行われません（`:2752-2757,815`）。実際に flow と windows のどちらを使うかは prompt の長さや path picker にも依存します（`:9360-9367`）。

コード内コメントは、TP flow が各メンバーで expert の down 部分全体を読み、例示した 3x V100 の条件では group windows より遅かったと記しています。ただしこれはコメント中の特定条件の記録であり、一般的な性能値や現行環境での測定結果としては扱えません（`:2707-2709`）。`docs/DETAILS.md` にこの変数の追加説明や測定値は見つかりませんでした。

## 根拠

- `src/dsv41/ds4_model.cu:2694-2710` — file-backed 条件、`DS4_FLOW` と `DS4_FLOW_TP` の値判定。
- `src/dsv41/ds4_model.cu:2711-2757` — device/layer ごとの適格性、TP block alignment、flow 初期化と chunk 閾値。
- `src/dsv41/ds4_model.cu:563-580,3240-3258,3537-3589,7381-7387` — flow data path と chunk layer 処理。
- `src/dsv41/ds4_model.cu:1957-1979` — GGUF と他形式の `file_experts` 選択。
- `src/dsv41/ds4_model.cu:9360-9367` — feed 時の chunked prompt path 選択。
