# `--stream`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load` |
| オプション | `--stream` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

expert arena のファイル読み込み後に、ホストメモリから GPU への転送帯域を複数の転送サイズで測り、さらに設計上の前提値を使った per-token の参考表を出力します。読み込み自体を有効にするフラグではなく、通常の読み込みに追加の測定を行います（`src/core/load_main.cpp:21-22, 66-67, 83-114`）。

## 使い方

```sh
strata-load --file experts.bin --layers 2 --stream
```

`--file` で入力ファイルを指定します。`--layers` を省略すると2層を読み込みます（`src/core/load_main.cpp:15-22, 30-35, 45-47`）。

## 値と既定値

- 値は不要です。指定すると内部フラグが `true` になり、指定しない場合は `false` です。同じ指定を繰り返しても有効化されるだけです（`src/core/load_main.cpp:22, 35`）。
- 数値引数のような値検証はありません。直後の文字列は別引数として通常の parser に渡され、未知の引数なら `unknown argument` で終了します（`src/core/load_main.cpp:24-43`）。
- `--help` の usage 表示には `--stream` が記載されていませんが、parser は受理します（`src/core/load_main.cpp:35-39`）。

## 実行時の動作

通常の expert 読み込みとチェックサム出力が成功した後にのみ、`--stream` の測定を行います（`src/core/load_main.cpp:66-83`）。転送粒度は1 blob、16 blobs、1 layer、arena 全体です。各サイズが読み込み量を超えるケースは飛ばし、反復回数はチャンク数に応じて3回または8回です（`src/core/load_main.cpp:86-99`）。続いて1 blob の転送を64回測定し、`E = 663.6 MB` と複数の hit rate 仮定から per-token の帯域・時間表を表示します。これは実際の推論 token 処理の計測ではなく、固定の設計値を用いた試算です（`src/core/load_main.cpp:100-113`）。

転送 helper は `chunk` サイズの CUDA device buffer を一度確保して再利用し、ホストから device への非同期コピーを行います。最初に計測外のウォームアップを1回実行し、CUDA stream を同期してから計測します（`include/strata/core/pinned.hpp:197-206`; `src/core/pinned.cu:951-981`）。

`--no-pin` と併用しても測定分岐は実行されます。この場合は arena の確保先が `malloc` ですが、そのポインタが同じ転送 helper に渡されます。helper 自体に pinned / pageable を切り替える処理はありません（`src/core/load_main.cpp:21, 52-64, 83-95`; `src/core/pinned.cu:951-974`）。

## 適用条件と副作用

`strata-load` は CUDA または HIP の GPU runtime が有効な構成でのみ CMake build されます（`CMakeLists.txt:333-354`）。実行時には通常の arena 確保・ファイル読み込みに加え、各測定で CUDA device buffer と stream を作成し、H2D コピーを発行してから破棄します（`src/core/load_main.cpp:52-67, 83-105`; `src/core/pinned.cu:951-981`）。

`--stream` 自体は入力ファイルや設定を書き換えません。arena 読み込みの副作用・資源量は `--layers` 等にも依存します。既定は2層で、ソースコメントは大きな arena の pinning がページキャッシュを追い出し得るため、小さい値から測る意図を記しています（`src/core/load_main.cpp:3-6, 16-22`）。

## 出力とエラー

成功すると測定ごとのチャンクサイズ・帯域・転送量・所要時間と、per-token の仮定表が標準出力に追加されます（`src/core/load_main.cpp:86-113`）。device buffer の `cudaMalloc` が失敗すると helper は標準エラーに失敗理由を出して負の時間を返し、その測定行は出力されません（`src/core/pinned.cu:951-960`; `src/core/load_main.cpp:93-98`）。この測定失敗を `main` は終了エラーにせず、後続の処理を続けます。CUDA stream 作成・コピー・同期など、`cudaMalloc` 以外の戻り値は helper 内で検査されません（`src/core/pinned.cu:962-981`）。

通常の必須引数・読み込みエラーはこのフラグの測定より前に発生します。`--file` 欠落や未知引数は終了コード2、arena 確保または読み込み失敗は終了コード1です（`src/core/load_main.cpp:27-43, 45, 58-70`）。

## 根拠

- parser、既定値、help 表示、通常読み込み後の分岐: `src/core/load_main.cpp:14-45, 66-83`
- 測定粒度と per-token 試算: `src/core/load_main.cpp:83-120`
- CUDA 転送実装と allocation failure: `src/core/pinned.cu:951-981`
- stream 統計型と helper の宣言: `include/strata/core/pinned.hpp:186-206`
- build 条件: `CMakeLists.txt:333-354`

この調査では parser・実装ソースを確認し、CLI help 表示は実行していません。GPU 実行による実機挙動や backend ごとの実測差は確認していません。
