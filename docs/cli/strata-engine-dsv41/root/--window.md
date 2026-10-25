# `--window`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` |
| オプション | `--window` |
| 別名 | なし |
| 値 | 整数として解釈される feed 幅 |

## 役割

入力 ID 列をモデルへ渡す幅を指定します。通常の prompt 入力では ID 列をこの数ずつ `Model::feed` に渡し、`--score`、`--profile-run`、`--spec-eval` では各モードの入力処理が同じ値で区切ります。モデル内部で chunk 経路を使うかどうかは別の条件でも決まり、この値が GPU の内部処理幅を常に直接指定するわけではありません（`src/dsv41/ds4_main.cpp:1049-1053,1112-1120,1144-1153,1360-1368`; `src/dsv41/ds4_model.cu:9056-9067`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1,2,3,4 --window 2
```

上の例では通常 prompt の入力を最大2 IDずつ feed します。モデル pack は必須です。`--window` は `strata-dsv41` のトップレベル引数で、通常実行と採点・profile 系モードが共有します（`src/dsv41/ds4_main.cpp:1209-1213,1255-1260,1282-1285`）。

## 値と既定値

- 値は必須です。引数がない場合、共通の値取得処理が `<option> needs a value` を stderr に出し、終了コード2で終了します（`src/dsv41/ds4_main.cpp:1200-1208,1257`）。
- 文字列を `atoi` で整数化し、結果が1未満なら1に補正します。したがって `0`、負数、整数として読めない文字列は1になります。`atoi` のため小数指定は整数部分までの解釈です。整数形式の検証や明示的な上限チェックはありません（同ファイル `:1257`）。
- 同じオプションを複数回指定すると、parser の逐次代入により最後の値が残ります（同ファイル `:1200-1208,1257`）。
- 省略時の既定値は実行モードで異なります。
  - `--profile-run`、`--spec-eval`、`--score`: 16（同ファイル `:1191,1297-1301`）。
  - 通常の `--ids` prompt で `--dump-logits` を指定: 16（同ファイル `:1356-1358`）。
  - 通常の `--ids` prompt で `--dump-logits` を省略: `max(16, min(m.feed_unit(), 1 << 30))`（同ファイル `:1356-1358`）。`feed_unit()` はモデルの chunk が有効なら `max(chunk, max_context)`、そうでなければ内部の固定幅 `kWin` を返します（`src/dsv41/ds4_model.cu:9085`）。
- `--serve`、`--pack-info`、画像 encode 経路では `--window` の値は処理幅として参照されません。`--serve` はモデルロード後にサーバー処理へ戻り、pack-info は parser 後の早期分岐です。画像 encode は通常 prompt の feed ループより前に戻ります（`src/dsv41/ds4_main.cpp:1275-1281,1295-1301,1303-1327`）。

## 実行時の動作と相互作用

- `--score` は各 segment を `window` 以下の幅で feed し、各 feed でその幅分の logits を要求します。入力末尾の未採点 token は feed 範囲から除きます（`src/dsv41/ds4_main.cpp:1049-1053`）。
- `--profile-run` は segment ごとにモデル状態を reset し、全 ID を `window` 以下の幅で feed します。logits は要求しません（同ファイル `:1110-1120`）。
- `--spec-eval` も各 segment を reset して同じ幅で prompt feed します。最後の feed だけ1行の logits を要求し、その後の token 生成・speculative verify はこの prompt 分割ループの外で行います（同ファイル `:1141-1163`）。
- 通常 prompt では `--ids` から得た ID 列を `window` 以下の幅で feed します。各 feed に対し、`--dump-logits` があれば全行、なければ最後の feed のみ1行分の logits を要求します。dump 指定時は各 feed の logits をファイルへ書き込みます（同ファイル `:1356-1368`）。
- `Model::feed` は内部 chunk が有効で、今回の `n` が `chunk_min` 以上なら、全行 logits 要求または `pick_path(n)` の結果に応じて `forward_chunks` または `feed_windows` を選びます。それ以外は `feed_windows` を使います。したがって `--window` は CLI からの feed 分割幅を制御しますが、内部経路の選択もモデル状態と各 feed の行数に依存します（`src/dsv41/ds4_model.cu:9056-9067`）。
- 複数のモード引数が同時にある場合、`--serve` が先に実行されます。それ以外は `--profile-run`、`--spec-eval`、`--score` の順に選択され、該当する先行モードがあれば後続モードおよび通常 prompt 経路では `--window` を使いません（`src/dsv41/ds4_main.cpp:1295-1301`）。

## 出力と失敗経路

- 通常 prompt では stderr の進捗行 `prompt: ... (windows of N)` に実際に使った幅が表示されます（`src/dsv41/ds4_main.cpp:1371-1373`）。`--window` 自体はファイルを作りません。
- feed が失敗すると通常 prompt は `maya-ds4: <理由>`、score/profile-run/spec-eval は `strata-dsv41: <理由>` を stderr に出し、終了コード1で戻ります（同ファイル `:1042-1053,1113-1118,1146-1151,1361-1365`）。モデル側で確認できる失敗例には context 上限超過と token ID 範囲外があります（`src/dsv41/ds4_model.cu:7891-7900`）。
- オプション名は parser で受理されますが、`usage()` の表示には `--window` が載っていません。これは usage 文言の記載範囲であり、parser 定義と使用箇所は同じファイル内にあります（`src/dsv41/ds4_main.cpp:85-94,1257-1258`）。この調査では同一 revision の実行可能バイナリを用いた `--help` 確認はしていません。

## 適用条件と制約

`strata-dsv41` は CMake の `STRATA_BUILD_DSV41=ON` で生成される独立 executable で、この option は既定で OFF です（`CMakeLists.txt:797-811`）。この調査では build、GPU 実行、Release artifact の配布状況は確認していません。

## 根拠

- Parser、既定値、モード分岐: `src/dsv41/ds4_main.cpp:1187-1208,1255-1301,1356-1368`
- 各モードの feed: `src/dsv41/ds4_main.cpp:1006-1053,1097-1127,1130-1153`
- Model feed 経路と feed unit: `src/dsv41/ds4_model.cu:7889-7900,9056-9067,9085`
- Build 条件: `CMakeLists.txt:797-811`
