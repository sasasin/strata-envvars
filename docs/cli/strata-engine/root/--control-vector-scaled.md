# `--control-vector-scaled`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--control-vector-scaled` |
| 別名 | なし |
| 値 | `FILE:SCALE[,...]`。GGUF ファイルのパスと浮動小数点 scale の組をカンマ区切りで指定する |

## 役割

GGUF の control vector を読み込み、指定 scale を反映した方向ベクトルをモデルの residual stream に適用する。`strata generate` の起動時にロードされ、通常は有効状態で開始する。`--serve` ではリクエストごとに適用を切り替えられる（`engine/src/program/generate.cpp:1199-1205, 1369-1374, 18835, 19149, 20048-20053`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --control-vector-scaled ./vector.gguf:0.7
```

複数ファイルは一つの値の中でカンマ区切りにできる。`strata generate` は `--pack` と token 入力を受け取る形式で、例では必要な入力も明示している（`engine/src/program/generate.cpp:1208-1214, 3849-3868, 4164-4178`）。

## 値と既定値

- 各要素は `FILE:SCALE`。最後の `:` で分割するため、Windows のドライブ文字を含むパスも扱える。scale は `strtof` で変換し、数値部分が空または末尾に未解釈文字がある場合は parser が拒否する。明示的な有限値・範囲チェックはない（`engine/src/program/generate.cpp:4165-4178`）。
- カンマで複数要素を指定でき、オプションを複数回指定した場合も各ファイルが追加される（`engine/src/program/generate.cpp:4165-4178`）。読み込み時、同じ層の `direction.<layer>` は各ファイルの scale を掛けて加算される（`engine/src/program/generate.cpp:2748-2777`）。
- オプションを省略するとファイルはロードされない。`--control-vector` は同じファイル一覧に scale `1.0` で追加される（`engine/src/program/generate.cpp:1202, 4164-4165`）。
- 値を省略すると `--control-vector-scaled needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3844-3846`）。形式不正は `--control-vector-scaled: expected FILE:SCALE, got ...` を stderr に出し、終了コード 2 を返す（`engine/src/program/generate.cpp:4170-4177`）。

## 実行時の動作

起動時にファイルを開き、GGUF の `general.architecture` が `controlvector` であることを確認する。該当層の `direction.<layer>` tensor を読み、scale を掛けて層ごとに加算した後、GPU 用の方向・scale テーブルをアップロードする（`engine/src/program/generate.cpp:2743-2777, 2813-2829`）。各層では FFN の residual write 後に control vector を適用する（`engine/src/core/layer.cpp:1638-1649`）。

併用する `--cvec-mode` は効果の式を選ぶ。既定の `add` は residual に方向ベクトルを加算し、`project` は方向を単位化して residual のその方向成分を scale 分だけ差し引く。`project` ではファイル群から合成した方向のノルムが scale として使われる（`engine/src/program/generate.cpp:1203-1205, 2793-2809`; `engine/src/kernels/cuda/cvec.cu:84-92`）。

併用する `--control-vector-layer-range A B` は両端を含む適用層範囲を指定する。省略時、または `A` が 0 以下なら層 1 から、`B` が 0 以下または層数以上なら最終層までとなる。layer 0 に方向はなく、モデル層数を超える tensor は無視される（`engine/src/program/generate.cpp:1203, 2786-2787, 2760-2764`）。範囲内の方向がある層だけが対象になる（`engine/src/program/generate.cpp:2793-2812`）。

`--serve` ではリクエストの `cvec=0|1` キーで切替でき、省略値は 1。有効状態が変わると live session は無効化され、制御ベクトル状態を切り替えてから処理する（`engine/src/program/generate.cpp:18835, 18885-18889, 19149, 20048-20053`）。

## 適用条件と副作用

- 少なくとも一つの指定ファイルに、適用範囲内でモデル層に対応する `direction.<layer>` が必要。layer 0 とモデル層数以上の層は使われない（`engine/src/program/generate.cpp:2760-2764, 2793-2812`）。
- ファイルの `controlvector.model_hint` が存在し `qwen4exp` 以外の場合は stderr に警告するが、この条件だけではロードを拒否しない（`engine/src/program/generate.cpp:2756-2758`）。
- Control vector は起動時に読み込まれ、GPU テーブルとして保持される。CUDA の layer split では各デバイスへ複製する（`engine/src/program/generate.cpp:6142-6150, 6693-6697`; `engine/src/kernels/cuda/cvec.cu:26-39, 135`）。
- Metal 側の実装コメントは control vector が未移植であると明記している。Metal でのこの option の実行結果は、ここで確認したソース範囲からは確定できない（`engine/metal/src/engine/missing.cpp:32-40`）。

## 出力とエラー

- 正常ロード時は stderr に mode、方向の選択方法、層範囲、適用層数を表示する（`engine/src/program/generate.cpp:2825-2829`）。
- GGUF が control vector でない、必要 tensor がない、tensor がモデルの埋め込み幅・f32 条件に合わない、payload が途中で切れている、ファイル読込で例外が発生した、適用範囲に方向がない、または GPU table upload に失敗した場合、エラーを `strata generate: control vector: ...` と stderr に出し、終了コード 2 で終了する（`engine/src/program/generate.cpp:2750-2783, 2789-2813, 6145-6150`）。
- `direction.<layer>` の tensor は埋め込み幅と f32 を検証し、読み出し前にファイル範囲も検証する（`engine/src/program/generate.cpp:2760-2774`）。

## 根拠

- parser と usage: `engine/src/program/generate.cpp:1208-1214, 1369-1374, 3844-3846, 4164-4183`
- GGUF 読込、validation、scale 合成、range 適用: `engine/src/program/generate.cpp:2743-2830`
- residual stream への適用: `engine/src/core/layer.cpp:1638-1653`; `engine/src/kernels/cuda/cvec.cu:45-95`
- serve リクエストごとの切替: `engine/src/program/generate.cpp:18835-18889, 19149-19155, 20048-20053`
- Metal の実装範囲: `engine/metal/src/engine/missing.cpp:32-40`
