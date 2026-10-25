# `--score`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` |
| オプション | `--score` |
| 別名 | なし |
| 値 | IDS JSON ファイルのパス |

## 役割

トークン ID のセグメントをモデルへ teacher-forcing で入力し、各位置で次トークンの対数確率と上位64トークンを計算して出力します。品質比較用の実行経路で、通常の生成や server 起動とは異なります。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --score /path/to/set.ids.json
```

`--pack` は必須です。`--score-out` を省略すると、入力パスに `.tsv` を付けたパス（`set.ids.json.tsv`）へ結果を書きます。任意の出力先を指定する例:

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --score /path/to/set.ids.json --score-out /tmp/run.tsv
```

## 値と既定値

- `--score` の直後の引数を入力パスとして受け取ります。値が欠けると `--score needs a value` を stderr に出して終了コード 2 で終了します。値の型変換や拡張子検査はありません（`src/dsv41/ds4_main.cpp:1200-1208,1259`）。
- 同じオプションを複数回指定すると、ループ内の文字列代入により最後のパスが使われます（同ファイル `:1200-1208,1259`）。
- IDS ファイルは `name` と `ids` を持つセグメントを含む `quant_quality.py` 形式として読み取られます。ファイルを開けない場合は `cannot open`、セグメントを一つも抽出できない場合は `no segments (expected quant_quality.py's ids file)` で失敗します（同ファイル `:972-1003`）。実装は汎用 JSON parser ではなく、文字列検索で `"name"`、`"ids"`、配列の角括弧を探し、ID は整数列として解析します（同ファイル `:71-83,983-1002`）。
- 各セグメントの ID 数が2未満なら、そのセグメントの採点ループは0位置になります。ID の語彙範囲はこの入力処理では検証されず、採点処理で ID を logits 配列の添字として使います（同ファイル `:1049-1070`）。
- `--window` 未指定時は採点・profiling 用に16です。指定時は `atoi` で整数化され、1未満は1に補正されます。スコア処理はこの値で入力を区切ります（同ファイル `:1191,1257-1258,1297-1301,1049-1053`）。

## 実行時の動作

モデルをロードした後、`--profile-run`、`--spec-eval`、`--score` の順に非空の入力を判定します。したがって複数のモード入力を同時に渡した場合、前にあるモードが選ばれ、`--score` は実行されないことがあります。`--serve` はこれらの判定より先に処理されます（`src/dsv41/ds4_main.cpp:1282-1301`）。`--score-out` は `--score` の分岐でのみ参照され、空または未指定なら `<score入力パス>.tsv` が選ばれます（同ファイル `:1198,1260,1301`）。

各セグメントの開始時にモデル状態をリセットし、window 単位で入力して logits を取得します。各位置について full-vocabulary の log-softmax を double 精度の和で計算し、対象となる次 ID の log-probability、argmax、EOS の log-probability、EOS を除いた対象 log-probability、および上位64 ID と log-probability を TSV に書きます。セグメント別の位置数、perplexity、top-1 一致率も sidecar に記録し、進捗統計は stderr に出します（同ファイル `:1035-1095`）。

EOS ID は同じ parser の `--eos` で指定し、省略時は文字列 `1` が `atoi` で整数化されます。範囲外の EOS ID は EOS 除外計算では無効扱いとなります（同ファイル `:1190,1222,1301,1070-1074`）。`DS4_SCORE_PREFIX` が正数で、複数セグメントがある場合はセグメントを `concat` として連結します。正数で単一セグメントの場合は先頭 prefix を一度 feed して、その後の位置を採点します（同ファイル `:1013-1022,1041-1049`）。

## 適用条件と副作用

- ターゲットは CMake の `STRATA_BUILD_DSV41` が有効な場合の `strata-dsv41` executable です。同オプションは既定 OFF であり、Release での配布有無はこの調査では確認していません（`CMakeLists.txt:797-812`）。
- `--pack` が空、または `--serve` 以外の実行モード入力（`--ids`、`--encode-image`、`--score`、`--profile-run`、`--spec-eval`）がいずれも空だと usage を出して終了コード 2 です（`src/dsv41/ds4_main.cpp:1282-1285`）。モデルロードに失敗すると `maya-ds4: ...` を stderr に出し終了コード 1 です（同ファイル `:1289-1294`）。
- 出力 TSV と `<出力パス>.seg.json` は `fopen(..., "wb")` で作成され、同名ファイルがあれば切り詰めます。片方でも開けないと `strata-dsv41: cannot write <出力パス>` を stderr に出し終了コード 1 です（同ファイル `:1023-1028`）。セグメント読み込み後、出力を開いた後の feed/logits 失敗も stderr に理由を出し終了コード 1 で戻ります（同ファイル `:1042-1053`）。

## 出力とエラー

- 主出力: TSV。各行に位置、対象 ID と確率、argmax と確率、argmax 一致フラグ、EOS 確率、EOS 除外対象確率、上位64候補を書きます（`src/dsv41/ds4_main.cpp:1071-1075`）。
- sidecar: `<出力パス>.seg.json`。各セグメントの名前、行範囲、位置数、perplexity、top-1 率を記録します（同ファイル `:1023-1029,1084-1094`）。
- stderr: セグメントごとの位置数、perplexity、top-1 率、経過秒数を表示します（同ファイル `:1087-1089`）。
- 入力を開けない、セグメントがない、出力を開けない、feed/logits に失敗する場合は終了コード1です（同ファイル `:972-1003,1006-1011,1023-1028,1042-1053`）。

## 注意点

索引はこのオプションを `strata-dsv41` の項目として掲載しています（[`docs/cli/README.md`](../../README.md)）。ただし `ds4_main.cpp` の `usage()` 表示には `--score` / `--score-out` が記載されていません。一方、parser と実行分岐には両方が存在します。そのため、この文書は parser と使用箇所を根拠にしています。`--help` を実行した場合に表示される usage の記載漏れは `src/dsv41/ds4_main.cpp:85-94,1259-1260,1301` で確認できます。

## 根拠

- Parser と値取得: `src/dsv41/ds4_main.cpp:1190-1208,1259-1260`
- IDS 読み込みと検査: `src/dsv41/ds4_main.cpp:71-83,972-1003`
- 採点計算・ファイル出力: `src/dsv41/ds4_main.cpp:1006-1095`
- モード選択・既定出力: `src/dsv41/ds4_main.cpp:1282-1301`
- ビルド条件: `CMakeLists.txt:797-812`
- usage 表示と索引: `src/dsv41/ds4_main.cpp:85-94`、[`docs/cli/README.md`](../../README.md)
