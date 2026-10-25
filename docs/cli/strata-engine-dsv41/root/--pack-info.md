# `--pack-info`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立 engine CLI） |
| オプション | `--pack-info` |
| 別名 | なし |
| 値 | 取らない mode flag。対象 pack は `--pack <dir>` で指定する |

## 役割

pack の記述ファイルと tensor 配置を読み、モデル概要、expert/dense tensor の型や容量、device kernel がない型、pack が参照するファイルの有無・長さを標準出力へ報告します。通常の推論用モデルロードに入る前の pack 確認に使えます。ソースコメントと実装では、この mode は host 側だけで実行し、device・重みの読み込み・lock を使わないとされています（`src/dsv41/ds4_main.cpp:1275-1280`、`src/dsv41/ds4_packinfo.cpp:1-4`）。

## 使い方

```sh
./strata-dsv41 --pack-info --pack /path/to/maya-ds4
```

`strata-dsv41` は `STRATA_BUILD_DSV41=ON` で構成された場合に定義される独立 executable です。Release での配布有無は索引でも未確認とされています（`CMakeLists.txt:797-811`、[`docs/cli/README.md`](../../README.md) の strata-dsv41 項）。

## 値と既定値

- `--pack-info` 自体は値を取りません。parser はこのフラグを立てるだけで、既定状態は `false` です（`src/dsv41/ds4_main.cpp:1196,1264`）。
- `--pack <dir>` が必要です。`--pack` の値は `Options::pack` に文字列として格納されます。`--pack-info` が指定されていて `--pack` が空なら usage を stderr に出し、終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1208,1209,1275-1279`）。
- `--pack` の値に対する専用の存在確認・正規化は parser では行いません。複数回指定すると後の値が残ります。`--pack-info` を複数回指定しても同じ mode flag が立つだけです（`src/dsv41/ds4_main.cpp:1200-1209,1264`）。

## 実行時の動作

引数解析完了後、`--pack-info` は通常の serve / 推論 / score / profile / image encode 経路より先に処理されます。したがって `--serve` など他の mode flag と併記しても pack-info 分岐が選ばれます。`--pack` 以外のオプションも構文上は引数解析されますが、この分岐からはモデル設定として `pack_info` に渡されません（`src/dsv41/ds4_main.cpp:1200-1273,1275-1285`）。

`pack_info` は `<dir>/ds4.txt` の key/value 行からモデル設定を読み、`<dir>/tensors.txt` の `file` / `t` 行から shard 名、tensor 型、ファイル番号、offset、byte 数、shape を読みます。各 shard について `ds4.txt` の `model_dir` と shard 名を連結したパスを開き、ファイル末尾位置から長さを調べます。重みの内容を読み込むのではなく、最大 tensor end までのサイズがあるかを検査します（`src/dsv41/ds4_packinfo.cpp:57-74,79-115,121-150`）。pack 形式の生成元スクリプトは `ds4.txt` と `tensors.txt` の形式を説明しています（`tools/dsv41/pack_gguf.py:9-14`）。

レポートには、モデルの層数・expert 数など、layer ごとの expert 型と byte 数、型別 tensor 数、expert/token の容量推定、dense tensor の型と分類容量、DSpark/Engram のメタデータ、device kernel のない tensor 型が含まれます。kernel 対応型は `ds4_iq` の対応判定と固定の追加型リストから構成され、expert と dense で判定対象が異なります（`src/dsv41/ds4_packinfo.cpp:25-45,153-209,211-263`）。未対応型は「CPU lane が担当し VRAM tier には置けない」と出力されます（`src/dsv41/ds4_packinfo.cpp:251-262`）。

## 適用条件と副作用

- この parser / pack report は `strata-dsv41` の root CLI に属します。CMake では `STRATA_BUILD_DSV41` が OFF 既定で、ON のときに `strata-dsv41` target に `ds4_packinfo.cpp` が含まれます（`CMakeLists.txt:797-811`）。
- 読み取り対象は pack の `ds4.txt`、`tensors.txt` と、それらが指す weight shard のファイル情報です。参照先の shard は開いてサイズを調べますが、重みデータ自体は読みません。GPU/device 初期化、通常の model load、lock はこの mode 分岐の後にあるため実行されません（`src/dsv41/ds4_main.cpp:1275-1292`、`src/dsv41/ds4_packinfo.cpp:121-150`）。
- `--pack-info` の処理自体はファイルを生成・変更しません。アクセス可能な pack ディレクトリが必要です。実際の存在検査基準は `model_dir/<shard name>` と、各ファイルに記録された最大 tensor end です（`src/dsv41/ds4_packinfo.cpp:121-150`）。

## 出力とエラー

レポートおよび pack 検査エラーは `stdout` に出力され、関数の戻り値がプロセス終了コードになります（`src/dsv41/ds4_main.cpp:1280`）。確認できる戻り値は次のとおりです。

- `0`: report 作成と参照ファイル検査が成功し、末尾に `files: ... all present and long enough` を出力します（`src/dsv41/ds4_packinfo.cpp:264-270`）。
- `1`: `ds4.txt` / `tensors.txt` がない、tensor が一つもない、または必要な expert tensor が欠けている場合です（`src/dsv41/ds4_packinfo.cpp:59-64,81-85,117-119,164-174`）。
- `2`: 参照ファイルの shard 名がない、shard がない、または最大 tensor end に対してファイルが短い場合です。report の末尾に不足件数と load できない旨を出します（`src/dsv41/ds4_packinfo.cpp:125-150,264-268`）。
- `--pack` がない場合は usage を `stderr` に出して 2 で終了します（`src/dsv41/ds4_main.cpp:1275-1279`）。未知のオプションは `stderr` に名前と usage を出して 2 で終了します（`src/dsv41/ds4_main.cpp:1269-1272`）。

## 根拠

- parser と mode 分岐: `src/dsv41/ds4_main.cpp:1187-1209,1264-1285`
- pack 記述・shard 検査: `src/dsv41/ds4_packinfo.cpp:57-150`
- report 内容と終了値: `src/dsv41/ds4_packinfo.cpp:153-270`
- pack 形式: `tools/dsv41/pack_gguf.py:9-14`
- executable の build 条件: `CMakeLists.txt:797-811`

Release archive や実ビルド済み CLI の `--help` は実行していません。この文書は指定 commit の parser と実装を根拠にし、配布実績や別 build 条件での CLI 動作までは主張しません。
