# `strata-overlap --experts`

- 対象: CMake で生成される診断用 CLI `strata-overlap` のトップレベル option
- 調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）
- parser: `src/core/overlap_main.cpp`

## 役割

処理対象にする expert blob の個数を指定します。`strata-overlap` は `--file` のファイルから先頭側の blob を読み、コピーと S2 GEMV の直列実行と二重バッファによる重複実行を比較します。この option は両方の実行ループの反復数を変えます。通常の推論 CLI の設定ではなく、CMake が生成する診断用プログラムです（`CMakeLists.txt:360-363`）。

## 値と既定値

値は整数として `std::atoi` で読み込みます。省略時は `64` です。たとえば次のように指定します。

```sh
strata-overlap --file /path/to/experts.bin --experts 64
```

parser に範囲検証や変換エラー検出はありません。0 は arena の要求サイズが 0 となり、`PinnedArena` は 0 byte で確保せず戻るため、後続の `arena.valid()` 判定で `arena allocation failed` となります。負数も拒否されず、確保サイズ計算時に `uint64_t` へ変換されるため、実用可能な expert 数として扱えません。入力値は正の整数にしてください。

## 効果と相互作用

`--experts N` は `N × 409,600` byte の pinned arena を要求します（1 role のコード plane は `640 × 2560 / 4` byte）。ファイルからは各 index `i` について `i × 1,382,400` byte の位置へ seek し、409,600 byte を読みます。したがって `N` 個分の先頭 blob のコード領域が必要です。S2 plane の scales は別途固定値で作られます。

同じ `N` が、直列ループ、重複ループ、結果表示の件数に使われます。出力の serial / overlapped 所要時間、1 expert 当たり時間、および `overlap / serial` 比率はこの件数で比較されます。`--tpr` は各 GEMV の threads-per-row を設定しますが、件数や読み込む範囲は変えません。

## 適用条件と副作用

- `--file` は必須です。相対パスは実行時の作業ディレクトリから解決されます。
- 読み込む量と GPU 上の処理回数を増やすため、値は利用可能なファイル長とホスト/GPU メモリに合わせてください。
- この診断はファイル全体の expert や通常の推論を処理しません。各 blob のコード部分を role-sized plane として読み、合成した入力・scale でコピーと GEMV を測ります。
- 実行時に CUDA device allocation、CUDA stream/event の作成、GPU への転送と GEMV を行います。測定後は device buffer、event、stream を解放します。

## 出力とエラー

成功時は role plane のサイズ、読み込んだ role-sized plane の数と arena backing、serial / overlapped の時間と比率、および測定範囲についての NOTE を stdout に出します。

- option に値がない場合は `<option> needs a value` を stderr に出して終了コード 2。
- 未知の option は usage を stderr に出して終了コード 2。
- `--file` がない場合は `--file is required` を stderr に出して終了コード 2。
- arena が無効なら `arena allocation failed`、ファイルを開けなければ `cannot open <path>`、要求した byte 数に満たない読み込みなら `short read on expert <i>` を stderr に出して終了コード 1。
- CUDA runtime 呼び出し失敗は `check()` が操作名と CUDA エラー文字列を stderr に出し、終了コード 1 で終了します。

## 根拠

- option parser、既定値、値変換、`--file` 必須判定、usage/error: `src/core/overlap_main.cpp:41-59`
- role plane のサイズ、arena 確保、ファイルの seek/read、短い読み込みの失敗: `src/core/overlap_main.cpp:61-85`
- serial/overlapped の反復数と `--tpr` の利用: `src/core/overlap_main.cpp:105-147`
- 計測結果、比率、測定対象外の注意、資源解放: `src/core/overlap_main.cpp:149-168`
- CUDA エラー時の stderr と終了: `src/core/overlap_main.cpp:27-32`
- 0 byte の arena を確保せず戻る実装: `src/core/pinned.cu:408-412`; 無効判定: `src/core/overlap_main.cpp:69-70`
- CMake target と GPU runtime のリンク: `CMakeLists.txt:360-363`
