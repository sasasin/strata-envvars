# `--file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-overlap` |
| コマンド | `strata-overlap`（root） |
| オプション | `--file` |
| 別名 | なし |
| 値 | 入力ファイルのパス。空でない文字列が必要 |

## 役割

重なり測定用の expert データを読む入力ファイルを指定します。ファイルから expert ごとのコード領域を host 側 arena に読み込み、その後 GPU 上で転送と GEMV を行う比較処理へ進みます。Strata の通常の推論用 `strata` CLI のオプションではなく、GPU backend 有効時に CMake が作る `strata-overlap` 実行ファイルのオプションです（`CMakeLists.txt:333-363`）。

## 使い方

```sh
strata-overlap --file ./experts.bin
```

`--experts` の既定値は 64 です。必要に応じて読み込む件数を指定できます。

```sh
strata-overlap --file ./experts.bin --experts 8
```

parser は `--file` の直後の argv を値として受け取ります。複数回指定した場合は最後の値が残ります（`src/core/overlap_main.cpp:45-53`）。

## 値と既定値

値は次の argv 文字列をそのままパスとして扱います。パスの存在、ファイル種別、完全なデータ形式は parser 段階では検証しません。未指定または空文字列の場合は `--file is required` を stderr に出して終了コード 2 で終了します。オプションの値が argv に続かない場合は `<option> needs a value` を stderr に出し、終了コード 2 で終了します（`src/core/overlap_main.cpp:45-59`）。

## 実行時の動作

指定パスを binary mode で開きます。`--experts` 件について、ファイルのオフセット `i * 1,382,400` から 460,800 byte（`640 * 2560 / 4`）ずつ読み、pinned arena 内の各領域へ格納します。つまりこの実装は expert blob の固定 stride と先頭コード領域を前提にし、ファイル全体を解析したり scale 領域を読むものではありません（`src/core/overlap_main.cpp:61-85`）。

読み込み後、実装は GPU メモリ・stream・event を確保し、同じ expert コードで serial と copy/compute overlap の処理を実行して時間と比率を標準出力に表示します（`src/core/overlap_main.cpp:87-103`, `105-157`）。従ってこのオプションを使った実行は入力ファイルの読み取りだけでは終わらず、GPU 実行を伴います。

## 適用条件と副作用

この実行ファイルは `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効な CMake 構成で定義されます（`CMakeLists.txt:333-363`）。この調査ではビルドや実行は行っていないため、個別 platform/backend での利用可否は確認していません。

指定ファイルを開いて読み取ります。通常経路では入力データの一部を pinned host arena に保持し、GPU にコードを転送して計算します。出力ファイルの作成・変更はソース上で確認できません（`src/core/overlap_main.cpp:68-98`, `129-147`）。この測定がモデル化するのはコメント上、CPU expert path、router、実 token の全 role 数を含まない比較です（`src/core/overlap_main.cpp:154-157`）。

## 出力とエラー

- ファイルを開けない場合、`cannot open <path>` を stderr に出して終了コード 1 で終了します（`src/core/overlap_main.cpp:71-74`）。
- 各読み込みで要求 byte 数を読めない場合、`short read on expert <i>` を stderr に出して終了コード 1 で終了します（`src/core/overlap_main.cpp:76-82`）。
- pinned arena の確保失敗は `arena allocation failed`、CUDA runtime API の失敗は呼び出し名と runtime error 文字列を stderr に出し、いずれも終了コード 1 で終了します（`src/core/overlap_main.cpp:12-16`, `68-70`, `89-103`）。
- 読み込み成功後は arena の backing 情報と serial/overlapped の時間、ratio などを stdout に出します（`src/core/overlap_main.cpp:66`, `85`, `149-157`）。

## 根拠

- parser、値の取り出し、未指定・不足・未知 option の経路: `src/core/overlap_main.cpp:41-59`
- 固定寸法・読み込み offset/byte 数・open/read 失敗: `src/core/overlap_main.cpp:61-85`
- GPU 処理と測定出力: `src/core/overlap_main.cpp:87-103`, `105-168`
- GPU backend 有効時の target 定義: `CMakeLists.txt:333-363`
- 索引上のコマンド階層と option scope: `docs/cli/README.md:1446-1452`

このソースには `strata-overlap` 専用の `--help` 分岐がありません。調査では実行せず、parser と実装を根拠にしています。また、`--experts` の値の validation や、実ファイルが想定された expert pack であることの完全な検証はこのコードから確認できません。ここではそれらを保証された仕様として扱っていません。
