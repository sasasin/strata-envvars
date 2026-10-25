# `--pack`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（usage 内の表示名は `maya-ds4`） |
| オプション | `--pack` |
| 別名 | なし |
| 値 | pack ディレクトリのパス（文字列） |

## 役割

DeepSeek-V4.1 engine が読む pack の場所を指定します。通常の推論・serve・画像 encode 等ではモデルのメタデータ、tensor 索引、重みファイル、Engram データの読込元になります。`--pack-info` と併用した場合は pack 情報の検査・表示先になります。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 --ids 1,2,3
strata-dsv41 --pack /models/example/maya-ds4 --pack-info
```

`--pack` は `--ids`、`--serve`、`--encode-image`、`--score`、`--profile-run`、`--spec-eval` のいずれかの実行指定と組み合わせます。`--pack-info` は別の早期処理経路です（`src/dsv41/ds4_main.cpp:91-93,1275-1285`）。この optional executable は `STRATA_BUILD_DSV41=ON` のとき CMake に登録され、既定では build されません（`CMakeLists.txt:798-811`）。

## 値と既定値

- 値を1つ取ります。値が次の argv にない場合は `--pack needs a value` を stderr に出して終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1200-1208`）。
- parser は値をそのまま `Options::pack` に代入します。パスの存在、形式、空白、絶対・相対パスなどを parser 段階では検証・正規化しません。空文字を渡した場合は後段で未指定相当になります（`src/dsv41/ds4_main.cpp:1209,1275-1284`）。
- 既定値はありません。`Options::pack` の初期値は空文字列で、pack が空なら `--pack-info` でも通常実行でも usage を表示して終了コード `2` になります（`src/dsv41/ds4_model.hpp:25-27`, `src/dsv41/ds4_main.cpp:1275-1284`）。usage の表示形式は `--pack <model>/maya-ds4` です（`src/dsv41/ds4_main.cpp:85-93`）。
- 同じオプションを複数回指定すると parser は各回代入するため、最後の値が使われます（`src/dsv41/ds4_main.cpp:1200-1209`）。値の受け取り時に次の引数がオプションかどうかは判定しません。

## 実行時の動作

通常経路では値が `Options::pack` に入り、`Model::load` から `Pack::load` に渡されます。pack path 直下の `ds4.txt` と `tensors.txt` を読み、`ds4.txt` の `model_dir` と `tensors.txt` に記載されたファイル名を結合して重みファイルを読み取り専用で開きます。pack ディレクトリの `engram.bin` も読みます。GGUF 形式の場合は重み shard の read-only mapping も作ります（`src/dsv41/ds4_model.cu:261-280,312-358,1852-1859`）。

`--pack-info` が指定されると推論モデルのロード前に分岐し、`pack_info(o.pack, stdout)` の戻り値で終了します。この経路は device、重みの model load、lock を使わず、pack のメタデータと tensor 情報を表示します。ただし参照先の重みファイルの存在と必要サイズは検査します（`src/dsv41/ds4_main.cpp:1275-1280`, `src/dsv41/ds4_packinfo.cpp:57-85,121-145,264-270`）。

pack path は他の既定パスにも使われます。`--expert-profile` を省略すると `<pack>/expert-profile.bin` が profile の保存先となり、値 `none` なら無効化されます（`src/dsv41/ds4_main.cpp:1216,1286-1287`）。serve 中に `STRATA_DS4_SLOT_KEEP` が有効で、`STRATA_DS4_SLOT_DIR` が未指定なら会話 slot のディレクトリは `<pack>/slots` です。slot 機能はそこに状態ファイルを作成し、期限切れや不整合の slot を削除することがあります（`src/dsv41/ds4_main.cpp:331-345,577-586`）。したがって `--pack` 自体は入力場所の指定ですが、通常経路ではその pack ディレクトリ配下が既定の書込先にもなり得ます。

## 適用条件と副作用

- `strata-dsv41` の全モードで pack 指定が必要です。索引上も optional DeepSeek-V4.1 executable の root scope に属します（`src/dsv41/ds4_main.cpp:1187-1209,1275-1284`; [`docs/cli/README.md`](../../README.md#strata-dsv41-optional-deepseek-v41-engine-executable)）。
- パックの構造や対応 geometry の検証は parser ではなく後続ロード側で行います。不完全な geometry や対象外 geometry はロード失敗になります（`src/dsv41/ds4_model.cu:1853-1865`）。
- `--pack-info` は model load を迂回するため、通常推論の GPU 初期化・モデル読込の副作用を持ちません。一方、serve で slot 保存が有効な場合は `<pack>/slots` 作成や slot ファイルの書込・削除が発生する可能性があります（`src/dsv41/ds4_main.cpp:1275-1280,577-586`）。

## 出力とエラー

- pack 値が欠落、または空である場合は usage を stderr に表示し、終了コード `2` です（`src/dsv41/ds4_main.cpp:1202-1206,1275-1284`）。
- 通常経路で `ds4.txt`、`tensors.txt`、参照重みファイル、`engram.bin` を開けない場合や Engram データを読めない場合、loader はエラー文字列を返します。呼出側は `maya-ds4: <理由>` を stderr に出して終了コード `1` で終了します（`src/dsv41/ds4_model.cu:261-280,312-358,1853-1859`; `src/dsv41/ds4_main.cpp:1290-1294`）。
- `--pack-info` では不備の内容を stdout に `pack-info: ...` 等として表示し、検出エラーに応じて非ゼロ終了します。`ds4.txt` / `tensors.txt` 欠落や tensor 不在は `1`、参照ファイル欠落・短縮は `2` です（`src/dsv41/ds4_packinfo.cpp:57-85,117-119,264-270`）。

## 根拠

- parser、値欠落、必須判定、pack-info 分岐: `src/dsv41/ds4_main.cpp:1187-1209,1275-1294`
- pack 読込と path の解決: `src/dsv41/ds4_model.cu:261-358,1852-1865`
- pack の初期値: `src/dsv41/ds4_model.hpp:25-27`
- pack-info の検査と終了値: `src/dsv41/ds4_packinfo.cpp:57-85,121-145,264-270`
- profile / serve slot との相互作用: `src/dsv41/ds4_main.cpp:331-345,577-586,1286-1287`
- executable の build 条件: `CMakeLists.txt:798-811`
