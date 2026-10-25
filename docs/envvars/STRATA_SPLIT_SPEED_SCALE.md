# `STRATA_SPLIT_SPEED_SCALE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の layer split を `--layer-split auto` で自動配置するとき、各 GPU stage の推定処理速度に倍率を掛けます。この値は分割探索用の速度モデルだけに使われ、GPU の実クロックや実行速度は変更しません。未設定なら推定値に変更はありません。ソースコメントは「test seam」と呼びますが、本番コードにも読み取り処理があり、自動配置の候補評価に影響します。

## 値と判定

環境変数は各 stage の推定速度を計算するときに読みます。未設定または空文字列なら倍率処理を行いません。非空ならカンマ区切りの要素を stage 番号に対応させ、対象要素を `std::atof()` で変換します。

| 入力 | 動作 |
|---|---|
| `0.57,1` | stage 0 の推定速度を 0.57 倍、stage 1 を 1 倍する |
| `1,0.55` | stage 0 を変更せず、stage 1 を 0.55 倍する |
| `0.5` | stage 0 のみ 0.5 倍。後続 stage は要素がないため変更しない |
| `,0.5` | stage 0 の空要素は 0 となり変更なし。stage 1 は 0.5 倍 |
| `abc,0.5` | `abc` は 0 として stage 0 は変更なし。stage 1 は 0.5 倍 |
| `-1,0.5`、`0,0.5` | 0 以下の倍率は無視し、stage 0 は変更なし。stage 1 は 0.5 倍 |

要素の前後空白や数値の後ろに文字がある場合の厳密な受理規則は `atof()` に委ねられ、文字列全体の検証やエラー報告はありません。正の倍率を適用した後の推定速度は `max(1.0, speed * 倍率)` に制限されます。倍率が非常に小さい場合も速度は 1.0 を下回りません。カンマ以降の余分な要素は、実際の stage 数を超える分は参照されません。

根拠: `src/program/generate.cpp:4330-4349`。

## 有効になる条件

- CUDA の複数 GPU layer split が選ばれ、`--layer-split auto` の配置探索に入る場合に読み取られます。手動の layer split や単一 GPU では、このコード経路に入りません。
- 各 stage の倍率は、その stage の GPU の SM 数と CUDA-reported clock rate から作る `speed` に適用されます。倍率が適用された `layer_ms` は予測 decode window 時間に加算され、2〜4 GPU の配置探索の採点と、4 GPU 超の比例配置の layer 割当てに使われます。
- 予測時間が同等の候補を比べる際の slowest-stage 時間にも `layer_ms` が使われます。別の容量・prompt 開始可能性の条件や、後段の小 stage 再探索があるため、倍率だけで境界が決まるわけではありません。
- 変数に既定の補完値はありません。stage に対応する要素が欠ける場合やその要素が正数でない場合、その stage の倍率は 1 相当（変更なし）です。

根拠: `src/program/generate.cpp:4321-4349,4463-4467,4481-4486,4630-4642,4744-4804`。

## 実行時の詳細

読み取りと配置探索は layer split 初期化中に行われます。`getenv()` の結果は `static` に保存されないため、stage ごとの速度計算で取得し直しますが、候補探索後に環境を変更しても既に選ばれた配置は再計算されません。各 stage の診断行 `strata generate: layer split auto: CUDA%d ... -> ... ms per layer` は倍率を反映した `layer_ms` を出しますが、表示する SM 数・GHz は元の GPU 属性値です。環境変数専用の警告や parse error はありません。

## 文書との照合

`docs/MULTI_GPU.md:70-82` は、2x RTX A4000 を `STRATA_SPLIT_SPEED_SCALE=0.57` と `--vram-reserve-mib 4400` で不均等に評価した条件での自動配置比較を記録しています。同資料では旧ルール K=3 に対して新ルール K=20、prompt reading 945→1,441 tok/s、decode 50.2→65.9 tok/s としています。これは記載された 14.5K token prompt、IQ3_XXS、5 組の interleaved run の結果であり、速度倍率単独の効果や他環境での性能を示すものではありません。ソース上もこの変数は stage 速度推定値を調整し、自動配置探索で利用されています。

## 根拠

- `src/program/generate.cpp:4321-4349` — CUDA 自動分割時の GPU 属性取得、変数の読み取りと倍率適用、推定 layer 時間。
- `src/program/generate.cpp:4463-4467,4481-4486,4630-4642,4705-4708` — 推定時間を用いた候補採点、slowest stage の tie-break、比例配置。
- `docs/MULTI_GPU.md:70-82` — 自動配置の背景と特定環境での測定記録。
