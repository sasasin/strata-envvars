# `STRATA_DS4_DISK_SKIP_W`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の DS4 実装で、decode などの小さい routing window において、重みファイルのページが現在 RAM にない CPU-lane expert を省略する閾値です。省略すると、その expert の出力と対応する route weight は token の計算から抜けます。route weight の再正規化はありません。そのため、実験用の近似であり、回答が変わり得ます。

## 値と判定

| 環境変数の状態 | `disk_skip_w` |
|---|---:|
| unset | `0.0`（無効） |
| 空文字 | `0.0`（`atof` の結果） |
| 数値文字列 | `atof` が変換した値と `0.0` の大きい方 |
| 数値として読めない文字列 | `0.0`（`atof` の結果） |
| 負値 | `0.0` に clamp |

文字列全体の妥当性検査はありません。`atof` のため、数値の後ろに文字がある値は数値部分として変換されます。たとえば `0.05junk` は `0.05` になります。値が正の場合、各 CPU-lane expert について `route_weight < disk_skip_w * その token の有効 route weight 合計` となり、かつページが RAM にない場合に省略します。比較は厳密な `<` です。

値は DS4 model の実装オブジェクト生成時に一度読み、メンバーに保持します。生成後にプロセス環境を変更しても、その model には反映されません。

## 有効になる条件

- DS4 の `serve_lane()` が処理する要求であること。window 内の token ごとに判定します。
- 対象 layer が MTP layer ではなく、`disk_skip_from <= layer < g.nl` であること。開始 layer は関連変数 `STRATA_DS4_DISK_SKIP_FROM` で指定され、既定値は `0`、未設定時は 0 未満を含めて 0 に clamp されます。
- routed expert が GPU slot 上ではなく CPU lane にあること。GPU slot の expert はこの省略判定を通りません。
- expert が RAM slot に存在するか、参照対象ページが OS の residency 判定で RAM にあること。RAM にある expert は閾値未満でも省略されません。

判定は `serve_lane()` の routing 要求処理にあり、prompt の大きな prefill 経路には適用されません。`STRATA_DS4_DISK_SKIP_W` が未設定、空、無効文字列、0 以下なら `disk_skip_w > 0` が成立せず、通常どおり CPU expert を計算します。

## 実行時の詳細

各 routing 要求について、実装はその token の有効な expert ID に対応する route weight を合算します。その後、CPU-lane expert ごとに `l.cpu_hits` と expert 使用統計を先に更新します。閾値未満で RAM residency もない expert は `picks` から除外され、`st.skipped` が増えます。除外された expert は `cpu_experts()` による計算と重み付き加算に入らないため、その寄与分は抜けます。残った expert の weight を再正規化する処理はありません。したがって、expert cache/profile の使用集計には現れる一方で、実計算は省略される場合があります。

RAM residency 判定は、Windows 以外では `mincore` で対象 mapping の全 page を確認します。Windows では `QueryWorkingSetEx` を使い、範囲から選んだ8 page が process working set にあるかを確認します。MXFP4 は3つの matrix part がすべて resident の場合に RAM 内と判定し、それ以外の file expert は blob 範囲を検査します。この判定は確認時点の OS residency を調べるものです。

省略数は stdout の `STAT` 行に `skipped=<expert/token>` として、decode 終了時には stderr に `decode left out ... experts a token not in RAM (...% of the routed)` として出力されます。stderr のログは実際に1つ以上の expert が省略された場合だけです。

## 根拠

- 値の読み取り、変換、clamp、layer 開始位置: `src/dsv41/ds4_model.cu:1036-1049`。
- RAM slot / file mapping の residency 判定: `src/dsv41/ds4_model.cu:1055-1062`。
- OS ごとの residency 判定: `src/dsv41/ds4_os.hpp:328-343,351-370,391-398`。
- route weight 合計、CPU-lane 判定、厳密な閾値比較、省略と計算候補への追加: `src/dsv41/ds4_model.cu:6171-6190,6230-6265`。
- 残った CPU expert の計算と重み付き加算: `src/dsv41/ds4_model.cu:6278-6329`。
- stdout / stderr の省略数ログ: `src/dsv41/ds4_main.cpp:847-874,1434-1460`。
- `docs/DETAILS.md` にこの変数の追加説明や測定値は見当たりません。性能・回答品質の測定値は記載していません。
