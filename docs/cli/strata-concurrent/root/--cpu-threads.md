# `--cpu-threads`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-concurrent` |
| コマンド | `strata-concurrent` |
| オプション | `--cpu-threads` |
| 別名 | なし |
| 値 | `N`。次の argv 要素を C の `atoi` で整数化する。 |

## 役割

CPU の読み取りループで起動する worker thread 数を指定します。この実行ファイルは CPU の読み取りと GPU の転送・計算を同時に実行し、帯域競合を測るためのプログラムです。Strata の通常の推論 CLI に対する CPU worker 設定ではありません（`src/core/concurrent_main.cpp:1-15, 52-59, 112-123`）。

## 使い方

実行ファイルと入力ファイルがある環境で、たとえば次のように指定します。

```sh
./strata-concurrent --file ./experts.bin --cpu-threads 6
```

`--file` は必須です。上の値 `6` は指定例であり、推奨値を示すものではありません（`src/core/concurrent_main.cpp:60-76`）。

## 値と既定値

- `N` は次のコマンドライン引数から `std::atoi` で変換されます。未指定時の既定値は `6` です（`src/core/concurrent_main.cpp:57-59, 67-69`）。
- 正数・ゼロ・負数の範囲検査や上限検査はありません。`atoi` が 0 を返す入力（数値に変換できない文字列や空文字列を含む）は 0 として扱われます。変換範囲外の入力について、コードはエラー処理を定義していません（`src/core/concurrent_main.cpp:67-69`）。
- `--cpu-threads` を複数回指定すると、その都度変数に代入され、最後の値が使われます（`src/core/concurrent_main.cpp:60-69`）。
- オプションの直後に値がない場合は stderr に `--cpu-threads needs a value` を出して終了コード 2 で終了します（`src/core/concurrent_main.cpp:60-65, 68`）。

## 実行時の動作

CPU 処理を有効にする測定では `cpu_threads` 回だけ `std::thread` を生成し、各 thread が pinned arena を繰り返し読みます。これは CPU 読み取り帯域を測るループで、コメントにも実際の VNNI kernel ではないと記載されています（`src/core/concurrent_main.cpp:112-123, 149-156, 187-188`）。

プログラムは「CPU only」「GPU only」「BOTH」の順で測定します。この指定は CPU worker を作る「CPU only」と「BOTH」に作用し、「GPU only」では CPU worker を起動しません。指定値は冒頭の arena 情報にも表示されます（`src/core/concurrent_main.cpp:93-94, 149-178`）。0 以下なら thread 生成ループの条件 `t < cpu_threads` を満たさないため worker は起動しません（`src/core/concurrent_main.cpp:155`）。

## 適用条件と副作用

`strata-concurrent` は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効な CMake 構成の中で定義されています（`CMakeLists.txt:333-358`）。このオプションはプロセス内で測定用 CPU thread 数を変えます。ソース上、この値を設定ファイルや環境変数から読み込んだり、通常の推論 engine に渡したりする処理はありません（`src/core/concurrent_main.cpp:52-75, 149-156`）。

## 出力とエラー

起動時に pinned arena の容量と指定された thread 数を stdout に表示し、各測定結果と競合率も stdout に出します（`src/core/concurrent_main.cpp:93-94, 170-188`）。値そのものに対する validation error はありません。値を欠落させると stderr にエラーを出して終了コード 2、未知の引数は usage を stderr に出して終了コード 2 です（`src/core/concurrent_main.cpp:60-75`）。

## 根拠

- parser、既定値、値変換、欠落値処理: `src/core/concurrent_main.cpp:52-75`
- thread 数の適用箇所と測定モード: `src/core/concurrent_main.cpp:149-178`
- CMake の生成条件と target: `CMakeLists.txt:333-358`
- 索引上のコマンド階層と option scope: `docs/cli/README.md:1437-1444`

同一 revision の CLI バイナリは実行していません。CMake target が GPU backend を必要とするため、ここでは parser と動作をソースから確認しています。Release 配布物での有無は調査していません。
