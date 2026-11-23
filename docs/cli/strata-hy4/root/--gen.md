# `--gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--gen` |
| 別名 | なし |
| 値 | 整数。生成ループの上限として使用 |

## 役割

オフライン実行でプロンプトの続きを最大何 token 生成するかを指定します。生成数は指定値を上限とし、EOS token が先に出ればそこで停止します。また、`--ctx` / `--max-context` を正の値で指定しない場合は、`--gen` の値を使って自動コンテキスト長を見積もります。

## 使い方

```sh
# ids.txt の token 列を入力し、続きの token ID を最大128個生成する
strata-hy4 --model SQ64.strata --tokens ids.txt --gen 128 --out ./result
```

## 値と既定値

- 値は `atoi` で整数へ変換され、既定値は `0` です。明示的な範囲検証や不正な数値文字列の拒否はありません。そのため、数値として読めない文字列は `atoi` の結果 `0` になり、先頭の数値部分だけが読める文字列はその数値として扱われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:352,486`）。
- 値が正の場合、通常の greedy decode または DFly2 speculative decode が最大その数まで生成します。EOS が出た場合は上限前でも停止します（`engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1054`、`engine/src/hy4flash/run/hy4_spec.hip.h:253-262`）。
- `0` または負数では通常の生成ループに入りません。DFly2 の生成モードも `gen > 0` が条件です（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,1018`）。負数を正値へ補正する処理はありません。
- オプションの値が欠けている場合は `ERR --gen needs a value` を stdout に出して終了コード `2` で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。

## 実行時の動作

- `--tokens` から読み込んだ prompt を prefill した後、正の `--gen` では次 token を選び、1 token ずつ追加入力して logits を計算します。通常経路では token ID 列を標準出力に表示し、DFly2 経路では同様に speculative runner へ上限値を渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:632-638,748-789,992-1008,1018-1076`、`engine/src/hy4flash/run/hy4_spec.hip.h:243-262`）。
- `--ctx` と `--max-context` は同じ `max_ctx` 変数に代入されます。正の context 長が設定されていなければ、prompt token 数 + `--gen` + 16 を自動値として計算します。画像入力で prompt の image-pad token が展開された場合も、自動値を展開後の長さから再計算します（`engine/src/hy4flash/run/hy4_main.hip.cpp:402,487,632-638,679-691`）。従って `--gen` は生成上限だけでなく、モデルメモリ計画に使う context 長にも影響します（同 `:648-659`）。
- `--draft dfly2` を指定しても `--gen` が正でなければ speculative generation 分岐は有効になりません。ただし DFly2 初期化の判定自体は `--draft dfly2` で行われ、`--gen` の条件より前に実行されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,711-716`）。
- `--serve` の場合、CLI の `--gen` は `ServeOpts` に転送されません。生成上限はサーバーの `GEN <max_new>` リクエスト側で指定されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:7,138-149`）。

## 適用条件と副作用

- `--gen` による生成は `--serve` を付けないオフライン実行に適用されます。通常のオフライン経路では `--model` が必須で、入力 token が空（ただし DFly batch 入力がある場合を除く）なら `no tokens` を出して終了コード `2` になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-615,686-690`）。
- 通常経路・DFly2 経路とも、`--out`（既定 `.`）に `gen_ids.txt` を書きます。`--margins` を併用した場合は `margins.txt` と `hashes.txt` も書きます。prefill 結果の `top5.txt` は生成数にかかわらず書き出され、`--dump` または `--save-logits` があれば `logits.npy` も保存されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,693-699,769-778,1010-1017,1097-1108`）。同名ファイルがあれば通常の出力ストリームで開き直して内容を置き換えます。出力ストリームの open/write 成否はこの箇所で検査されません。
- DFly2 の runner は prompt の次 token を先に選ぶため、`--gen 1` でもその token を出力します。EOS token が選ばれた場合はその token を生成列に含めてから停止します（`engine/src/hy4flash/run/hy4_spec.hip.h:251-262`）。通常経路も選んだ token を列へ追加した後 EOS を確認します（`engine/src/hy4flash/run/hy4_main.hip.cpp:1050-1054`）。

## 出力とエラー

- 通常のオフライン生成は標準出力に `generated ids: ...` を出し、標準エラーに生成数と処理時間などを出します。DFly2 経路も同じ標準出力形式で token 列を表示します（`engine/src/hy4flash/run/hy4_main.hip.cpp:1002-1008,1075-1098`）。
- 生成時の forward 失敗は `forward: ...` を標準エラーに出して終了コード `1`、DFly2 runner の失敗は `spec: ...` を標準エラーに出して終了コード `1` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:1002-1005,1055-1059`）。
- `--gen` 単独に対する負数・上限超過のエラー経路は確認できません。整数変換後の値を使う実装で、生成上限値の追加 validation は見当たりません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:352,375-383,486` — 既定値、引数値の取得、整数変換、値欠落時の終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-659,686-705` — token 読み込み、自動 context 長、メモリ計画と Runner 初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1017,1018-1108` — DFly2 適用条件、生成分岐、表示とファイル出力。
- `engine/src/hy4flash/run/hy4_spec.hip.h:243-262` — DFly2 runner における生成上限、EOS、出力 token のカウント。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:7,138-149` — serve 経路の option 転送と要求ごとの `GEN <max_new>`。
