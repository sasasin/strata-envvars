# `--expert-profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立した DeepSeek-V4.1 engine executable） |
| オプション | `--expert-profile` |
| 別名 | なし |
| 値 | profile ファイルのパス、または特別値 `none` |

## 役割

expert ごとの過去の routing 回数を profile ファイルから読み込み、回数の多い expert を優先して VRAM に配置したり、CPU 側の expert cache を事前に温めたりします。推論中に新たな routing 回数を同じファイルへ保存するため、次回起動時にも利用できます。オプション自体は `Options::profile` に値を渡す parser で、実装上の既定値は空文字列です（`src/dsv41/ds4_main.cpp:1216`、`src/dsv41/ds4_model.hpp:25-33`）。

## 使い方

```sh
strata-dsv41 --pack /models/maya-ds4 --expert-profile /data/ds4-profile.bin --ids 1,2
```

profile を使わず、読み込み・保存の両方を止める場合:

```sh
strata-dsv41 --pack /models/maya-ds4 --expert-profile none --ids 1,2
```

`--pack` と実行モードの指定も必要です。`--ids` は token ID 列を指定する実行モードの一例です（usage: `src/dsv41/ds4_main.cpp:85-93`）。

## 値と既定値

- 値は一つの引数として受け取ります。オプションの値がないと `--expert-profile needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1200-1207`）。
- 未指定のまま通常実行に進むと、`<pack>/expert-profile.bin` が使われます（`src/dsv41/ds4_main.cpp:1282-1288`）。
- 値が大文字小文字を含めて `none` と完全一致すると profile path を空にし、読み込みと保存を無効にします。それ以外の文字列はファイルパスとして扱われます（同 `1286-1288`）。
- 同じオプションを複数回指定した場合、parser は各出現値を順に代入するため最後の値が残ります（同 `1200-1217`）。
- profile はヘッダー付き形式ではなく、layer・expert の順に並んだ生の `uint32` routing hit 数です。engine は `(全 layer 数 + MTP layer 数) × expert 数` 個、または trunk の `全 layer 数 × expert 数` 個を読み取れた場合だけ採用します（`src/dsv41/ds4_model.cu:966,2537-2545`）。

## 実行時の動作

起動時、指定 path を binary read mode で開きます。ファイルが開けない場合や読み取った要素数が上記のどちらの個数とも一致しない場合、エラーを出さず profile を初期値のゼロのまま使います。読み込んだ数値は expert ごとの hit 数であり、expert 別の値の意味や順位を検証する追加 validation はありません（`src/dsv41/ds4_model.cu:2537-2545`）。

読み込まれた hit 数の大きい expert は、layer ごとの VRAM slot に優先して割り当てられます。同じ layer 内で hit 数が同じ場合は初期 index 順です（`src/dsv41/ds4_model.cu:3880-3897`）。CPU 側に残る expert の warmup 順序にも profile が使われ、expert store が存在するときは、profile が空でなければ起動時 preload の候補選定にも使われます（同 `4049-4073,4562-4583`）。

推論中は routed expert の選択回数が profile の hit 数に加算されます（同 `7089-7098`）。profile が有効なら `.tmp` ファイルに生データを書き、置換処理で指定先へ反映します。serve 実行では要求処理中および serve 終了時に保存され、通常の生成実行でも終了時に保存されます（`src/dsv41/ds4_main.cpp:930,957,1506`、`src/dsv41/ds4_model.cu:8996-9005`）。既存の profile ファイルは置換されます。

## 適用条件と副作用

- この文書の対象は CMake option `STRATA_BUILD_DSV41=ON` で生成される独立 executable `strata-dsv41` です。Release での配布有無はこの調査では確認していません（`CMakeLists.txt:797-811`、索引 `docs/cli/README.md:1353-1357`）。
- `--expert-profile none` は profile に基づく初期配置・warmup と profile の永続化を無効にします。expert cache 自体を無効にする設定ではありません。
- `--no-expert-cache` は別の option です。cache の swap 用 spare VRAM slot の扱いを変えますが、profile による expert 配置の順位付けは別処理として残ります（`src/dsv41/ds4_main.cpp:1216,1223`、`src/dsv41/ds4_model.cu:3880-3897`）。
- profile を有効にした実行は指定先（省略時は pack 内）を書き換えます。保存先を変更する場合、書き込み可能な場所を指定してください。`.tmp` の作成または置換に失敗した場合、実装は `.tmp` を削除し、CLI へ保存失敗を報告しません（`src/dsv41/ds4_model.cu:8996-9005`）。

## 出力とエラー

値の欠落は stderr にメッセージを出し、終了コード 2 になります。未知の option は stderr に `unknown option ...` と usage を出して終了コード 2 です（`src/dsv41/ds4_main.cpp:1202-1207,1266-1272`）。profile ファイルが存在しない、開けない、またはサイズが不一致である場合の専用 warning/error 出力はありません（`src/dsv41/ds4_model.cu:2537-2545`）。model のロード自体が失敗した場合は `maya-ds4: <理由>` を stderr に出して終了コード 1 になります（`src/dsv41/ds4_main.cpp:1289-1294`）。

## 根拠

- parser、usage と必須値・unknown option の経路: `src/dsv41/ds4_main.cpp:85-93,1200-1217,1266-1294`
- 既定値と `none` の処理: `src/dsv41/ds4_model.hpp:25-33`、`src/dsv41/ds4_main.cpp:1282-1288`
- 読み込み形式と件数条件: `src/dsv41/ds4_model.cu:966,2537-2545`
- VRAM 配置、warmup、routing count の更新: `src/dsv41/ds4_model.cu:3880-3897,4049-4073,4562-4583,7089-7098`
- 保存と CLI 側の保存タイミング: `src/dsv41/ds4_model.cu:8996-9005`、`src/dsv41/ds4_main.cpp:930,957,1506`
- executable の build 条件: `CMakeLists.txt:797-811`
