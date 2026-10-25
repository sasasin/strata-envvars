# `--gpu-roles`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-concurrent` |
| コマンド | `strata-concurrent` |
| オプション | `--gpu-roles` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

GPU ストリーム計測で実行する反復数を指定します。このツールの `roles` は GPU の割当先や Strata の推論ロール構成ではなく、計測ループの回数です。各反復で role plane を GPU にコピーし、`s_gemv_split_async` を呼び出します（`src/core/concurrent_main.cpp:125-143`）。

## 使い方

`experts.bin` を読み込んで GPU 側の計測反復数を 128 にする例です。

```sh
strata-concurrent --file experts.bin --gpu-roles 128
```

`--file` は必須です。usage 表示は `src/core/concurrent_main.cpp:71-76` に定義されています。

## 値と既定値

- 既定値は `256` です（`src/core/concurrent_main.cpp:57-59`）。
- 値は次の引数文字列を `std::atoi` で変換します。厳密な整数形式や範囲の検証はありません（`src/core/concurrent_main.cpp:62-69`）。
- 同じオプションを複数回指定した場合は、引数を順に処理するため最後の値が残ります（`src/core/concurrent_main.cpp:60-69`）。
- 値がない場合は標準エラーに `<option> needs a value` を出して終了コード `2` で終了します（`src/core/concurrent_main.cpp:62-65`）。数値でない文字列は `atoi` の結果 `0` になります。負数・ゼロを拒否する validation もありません。

## 実行時の動作

値は `gpu_work(gpu_roles)` に渡され、GPU 計測ループの上限として使われます。各反復では次の plane のコピーを必要に応じてキューに積み、計算ストリームでイベントを待ってから GEMV カーネルを呼びます（`src/core/concurrent_main.cpp:125-143`, `157`）。GPU 計測は「GPU only」と「BOTH」の2回行われます（`src/core/concurrent_main.cpp:175-178`）。

`--gpu-roles 0` または `atoi` 結果が 0 の値では GEMV 反復がなく、負数でも `i < roles` が成立しないため反復しません。ただし GPU 計測の開始時に最初の plane をコピーする処理はループより前に実行されます（`src/core/concurrent_main.cpp:130-143`）。この場合も表示される GPU roles/s は指定値を経過時間で割った値です（`src/core/concurrent_main.cpp:166-171`）。

`--experts` は読み込む plane 数を決め、反復中に使う次 plane の index は `experts` を法として進みます。`--gpu-roles` はこのデータ数を変更せず、計測反復数だけを指定します（`src/core/concurrent_main.cpp:57-59`, `87-90`, `135-136`）。

## 適用条件と副作用

このコマンドは CMake の `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` ブロック内で `strata-concurrent` 実行ファイルとして定義されています（`CMakeLists.txt:335-358`）。GPU runtime、GPU メモリ、CUDA stream を使う実装です（`src/core/concurrent_main.cpp:96-110`）。コマンド実行時には GPU 処理に加えて、指定されたファイルの読み込みと pinned arena の確保が行われます（`src/core/concurrent_main.cpp:78-92`）。この調査ではビルド構成別の実行可否は確認していません。

## 出力とエラー

起動時に pinned arena 容量、CPU thread 数、GPU roles 数を表示し、計測ごとに経過時間と CPU read / GPU roles/s を表示します（`src/core/concurrent_main.cpp:93-94`, `166-188`）。GPU runtime 呼び出しが失敗すると `check` が標準エラーに処理名と CUDA エラー文字列を出して終了コード `1` で終了します（`src/core/concurrent_main.cpp:28-34`, `96-110`）。

## 根拠

- parser、既定値、値の変換、usage: `src/core/concurrent_main.cpp:52-76`
- 計測ループとカーネル呼び出し: `src/core/concurrent_main.cpp:125-143`
- 値の引き渡しと計測出力: `src/core/concurrent_main.cpp:149-178`
- GPU 呼び出し失敗時の出力・終了: `src/core/concurrent_main.cpp:28-34`
- CMake target の条件と登録: `CMakeLists.txt:335-358`
