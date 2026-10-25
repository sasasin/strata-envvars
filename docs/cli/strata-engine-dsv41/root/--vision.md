# `--vision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 専用 engine CLI） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `on` / `off` 相当の文字列を1つ取る。値が厳密に `off` のとき無効、それ以外は有効 |

## 役割

モデル読み込み時に checkpoint の vision tower（`vision.*` / `aligner.*`）を読み込むか制御します。既定では有効です。無効にすると画像のエンコードができず、`--images` や serve の `GENI` 要求は失敗します。通常のテキスト推論は引き続き可能です（`src/dsv41/ds4_model.hpp:58`; `src/dsv41/ds4_model.cu:1985-1995,5209-5216`）。

## 使い方

```sh
strata-dsv41 --pack /models/deepseek/maya-ds4 --vision off --ids @prompt.ids --n 32
```

`--pack` にはモデル pack、`--ids` には token ID 列または `@` で始まる ID ファイルを指定します。画像入力を使うときは `--vision on`（または省略）にします。`strata-dsv41` は `STRATA_BUILD_DSV41=ON` の GPU backend 付き build で生成される独立 executable です（`CMakeLists.txt:797-811`）。

## 値と既定値

- 値は必須です。値の比較は大文字小文字を含む完全一致で、`off` だけが false、それ以外（`on`、`no`、空文字列を含む）は true になります。`on|off` は usage に示された形式ですが、parser に許容値 validation はありません（`src/dsv41/ds4_main.cpp:85-93,1202-1208,1234`）。
- 省略時は `Options::vision` の初期値 `true`、つまり有効です（`src/dsv41/ds4_model.hpp:58`）。
- 複数回指定すると各値を順に代入し、最後の指定が有効です（`src/dsv41/ds4_main.cpp:1200-1208,1234`）。
- 値が欠けていると `<option> needs a value` を標準エラーへ出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1206`）。

## 実行時の動作

`--vision` の値は `Options::vision` に入り、通常の model load 時に true なら最初の GPU 上へ vision tower をロードします。checkpoint に必要な vision 情報がある場合、tower と画像 token が有効になります（`src/dsv41/ds4_main.cpp:1234,1289-1292`; `src/dsv41/ds4_model.cu:1985-1986,5161-5207`）。`--vision off` ではこの load 処理をスキップします。画像 span は `--images` の単発推論と serve の `GENI` 要求で encode されるため、これらの画像経路に影響します（`src/dsv41/ds4_main.cpp:665-675,1336-1354`）。

## 適用条件と副作用

- tower の読み込み対象は checkpoint に vision layer、image token、patch embedding が揃っている場合です。tower の構成要素が見つからない場合、`load_vision` は tower を読み込まず成功扱いにします（`src/dsv41/ds4_model.cu:5161-5168`）。
- 有効時に tower の実ロードが失敗すると、通常の model load は警告を出し、画像を無効化してテキスト専用で続行します。画像 encode 専用経路（`--encode-image`）では model load が失敗扱いになります（`src/dsv41/ds4_model.cu:1985-1995`; `src/dsv41/ds4_main.cpp:1288-1293`）。`--vision off` 自体は警告を出しません。
- 画像 encode を試みると、tower が無効または利用不可の場合 `this model has no vision tower (or it is off)` で失敗します。単発 `--images` / `--encode-image` ではこのエラーを標準エラーへ出し、終了コード 1 になります（`src/dsv41/ds4_model.cu:5209-5216`; `src/dsv41/ds4_main.cpp:1313-1317,1342-1349`）。
- serve の `GENI` 要求は画像 tower がない場合 `ERR this engine has no vision tower, so it cannot read pictures` と `DONE ... cancel` を標準出力へ返して、その要求をスキップします。プロセス全体は要求処理を続けます（`src/dsv41/ds4_main.cpp:661-675`）。
- `--pack-info` は parser 後に model load より先に終了するため、このモードでは `--vision` の効果はありません（`src/dsv41/ds4_main.cpp:1275-1285`）。

## 出力とエラー

`--vision` が受理されたこと自体による出力はありません。vision tower の load 失敗時は通常経路で `ds4: WARNING: ... pictures are OFF, the model reads text only` が標準エラーへ出ます。画像処理で tower が使えない場合の終了・要求応答は前節のとおりです（`src/dsv41/ds4_model.cu:1985-1995,5209-5216`; `src/dsv41/ds4_main.cpp:665-675,1313-1317,1342-1349`）。

## 根拠

- `src/dsv41/ds4_main.cpp:85-93,1200-1208,1234` — usage、値取得、parser の真偽判定。
- `src/dsv41/ds4_model.hpp:58` — 既定値。
- `src/dsv41/ds4_main.cpp:1275-1296` — `--pack-info` の早期終了と model load。
- `src/dsv41/ds4_model.cu:1985-1995,5140-5146,5161-5207,5209-5216` — tower のロード条件、失敗時の扱い、画像 encode。
- `src/dsv41/ds4_main.cpp:661-675,1313-1317,1336-1354` — serve と単発画像入力での適用・失敗経路。
- `CMakeLists.txt:797-811` — 独立 executable の build 条件。

既存の同 revision `strata-dsv41 --help` バイナリは確認していません。記述は指定 commit の parser と使用箇所に基づき、Release 配布物の有無・挙動は調査範囲外です。
