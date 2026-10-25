# `--score-out`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--score-out` |
| 別名 | なし |
| 値 | 出力ファイルのパス。空白を含む場合はシェルで引用する |

## 役割

`--score` による teacher-forced scoring の TSV 出力先を指定します。 scoring は ID ファイルの各 segment をモデルに通し、各位置の対数確率と上位64候補を記録します。出力先の隣には segment 範囲などを記録した `<出力パス>.seg.json` も作られます（`src/dsv41/ds4_main.cpp:962-966, 1023-1029, 1073-1086`）。

## 使い方

```sh
strata-dsv41 --pack PACK2 --score data/quant_quality/v1/set.ids.json --score-out /tmp/quality-run.tsv
```

`--pack` と `--score` は必要です。`--score-out` を省略した場合は、`--score` の値に `.tsv` を連結したパスが使われます（`src/dsv41/ds4_main.cpp:1282-1294, 1301`）。

## 値と既定値

- 値は次の argv 要素をそのままパス文字列として受け取ります。値を省略すると `--score-out needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1208, 1260`）。
- パス形式や拡張子の検証はありません。指定値が空文字列なら、後段の `score_out.empty()` 判定により省略時と同じ `<score IDS の値>.tsv` が使われます（`src/dsv41/ds4_main.cpp:1301`）。
- 同じオプションを複数回指定した場合、parser の文字列代入により最後の値が使われます（`src/dsv41/ds4_main.cpp:1200-1208, 1260`）。
- `--score-out` 単独では scoring を開始しません。`--pack` といずれかの実行モードが必要で、score モードには `--score` が必要です（`src/dsv41/ds4_main.cpp:1282-1284`）。

## 実行時の動作

parser は `--score-out` の値を `score_out` に保存し、`--score` が選択されるとその値（空なら既定パス）を `score()` に渡します。`score()` は TSV と `<パス>.seg.json` の両方を `fopen(..., "wb")` で開くため、同名の既存ファイルは切り詰められます。親ディレクトリは作成しません（`src/dsv41/ds4_main.cpp:1259-1260, 1301, 1023-1028`）。

`score()` は入力 IDS を読み込んだ後、各 segment の結果を TSV に書き、segment の名前・行範囲・位置数・perplexity・top-1 比率を companion JSON に記録します。`--window` が省略された scoring の既定 chunk は 16 です（`src/dsv41/ds4_main.cpp:1029-1035, 1049-1089, 1297-1301`）。モデルは score 処理より先にロードされます（`src/dsv41/ds4_main.cpp:1289-1296, 1301`）。

同時に複数の処理モードを指定した場合、score より前に `--serve`、`--profile-run`、`--spec-eval` の分岐が評価されます。これらが選ばれる場合は `--score-out` の出力先は使われません（`src/dsv41/ds4_main.cpp:1296-1301`）。`--eos` も score に渡り、EOS token の確率補正に使われますが、出力パスの規則は変えません（`src/dsv41/ds4_main.cpp:1222, 1301, 1070-1074`）。

## 適用条件と副作用

- scoring 用の `--score IDS.json` と DeepSeek-V4.1 pack が必要です。`--score` の入力は `name` と `ids` を含む segment 構造として読まれます（`src/dsv41/ds4_main.cpp:972-1003, 1282-1294`）。
- 成功時に指定パスの TSV と `.seg.json` の2ファイルを書き込みます。両方とも既存ファイルを上書きします（`src/dsv41/ds4_main.cpp:1023-1029`）。
- 出力先を2つとも開けない場合は `strata-dsv41: cannot write <出力パス>` を stderr に出して終了コード 1 で戻ります。片方だけ開けた場合も同じ経路で、すでに開けたファイルを切り詰めている可能性があります（`src/dsv41/ds4_main.cpp:1023-1027`）。
- 入力 IDS を開けない場合や segment が見つからない場合は stderr に理由を出して終了コード 1 です。処理中に `feed` / logits が失敗した場合もエラーを stderr に出して終了コード 1 になります（`src/dsv41/ds4_main.cpp:972-1003, 1006-1011, 1042-1053`）。

## 出力とエラー

TSV は stdout ではなく指定したファイルへ書かれます。各 segment の位置数、perplexity、top-1 比率と所要時間は stderr に表示されます（`src/dsv41/ds4_main.cpp:1073-1089`）。書き込み中に `fprintf` / `fflush` の戻り値を検査する処理は確認できず、ディスク容量不足などの遅延書き込み失敗時の通知・終了状態はソースから確定できません（`src/dsv41/ds4_main.cpp:1073-1095`）。

現行 parser は `--score-out` を認識しますが、`usage()` のヘルプ文字列には `--score` / `--score-out` の記載がありません（parser: `src/dsv41/ds4_main.cpp:1259-1260`; usage: `src/dsv41/ds4_main.cpp:85-94`）。

## 根拠

- parser と値取得: `src/dsv41/ds4_main.cpp:1200-1208, 1259-1260`
- 必須モード・モデルロード・モード選択・既定出力名: `src/dsv41/ds4_main.cpp:1282-1301`
- IDS segment 読み込み・出力ファイルの生成・書き込み: `src/dsv41/ds4_main.cpp:962-1003, 1006-1095`
- scoring の利用例: `docs/DEEPSEEK41.md:130-138`
- `--score-out` の実呼び出し例と prefix/window 設定: `tools/dsv41/test_prompt_skip.py:39-49`（このテストは GPU・pack 等を要するため、今回実行していません）。

