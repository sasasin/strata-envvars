# `--vram-experts`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` の root（サブコマンドなし） |
| オプション | `--vram-experts` |
| 別名 | なし |
| 値 | `F`。`std::atof` で読む数値。既定値は `1.0` |

## 役割

GPU の空きメモリから DeepSeek-V4.1 の expert 用に見積もる配置予算に係数を掛け、VRAM に置く expert 数を調整します。残りの expert は CPU lane 側に置かれます。これは「VRAM に置く expert の個数」そのものではなく、メモリ予算に対する倍率です（`src/dsv41/ds4_model.hpp:27-31`、`src/dsv41/ds4_model.cu:4585-4590,4616-4617,4645-4657`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1,2,3 --vram-experts 0.5
```

`--vram-experts` は `--pack`、`--ids` などと同じトップレベル引数です。source の usage も `[--vram-experts F]` と示しています（`src/dsv41/ds4_main.cpp:101-109`）。

## 値と既定値

- 省略時は `vram_experts_auto=true`、`vram_experts=1.0` です（`src/dsv41/ds4_model.hpp:30-31`）。
- 指定すると `std::atof` の結果を保存し、`vram_experts_auto=false` にします。範囲・符号・有限値の検証やエラー処理は parser にありません。非数値文字列は `atof` の規則により通常 `0` になり、数値の後ろに変換できない文字がある場合もその位置までが変換対象です（`src/dsv41/ds4_main.cpp:1307-1315,1321`）。
- 同じ option を複数回指定した場合は parser のループで値を順次上書きするため、最後に現れた値が残ります（`src/dsv41/ds4_main.cpp:1307-1321`）。値を省くと `--vram-experts needs a value` を stderr に出して終了コード `2` で終了します（同:1309-1314）。
- 安全な設定範囲はコードで定義されていません。`0` は expert 予算係数をゼロにします。負数や `1` を超える値も parser では拒否されませんが、意図した動作・資源上の安全性は保証されません。

## 実行時の動作

モデルの配置では各 device の利用可能メモリから `--reserve-mib` 分と、該当経路の作業領域分を差し引いた量にこの係数を掛けて予算を算出します。算出した予算を expert のサイズで配分し、VRAM に置く expert 数を決定します（`src/dsv41/ds4_model.cu:4585-4617,4645-4668`）。一部の事前見積もりでも係数を用い、CPU lane 側 expert の読み込み・先読み量や、expert 配置割合に基づく prompt の attention slab 判定に影響します（同:2261-2275,3001-3023,3267-3281,3344-3354）。

配置されなかった expert は CPU lane 側の処理対象となり、必要に応じてモデルファイルから読み込まれます。expert cache が有効で、一層の VRAM 配置数が全 expert 数より少なく、かつ 2 以上の場合には、配置数から cache swap 用の 1 slot を空けます（`src/dsv41/ds4_model.cu:4695-4704,4726-4756`）。

## 適用条件と副作用

- `strata-dsv41` の parser が引数を受け取る推論経路で適用されます。pack 情報だけを表示する `--pack-info` 経路はモデルを load せず終了するため、expert 配置への効果はありません（`src/dsv41/ds4_main.cpp:1388-1394,1395-1408`）。
- Metal build では、option を省略した場合（`vram_experts_auto=true`）に限り、環境変数 `DS4_NO_AUTO_VX` が未設定なら `metal_expert_cap()` の上限をさらに適用します。明示的に `--vram-experts` を渡すと自動上限の分岐を通りません。環境変数の詳細は [`DS4_NO_AUTO_VX`](../../../envvars/DS4_NO_AUTO_VX.md) を参照してください（`src/dsv41/ds4_model.cu:4618-4627`）。
- Metal の cap は物理 RAM、GPU の総メモリ、プロセスの `phys_footprint`、他プロセスの匿名メモリ等から計算されます。cap を適用した場合は stderr に `ds4: expert share: ...` を出します（`src/dsv41/ds4_model.cu:4423-4468,4618-4625`）。
- Windows の commit 上限が配置を制約すると、GPU に置けなかった expert 量と page file の案内を stderr に警告します（`src/dsv41/ds4_model.cu:4630-4685`）。この予算処理や係数により配置された expert が実際の CUDA allocation に収まらない場合、`cudaMalloc` の失敗として model load が失敗します。main は `maya-ds4: <error>` を stderr に出して終了コード `1` を返します（同:4705-4713、`src/dsv41/ds4_main.cpp:1402-1407`）。

## 出力とエラー

未知の option は `unknown option ...` と usage を stderr に出して終了コード `2` です。値不足も終了コード `2` です（`src/dsv41/ds4_main.cpp:1309-1314,1379-1385`）。数値として解釈できない値や範囲外の値そのものを理由とする parser エラーは実装されていません。モデル load 失敗時は上記の `maya-ds4:` エラーを出してコード `1` で終了します（同:1402-1407）。

## 根拠

- `src/dsv41/ds4_main.cpp:101-109,1307-1322` — usage、引数値の取得と変換、auto フラグの切り替え。
- `src/dsv41/ds4_model.hpp:25-37` — 既定値と関連する expert cache 設定。
- `src/dsv41/ds4_model.cu:2261-2275,3001-3023,3267-3281,3344-3354` — 係数を使う見積もりと関連計算。
- `src/dsv41/ds4_model.cu:4585-4713,4726-4756` — 配置予算から VRAM/CPU lane の配置を決め、device allocation を行う処理。
- `src/dsv41/ds4_model.cu:4423-4468,4618-4627` — Metal の自動 cap と stderr 出力。
- `docs/cli/README.md:1375-1424` — `strata-dsv41` の root scope と索引上の option リンク。索引は指定 option を現行 parser に掲載しています。
