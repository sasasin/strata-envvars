# `--profile-run`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（トップレベル） |
| オプション | `--profile-run` |
| 別名 | なし |
| 値 | 必須の ID JSON ファイルパス |

## 役割

ID JSON の各 segment を DeepSeek-V4.1 モデルに順に読み込ませ、expert の利用回数 profile を集計・保存する実行モードです。各 segment は独立した新しいモデル状態から処理されます。logits の計算・出力は要求しません。[`ds4_main.cpp:1097-1127`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp) に処理本体があります。

この実行ファイルは CMake の `STRATA_BUILD_DSV41=ON` で追加される独立 CLI です。同オプションは既定で OFF です（[`CMakeLists.txt:797-810`](../../../../../../Niko1221/Strata/CMakeLists.txt)）。索引は Release での配布有無をこの source inventory から断定していません（[`docs/cli/README.md:1353-1357`](../../README.md)）。

## 使い方

```sh
./build/strata-dsv41 \
  --pack /models/dsv41/maya-ds4 \
  --profile-run ./set.ids.json \
  --expert-profile /tmp/dsv41-expert-profile.bin
```

`--pack` は必須です。ここでは pack 内の既定 profile を意図せず上書きしないよう、`--expert-profile` で `/tmp` の保存先を指定しています。`--window` を省略した場合の profile-run 用 window は 16 token です（[`ds4_main.cpp:1191-1192, 1257, 1297-1299`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。

## 値と既定値

- 値は `--profile-run` の次の argv 要素をそのままファイルパスとして受け取ります。値を省略すると parser の共通 helper が `<option> needs a value` を stderr に出し、終了コード 2 で終了します（[`ds4_main.cpp:1200-1207, 1261`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
- この option 自体に既定パスはありません。空文字を渡した場合 `prof_ids` は空のままとなり、他の実行モードも指定されていなければ usage を出して終了コード 2 になります（[`ds4_main.cpp:1198-1199, 1282-1285`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
- parser はパスの存在や JSON 構文を事前検証しません。処理関数はファイル全体を読み、テキスト中の `"name"` とそれに続く `"ids"`、括弧内の整数列を簡易走査します。公式 `tools/quant_quality.py` の生成形式は `segments` 配列内の `{ "name": ..., "ids": [...] }` です（[`ds4_main.cpp:972-1003`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)、[`quant_quality.py:59-69`](../../../../../../Niko1221/Strata/tools/quant_quality.py)）。形式外の JSON を厳密に拒否する parser ではありません。
- 複数回指定時は parser が最後に読んだパスで置き換えます（[`ds4_main.cpp:1261`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。

## 実行時の動作

1. parser は値を `prof_ids` に格納します。pack が指定されていない、または他の実行モードを含めて実行モードがない場合は usage を stderr に出して終了コード 2 です（[`ds4_main.cpp:1261, 1282-1285`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
2. `--expert-profile` が省略されると profile の保存先は `<pack>/expert-profile.bin` になります。値 `none` は profile の読み書きを無効にします。それ以外の明示パスが既定値に優先します（[`ds4_main.cpp:1216, 1286-1287`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。既存 profile があればモデル load 時に読み込まれ、ID JSON の処理で得た回数が加算されます（[`ds4_model.cu:2537-2545, 7090-7096`](../../../../../../Niko1221/Strata/src/dsv41/ds4_model.cu)）。
3. `--serve` が同時に指定されると serve 分岐が先に実行され、profile-run は呼ばれません。serve 以外では `--profile-run` が `--spec-eval`、`--score`、通常の ids 処理より先に選ばれます（[`ds4_main.cpp:1295-1301`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
4. ID JSON の各 segment の開始時に model state を reset し、ID 列を最大 `window` 個ずつ `feed(..., logits_rows=0, ...)` します。window は `--window N` の値で、parser は `atoi` 後に最低 1 に丸めます。未指定は内部で 16 です（[`ds4_main.cpp:1110-1120, 1257, 1297-1299`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
5. 各 segment の処理後に segment 名、token 数、累計 token 数、経過秒、累計 token/s を stderr に出します。10 segment ごと、および正常終了時に profile を保存します（[`ds4_main.cpp:1121-1127`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。環境変数 `DS4_TRACE` が設定されていれば、model 側は routing trace もそのパスに開きます。これは `--profile-run` の引数ではありません（[`ds4_model.cu:1153, 6203-6212, 7078-7088`](../../../../../../Niko1221/Strata/src/dsv41/ds4_model.cu)）。

## 適用条件と副作用

- モデルを load する通常の推論経路で使います。`--pack-info` が指定されると pack 情報表示の分岐が先行し、profile-run は実行されません（[`ds4_main.cpp:1275-1285`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
- `--window` は profile-run の feed の分割幅を決めます。既定値は 16、明示値は 1 未満が 1 に補正されます。`feed` は build/model 側の chunk 条件に応じて内部の window/chunk 経路を選びます（[`ds4_main.cpp:1257, 1297-1299`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)、[`ds4_model.cu:9056-9067`](../../../../../../Niko1221/Strata/src/dsv41/ds4_model.cu)）。
- 保存先 profile は `<path>.tmp` に書き、成功時に本来の profile パスへ置換します。したがって既存の profile ファイルは更新されます。書き込みまたは置換に失敗した場合は一時ファイルを削除しますが、`save_profile()` 自体はエラーを返さず、stderr のエラー表示もありません（[`ds4_model.cu:8996-9006`](../../../../../../Niko1221/Strata/src/dsv41/ds4_model.cu)）。`--expert-profile none` の場合は保存処理が何もせず戻ります（同箇所）。
- source の `usage()` 表示には `--profile-run` が列挙されていませんが、parser と実行分岐には実装されています（[`ds4_main.cpp:85-94, 1261, 1299`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。そのため `--help` はこの option の使用例・値規則を案内しません。

## 出力とエラー

- 入力ファイルを開けない場合は `strata-dsv41: <path>: cannot open`、認識できる segment がない場合は `strata-dsv41: <path>: no segments (expected quant_quality.py's ids file)` を stderr に出し、終了コード 1 です（[`ds4_main.cpp:972-1003, 1101-1106`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
- 各 segment の `feed` が失敗すると `strata-dsv41: <model error>` を stderr に出し、終了コード 1 です（[`ds4_main.cpp:1113-1118`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。model load 失敗は `maya-ds4: <model error>`、終了コード 1 です（[`ds4_main.cpp:1289-1294`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)）。
- 正常完了時の処理本体は 0 を返します。profile 保存の失敗は上述の通り、呼び出し元に失敗として伝わりません（[`ds4_main.cpp:1124-1127`](../../../../../../Niko1221/Strata/src/dsv41/ds4_main.cpp)、[`ds4_model.cu:8996-9006`](../../../../../../Niko1221/Strata/src/dsv41/ds4_model.cu)）。

## 調査範囲

同一 revision の source checkout と `docs/cli/README.md` の索引を確認しました。ビルド済み CLI の `--help` や Release artifact は確認していません。ソースの `usage()` は option を表示しないため、上記の仕様は parser と実装本体を根拠にしています。

## 根拠

- Parser、必須引数判定、実行モードの優先順位: `src/dsv41/ds4_main.cpp:1200-1273, 1275-1301`
- ID JSON 読み込みと segment 実行: `src/dsv41/ds4_main.cpp:967-1004, 1097-1127`
- profile のロード、更新、保存: `src/dsv41/ds4_model.cu:2537-2545, 7090-7096, 8996-9006`
- window feed の実装: `src/dsv41/ds4_model.cu:9056-9067`
- CLI の生成条件: `CMakeLists.txt:797-810`
- 索引上の配置と Release 配布についての注記: `docs/cli/README.md:1353-1381`
