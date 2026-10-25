# `--no-pin`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata-load` |
| オプション | `--no-pin` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`strata-load` が expert arena の読込先を確保するとき、既定の `PinnedArena` 経路を使わず、通常の `malloc` で確保するよう切り替えます。比較実験などで、CUDA 登録を行わない読込先を使う場合の指定です。このオプションは `strata-load` 専用であり、推論エンジン全体の pin 動作を切り替えるものではありません。

## 使い方

```sh
strata-load --file pack/full/experts.bin --layers 1 --no-pin
```

## 値と既定値

値は不要です。未指定時の `pin` は `true` で、`--no-pin` を指定すると `false` になります。同じフラグを複数回指定しても同じ値を設定するだけです。フラグ自体に値を付ける形式は parser にありません。`--no-pin` の直後に別の値を置くと、その値は独立した引数として処理され、未知の引数なら終了コード 2 になります。

## 実行時の動作

parser は `--no-pin` を見つけると `pin = false` にします。読込先確保時は `PinnedArena` の構築・backing 判定・CUDA 登録経路を通らず、計算した arena byte 数を `malloc` に渡します。成功時は標準出力に `backing: malloc, NOT pinned (--no-pin)` と表示し、そのポインタを `load_experts` に渡します。ファイル読込、レイヤーチェックサム計算、ロード統計は同じ経路で続きます。

`--stream` を併用した場合も `stream_bandwidth` に同じ読込先ポインタが渡されます。したがって `--no-pin` 指定時の転送元は通常の `malloc` 領域です。ソースはこの組み合わせを拒否せず、計測結果が pinned memory 使用時と同じ条件になるとも保証していません。

## 適用条件と副作用

`strata-load` は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効なときに CMake で生成されます。`--no-pin` はその実行時に arena の確保方法だけを選びます。要求した byte 数の通常メモリを確保し、ロード中はその領域を保持します。既定経路にある `PinnedArena` の大ページ・CUDA 登録・resident lock の処理は実行しません。

## 出力とエラー

- `malloc` が失敗すると標準エラーに `malloc failed` を出し、終了コード 1 です。
- `--file` が未指定なら標準エラーに `--file is required` を出し、終了コード 2 です。
- 読込先のファイルを開けない、seek に失敗する、要求 byte 数より短く読めないなどの場合、loader がエラーを記録し、呼び出し側が `loading the experts failed: ...` を標準エラーに出して終了コード 1 を返します。
- `--no-pin` 自体は引数を取りません。未知の引数は `unknown argument: ...` を標準エラーに出し、終了コード 2 です。

## 根拠

- `src/core/load_main.cpp:14-23` — root parser の初期値。`pin` の既定値は `true`。
- `src/core/load_main.cpp:24-45` — `--no-pin` の parser 定義、値を消費しないこと、未知引数と必須 `--file` の処理。
- `src/core/load_main.cpp:47-70` — arena byte 数、通常経路と `malloc` 経路の分岐・表示、割当失敗とロード失敗の終了経路。
- `src/core/load_main.cpp:83-98` — `--stream` 時に同じ `dst` を `stream_bandwidth` へ渡す処理。
- `src/core/pinned.cu:832-948` — loader のファイル open、seek、短読込の失敗とチェックサム処理。
- `src/core/pinned.cu:951-981` — `stream_bandwidth` が渡された host pointer から CUDA 転送を行う処理。
- `CMakeLists.txt:333-354` — GPU backend 有効時の `strata-load` target 定義。

## 調査範囲

ソース checkout の parser と呼出先を調査しました。同一 revision の既存 `strata-load` バイナリや Release 配布物は確認しておらず、実行・build は行っていません。
