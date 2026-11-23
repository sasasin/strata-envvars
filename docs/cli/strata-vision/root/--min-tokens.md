# `strata-vision --min-tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（`strata-vision-hip` / `strata-vision-sycl` も同じ parser） |
| オプション | `--min-tokens` |
| 別名 | なし |
| 値 | 整数。正の値は画像 encoder が使う最小画像トークン数として扱われる |

## 役割

画像を vision encoder に渡す前に、画像を最小トークン数に相当する画素面積まで拡大する設定です。小さな画像から得る画像 embedding の格子を大きくできます。`--min-tokens` は `strata-vision` の reader 起動時に指定し、各 `ENC` 要求の画像前処理に使われます。

## 使い方

```sh
strata-vision --mmproj ./vision-projector.gguf --min-tokens 1024
```

`--mmproj` は必須です。reader は起動後に標準入力から `ENC <画像パス> <出力パス>` を受け付ける常駐プロセスとして動作します。server の vision 設定 `min_tokens` が truthy の場合も、server がこのオプションと値を reader に渡します。

## 値と既定値

- オプションは値を1つ取り、`std::atoi` で整数に変換します。数値形式や範囲の検証はありません。変換できない文字列や空文字は `atoi` の結果 `0` になり、負数も拒否されません。値を省略すると parser は stderr に `<option> needs a value` を出して終了コード 2 で終了します。`--min-tokens` を複数回指定した場合は、後の値が前の値を上書きします。(`terminal/tools/vision/strata_vision.cpp:61-65, 89-91`)
- 既定値は `0` です。0 以下ではオプション値による下限指定を使わず、mmproj から読み込んだ tower の `min_tokens` が使われます。Strata の `VitGeometry` 初期値は 8 ですが、実際の geometry は GGUF の情報から構築されます。(`terminal/tools/vision/own/own_reader.h:14-20`; `terminal/tools/vision/own/vit_geometry.h:41-45`; `terminal/tools/vision/own/image_prep.cpp:205-209`)

## 実行時の動作

parser は受け取った整数を `OwnReaderOptions.min_tokens` に格納します。画像ごとに、tower の patch・merge 形状から `patch_area = patch² × merge²` を計算し、正の指定値なら `min_pixels = min_tokens × patch_area`、それ以外なら tower の既定最小値を同様に画素面積へ換算します。画像寸法を tower の整列幅に合わせ、現在の画素面積がその下限を下回る場合はアスペクト比を保って拡大します。その後 resize/pad と正規化を行い、得られた画像を encoder に渡します。(`terminal/tools/vision/own/image_prep.cpp:42-59, 205-225`)

この値は画像前処理に適用され、text model のトークン数や生成上限を設定するものではありません。`--max-tokens` も正の値なら最大側の画素面積として resize に使われます。`smart_resize` は、まず現在の整列済み寸法が最大面積を超える場合に縮小し、それ以外で下限を割る場合に拡大します。さらに指定された最大トークン数を超える結果が許容幅（最大値の 1/8）を超えた場合、その画像要求を拒否します。(`terminal/tools/vision/own/image_prep.cpp:42-59, 205-209`; `terminal/tools/vision/own/own_reader.cpp:132-140`)

`terminal/serve/server.py` の `Vision.reader_args` は設定 `min_tokens` が truthy の場合にのみ `--min-tokens <値>` を追加します。したがって server 設定の 0 は引き渡されず、reader 側の tower 既定値が残ります。設定の型変換・入力検証はこの引き渡し箇所からは確認できず、ここでは推測しません。(`terminal/serve/server.py:3017-3029`)

## 適用条件と副作用

- `strata-vision`、`strata-vision-hip`、`strata-vision-sycl` は同じ `terminal/tools/vision/strata_vision.cpp` をビルドし、出力名と backend 定義を切り替えます。ビルドによる GPU/CPU 経路の差はありますが、正の `min_tokens` は画像準備に渡されます。(`terminal/tools/vision/CMakeLists.txt:77-97`; `terminal/tools/vision/strata_vision.cpp:87-90`; `terminal/tools/vision/own/own_reader.cpp:112-114, 132-134`)
- 指定値が大きいと、小画像がより大きな寸法に拡大されて encoder へ渡り、その画像の処理時間やメモリ使用量が増える可能性があります。具体的な増加量は画像・tower・backend に依存し、この調査では測定していません。
- 指定値自体に正の上限 validation はありません。極端な値での寸法計算やメモリ確保の挙動はソース上で安全な上限として定義されていないため、範囲を断定できません。

## 出力とエラー

`--min-tokens` 固有の成功メッセージはありません。reader は起動時に `READY`、各画像要求の完了時に `OK <トークン数> <横格子数> <縦格子数> <処理時間>` を標準出力へ返します。前処理失敗や最大トークン超過は `ERR ...` を標準出力へ返して、その画像要求を続行します。オプション値の欠落は標準エラーと終了コード 2、未知の引数も標準エラーと終了コード 2 です。(`terminal/tools/vision/strata_vision.cpp:63-65, 89-95`; `terminal/tools/vision/own/own_reader.cpp:120-140, 155`)

## 根拠

- `terminal/tools/vision/strata_vision.cpp:61-95` — parser、整数変換、必須 `--mmproj` の確認、usage と引数エラー。
- `terminal/tools/vision/own/own_reader.h:14-20` — reader option の既定値。
- `terminal/tools/vision/own/image_prep.cpp:42-59, 205-225` — 最小値から画素面積を作る処理、resize の条件、画像への適用。
- `terminal/tools/vision/own/own_reader.cpp:112-140, 147-155` — 起動時 warm-up と各画像処理への値の伝播、最大値超過、出力。
- `terminal/serve/server.py:3017-3029` — server 設定から reader 引数への条件付き転送。
- `terminal/tools/vision/CMakeLists.txt:77-97` — 同じ parser ソースをビルドする実行ファイル名と backend の切替。
