# `strata-overlap`（GPU overlap 診断 CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-overlap` |
| コマンド | `strata-overlap`（トップレベル） |
| 実装 | `src/core/overlap_main.cpp` |
| 用途 | GPU への expert code 転送と GEMV 計算を重ねた場合の時間を、同一プロセスの serial 実行と比較する診断用プログラム |

## 役割

`strata-overlap` は製品の推論 CLI やモデルサーバーではなく、GPU 上の転送と計算の重なりを調べるビルド生成プログラムです。入力ファイルから複数の expert 相当 code 領域を読み、同じ GEMV を「同一 stream で順番に実行」と「copy stream と compute stream に分けて実行」の二通りで行い、経過時間と比率を表示します（`src/core/overlap_main.cpp:1-11,105-157`）。

CMake では `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効な場合の GPU runtime 節で target が定義されます。ソースは CUDA runtime API を直接呼びます（`CMakeLists.txt:333-363`, `src/core/overlap_main.cpp:15,89-103`）。通常の Terminal CLI の `strata` コマンドとは別の実行ファイルです（[`000_cli_tools.md`](../../../000_cli_tools.md)）。

## 基本的な使い方

ビルドした `strata-overlap` を、実装が想定する expert データファイルに対して実行します。

```sh
strata-overlap --file pack/full/experts.bin --experts 64 --tpr 32
```

`--file` は必須です。省略時や未知の引数では usage/error を stderr に出して終了コード 2 になります。値を要するオプションの値が欠ける場合も終了コード 2 です（`src/core/overlap_main.cpp:45-59`）。各 option の値と効果は [`--file`](--file.md)、[`--experts`](--experts.md)、[`--tpr`](--tpr.md) を参照してください。

この例は GPU 計測を実際に実行し、host pinned memory と device memory を確保して GPU kernel を起動します。`--file` の指定や引数確認だけを行う dry-run／plan モードはありません。実データ・GPU に対する計測が目的でない場合は実行しないでください。

## 実行モードと主要な動作

このコマンドに対話モードや推論モードはなく、引数を解析した後に計測を一度実行します。

1. 固定寸法の role (`n_in=2560`, `n_out=640`) を使い、`experts` 個分の pinned arena を確保します。入力ファイルを binary mode で開き、expert `i` ごとに `i * 1,382,400` byte の位置へ seek し、role code 領域分の code bytes を読み込みます。不足すると `short read on expert i` を stderr に出して終了コード 1 です（`src/core/overlap_main.cpp:61-85`）。
2. 2 個の device code buffer と入力・scale・出力 buffer を確保します。入力 vector と scale は固定値で初期化し、SForm も固定値で選択されます（`src/core/overlap_main.cpp:87-103`）。
3. serial 計測では各データの転送と GEMV を default stream に順番に投入し、最後に同期します。overlap 計測では double buffer と event を使い、次の転送中に現在のデータを別 stream で計算します（`src/core/overlap_main.cpp:105-147`）。
4. serial / overlapped の合計時間、expert あたり時間、`overlap / serial` 比率を stdout に表示します。比率 1.00 は重なりなし、1.00 未満は overlap がある計測結果として表示されます（`src/core/overlap_main.cpp:149-157`）。
5. device buffer、event、stream を解放して終了します。ソース上、この処理は結果ファイルを作成しません（`src/core/overlap_main.cpp:159-168`）。

## 注意点と調査範囲

- コードコメントは入力 byte を実データの Q2_0 code として扱うと説明していますが、このプログラム自身はモデル形式やファイル全体のメタデータを検証しません。指定位置から所定長を読み込めることだけを確認します（`src/core/overlap_main.cpp:68-83`）。
- この計測は固定寸法の単一 role 相当の GEMV を使います。出力にも CPU expert path、router、実 token の 1440 roles をモデル化しないと明記されています。したがって結果だけから実モデルの推論速度や全体性能を判断できません（`src/core/overlap_main.cpp:61-66,154-157`）。
- `--experts` と `--tpr` は `std::atoi` で整数化されますが、数値形式・正の範囲・境界の validation はありません。特に `experts` は arena サイズ計算、読み込み回数、計測回数、最後の比率計算に使われるため、正の妥当な整数を指定してください。`--tpr` は GEMV 呼び出しへ渡されます（`src/core/overlap_main.cpp:42-53,68-70,114-120,149-153`）。
- 入力を開けない場合、pinned arena 確保に失敗した場合は stderr に理由を出して終了コード 1 です。CUDA runtime 呼び出しが失敗した場合はエラー名と runtime の説明を stderr に出して終了コード 1 で終了します（`src/core/overlap_main.cpp:27-31,68-74,87-103`）。
- この checkout の実装は独自の `--help` を持たず、`--help` も未知 option として usage を出して終了します（`src/core/overlap_main.cpp:51-57`）。同一 revision での help 実行は行わず、parser と実行経路をソースで確認しました。
- CMake の target 定義と当該ソースを調べました。異なる GPU backend / hardware 上での build・実測、および Release 配布物の有無はこの調査では確認していません。

## 関連文書

- [`strata-overlap` のオプション一覧](../../../README.md) — CLI 索引内のこの target の項目。
- [`--file`](--file.md)、[`--experts`](--experts.md)、[`--tpr`](--tpr.md) — 個別 option 文書。
- [`000_cli_tools.md`](../../../000_cli_tools.md) — CLI とビルド生成実行ファイルの位置づけ。

## 根拠

- `src/core/overlap_main.cpp:1-11` — 診断の目的と計測上の位置づけ。
- `src/core/overlap_main.cpp:41-59` — 引数 parser、既定値、必須引数、usage/error 経路。
- `src/core/overlap_main.cpp:61-85` — 固定 role 寸法、入力ファイル読込、失敗経路。
- `src/core/overlap_main.cpp:87-103,105-157` — GPU buffer、serial / overlap の計測、出力とモデル化の制約。
- `src/core/overlap_main.cpp:159-168` — GPU resource 解放と正常終了。
- `CMakeLists.txt:333-363` — GPU runtime 条件と `strata-overlap` target 定義。
