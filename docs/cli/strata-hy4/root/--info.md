# `--info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--info` |
| 別名 | なし |
| 値 | `.strata` ファイルのパスを1つ取る |

## 役割

`.strata` ファイルのモデル情報を調べ、1行の `key=value` 情報を標準出力へ出します。主モデルの manifest からアーキテクチャ、層数、hidden size、語彙数、expert 数、EOS token、draft 機能、画像対応などを報告します。Vision shard 自体を指定した場合は Vision の構成情報を出します。情報出力への分岐は通常のモデル実行・GPU 初期化経路より前に行われます。

## 使い方

```sh
# 主モデルの情報を表示
strata-hy4 --info Hy4-Flash.strata

# 主モデルの情報と、指定した Vision shard の利用可否を表示
strata-hy4 --info Hy4-Flash.strata --vision Hy4-Flash-Vision.strata

# Vision shard 自体の構成情報を表示
strata-hy4 --info Hy4-Flash-Vision.strata
```

## 値と既定値

- ファイルパスを1つ取ります。parser は文字列として受け取り、存在・形式の検証は情報表示処理がファイルを開く段階で行います。既定値はありません。
- `--info` を複数回指定した場合は、parser が最後に代入したパスが使われます。
- `--info` の値が欠落すると `ERR --info needs a value` を標準出力に出して終了コード `2` で終了します。
- 空文字列を値にした場合は内部の `info_file` が空のままとなり、情報表示分岐に入りません。その後は通常実行経路に進みます。

## 実行時の動作

parser はコマンドライン全体を読み終えてから `print_info(info_file, vision_path)` を呼びます。このため `--vision` は `--info` の前後どちらに書いても情報表示に反映されます。その他の引数も先に parser を通るため、未知の引数があれば情報表示へ進む前にエラーになります。情報表示へ進んだ後は、`--vision` 以外の通常実行オプションは処理に使われません。

指定ファイルを `StrataFileReader` で開きます。ヘッダーの profile が Vision shard の場合はそのファイルを `vision_probe` で検査し、`arch=hy4flash-vision` と層数、各種寸法、tensor 数、image pad token を出力します。主モデルの場合は manifest を解析し、DFly2 drafter の所定 tensor が両方あれば `drafter=dfly2`、それ以外は `drafter=none` とします。`--vision FILE` が指定されていれば、そのファイルが Vision profile と必要な manifest / tensor 条件を満たすか検査し、結果を `images=1` または `images=0` として報告します。指定しない場合の `images=1` は、このビルドが画像入力機能を持つことを示します。

## 適用条件と副作用

- 対象文書の scope は索引上の `strata-hy4`（CUDA/HIP）です。Metal と SYCL の同名オプションは別 scope です。
- 情報表示への分岐自体は GPU モデルのロード前ですが、`main` 冒頭のプラットフォーム処理は先に実行されます。Linux HIP では条件に応じてこのプロセスの NUMA memory policy を設定し、CUDA build では `CUDA_MODULE_LOADING` が未設定なら `EAGER` または volta-forever 検出時の `LAZY` をプロセス環境に設定します。
- 主モデルと Vision shard の読み込みは読み取り専用です。Vision shard の検査に失敗した場合、主モデル情報の出力は継続し、警告を標準エラーに出して `images=0` とします。

## 出力とエラー

- 主モデルでは `arch=hy4flash layers=... hidden=... vocab=... experts=... eos=... drafter=... images=... image_pad=... image_max_pixels=...` 形式の1行を標準出力に出します。Vision shard では `arch=hy4flash-vision layers=... hidden=... out_hidden=... patch=... merge=... tensors=... image_pad=...` を出します。正常終了はコード `0` です。
- 主ファイルを開けない、または `.strata` reader がヘッダーや manifest section を読めない場合は `open: ...` を標準エラーに出してコード `1` で終了します。
- 主モデルに対する `--vision` の検査に失敗した場合は `vision shard: ...` を標準エラーに出しますが、主モデル情報の出力と終了コード `0` は維持されます。Vision shard 自体を `--info` の対象にした場合は検査失敗を同じ prefix で標準エラーに出し、コード `1` で終了します。
- 非対応の Vision profile / config、dtype、必要 tensor 欠落は shard 検査エラーになります。主モデル manifest の必須フィールド不足など、`parse_manifest` 内で例外となる malformed manifest の終了表示・終了コードは、この経路では個別に捕捉されておらず、ここで確認した範囲から特定できません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:52-87` — `print_info` のファイル読み込み、Vision shard / 主モデルの分岐、出力フィールド、`--vision` の検査とエラー扱い。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-346` — 引数解析前に実行される Linux HIP NUMA policy / CUDA module loading 処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-391` — `--info` 値取得、欠落時の診断と終了コード、および値の保存。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:448` — `--vision` 値の保存。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-507` — 未知引数の失敗経路と、引数解析後の情報表示分岐。
- `engine/src/hy4flash/run/hy4_vision.h:67-124` — Vision shard profile、manifest、config、dtype、必須 tensor の検証。
- `engine/src/hy4flash/run/hy4_manifest.h:78-124` — 主モデル manifest の各フィールド解析。
- `engine/src/artifact/strata_reader.cpp:33-110` — `.strata` を読み取り専用で開き、ヘッダー / manifest section の失敗を返す処理。
- `engine/include/strata/core/volta_forever.hpp:74-94` — 未設定時の `CUDA_MODULE_LOADING` 設定。
- `engine/include/strata/platform/numa_balancing.hpp:71-94` — Linux で条件に応じて行う NUMA memory policy 処理。
