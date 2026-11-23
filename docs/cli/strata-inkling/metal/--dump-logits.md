# `--dump-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--dump-logits PATH` |
| 別名 | なし |
| 値 | 出力先パスを1つ取る。形式・拡張子・ディレクトリの事前検証なし |

## 役割

指定時に Metal 版 Inkling の診断用 forward を1回実行し、最後の入力 token に対応する logits を指定ファイルへ書き出します。`--selfcheck` を付けなくてもこの forward が実行され、`--selfcheck` も付けた場合は同じ forward を共有します。prompt は `--ids` で指定でき、省略時はソース内の決定的な既定 token 列が使われます。【`engine/src/inkling2/metal/ink_metal_main.cpp:511-529,544-547`】

## 使い方

```sh
# 新しい一時ディレクトリに、既定 prompt の logits を保存する
outdir="$(mktemp -d)" && strata-inkling-metal --model ./model.strata --dump-logits "$outdir/logits.f32"
```

Metal 版の実行ファイルと利用可能な `.strata` モデルが必要です。`--ids` を併用すると診断に使う token ID 列を指定できます。保存先は `wb` で開くため、既存ファイルを指定すると内容を切り詰めます。【`engine/src/inkling2/metal/ink_metal_main.cpp:444,459,512-515,545`】

## 値と既定値

- `PATH` は次の argv 要素を文字列として受け取ります。数値形式や拡張子、親ディレクトリの存在確認はありません。【`engine/src/inkling2/metal/ink_metal_main.cpp:432-437,459`】
- 値を省略すると stderr に `missing value for --dump-logits` を出し、終了コード `2` で終了します。未知の引数も stderr に `unknown arg: ...` を出して終了コード `2` です。【`engine/src/inkling2/metal/ink_metal_main.cpp:434-436,464-467`】
- 同じオプションを複数回指定した場合、変数への代入が後勝ちとなり、最終値だけが出力先になります。空文字列を渡すと `empty()` 判定で dump 処理は行われません。【`engine/src/inkling2/metal/ink_metal_main.cpp:418,459,517,544`】
- オプション自体に値の既定値はありません。`--dump-logits` を省略するとファイル出力はありません。【`engine/src/inkling2/metal/ink_metal_main.cpp:418-419,459,517,544`】

## 実行時の動作

1. parser が `PATH` を `dump_logits_path` に格納します。【`engine/src/inkling2/metal/ink_metal_main.cpp:432-437,459`】
2. モデルをロードし runner を初期化した後、`--selfcheck` が指定されたか、パスが空でなければ診断 forward に入ります。したがって `--dump-logits PATH` は単独でも forward を起動します。`--selfcheck` との併用で forward が二重になることはなく、同じ結果を表示・保存します。【`engine/src/inkling2/metal/ink_metal_main.cpp:481-494,517-533`】
3. 入力 token 列の長さ `P` に対して logits を計算し、`logits_last_only_idx = P - 1` として最後の位置だけを unembed します。runner はこの index が非負なら指定 index の1行だけを計算し、出力配列には `vocab_unpadded` 個の `float` をコピーします。【`engine/src/inkling2/metal/ink_metal_main.cpp:519-529,531`; `engine/src/inkling2/metal/ink_metal_runner.h:75-76,1995-2001,2118-2121`】
4. 全 logits が有限値であれば出力先を `fopen(PATH, "wb")` で開き、`lg` の全要素を `sizeof(float)` 単位で書きます。ファイルにはヘッダーや token ID は付加されません。要素数はモデル設定の `vocab_unpadded` に従います。【`engine/src/inkling2/metal/ink_metal_main.cpp:535-547`; `engine/src/inkling2/metal/ink_metal_common.h:231-238`】

## 適用条件と副作用

- `--model` が必要です。`--info` は parser 中に即時 return する別経路なので、同じ起動引数に `--dump-logits` があっても dump には進みません。モデルのロードまたは runner 初期化に失敗した場合も dump 前に終了します。【`engine/src/inkling2/metal/ink_metal_main.cpp:439-443,470-494`】
- ファイルは `wb` で作成・切り詰めされます。`fopen` が失敗した場合は何も書かず、エラー表示や明示的な非ゼロ終了はありません。`fwrite` と `fclose` の戻り値も確認していないため、書き込み途中の失敗はこの処理では報告されません。【`engine/src/inkling2/metal/ink_metal_main.cpp:544-547`】
- logits に非有限値が1つでもあると、stderr ではなく標準出力の `[SELFCHECK]` 行を出した後に終了コード `1` で return し、ファイル書き込みには進みません。forward 失敗もエラーを stderr に出して終了コード `1` です。【`engine/src/inkling2/metal/ink_metal_main.cpp:531-543`】
- dump 後も main の処理は続き、指定があれば `--spec-check`、`--bench`、`--par-sweep` などの処理を実行します。【`engine/src/inkling2/metal/ink_metal_main.cpp:544-547,560-616`】

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-467` — 変数初期化、argv parser、値の取得、欠落値・未知引数のエラー。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-494` — model 必須条件、モデルロードと runner 初期化。
- `engine/src/inkling2/metal/ink_metal_main.cpp:511-547` — 既定 prompt、診断 forward、有限値検査、出力ファイル処理。
- `engine/src/inkling2/metal/ink_metal_runner.h:75-76,1995-2001,2118-2121` — logits の最終位置選択と FP32 出力配列へのコピー。
- `engine/src/inkling2/metal/ink_metal_common.h:231-238` — `vocab_unpadded` のモデル設定への読み込み。
