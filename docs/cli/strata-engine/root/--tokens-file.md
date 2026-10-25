# `--tokens-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（root parser） |
| オプション | `--tokens-file PATH` |
| 別名 | なし |
| 値 | 事前 token 化された prompt ID を格納したファイルへのパス |

## 役割

トークナイザーを持たない engine に、prompt を token ID の列として渡します。`--tokens` の直接指定に代わる入力経路です。ファイル全体を読み込み、ID の列として解析します。parser の help にもカンマまたは空白区切りと記載されています（`src/program/generate.cpp:806-813`）。

## 使い方

```sh
strata --pack <pack-dir> --native <model-shard-1.gguf> \
  --ple-gguf <PLE-shard.gguf> --tokens-file prompt.ids --max-new 16
```

`<...>` は実際の pack / model のパスに置き換えます。`prompt.ids` は、使用モデルに対応する tokenizer で事前に作った token ID 列です。engine は `Options::tokens` に prompt として保持し、prompt 処理と後続生成に用います（`src/program/generate.cpp:418-423, 2424-2443, 7122-7123, 15850-15855`）。

## 値と既定値

- `PATH` は次の argv 要素から取得されます。値を省略すると `--tokens-file needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2416-2421, 2432-2435`）。
- ファイル内容は全量メモリーに読み込まれます。カンマを空白に置き換えたうえで、空白区切りの各要素を整数として解析します。空白だけの区切りとカンマ区切りを混在できます（`src/program/generate.cpp:2434-2439, 1097-1114`）。
- 各 ID は 0〜2,147,483,647 の範囲です。負数、整数でない要素、範囲外の値、要素なしの空ファイルは受け付けません。NUL byte を含むファイルも拒否されますが、この経路ではエラー詳細文字列は空です。形式エラーは `malformed token file: ...` を stderr に出し、終了コード 2 になります（`src/program/generate.cpp:1097-1114, 2439-2441`）。
- この option の既定値はありません。`--tokens` または `--tokens-file` のいずれか一方が必要です（`src/program/generate.cpp:2426-2443, 3168-3179`）。
- `--max-new` の既定値は 16、`--max-context` の既定値は 4096 です。prompt ID 数と生成数の合計が `--max-context` に収まらないとエラーになります（`src/program/generate.cpp:418-423, 3302-3310, 3970-3973`）。

## 実行時の動作

parser はファイルを読み取り専用で開きます。開けない場合は `cannot open token file`、読み込み時に stream error が発生した場合は `cannot read token file` を stderr に出し、どちらも終了コード 2 で終了します。ファイルへの書き込みや削除は行いません（`src/program/generate.cpp:2432-2441`）。

`--tokens` と `--tokens-file` は共通の `have_tokens` 判定で排他です。どちらを先に指定しても、2つ目の token 入力で `supply one token input only` を stderr に出して終了コード 2 になります。各 option は1回だけ指定できます（`src/program/generate.cpp:2426-2443`）。

読み込んだ配列は prompt の各位置で参照され、最終的に標準出力の `prompt  :` 行にも ID として表示されます（`src/program/generate.cpp:7122-7123, 15850-15855, 16867-16872`）。ID から文字列への tokenizer 処理はこの CLI では行いません（`src/program/generate.cpp:10-13`）。

## 適用条件と副作用

この文書は `strata-engine/root` の通常 parser に対する説明です。`--serve` の要求 prompt は標準入力上の `GEN <max_new> <id,id,...>` で別途渡されるため、`--tokens-file` の内容が各 serve request に使われるわけではありません（`src/program/generate.cpp:7497-7518`）。通常 parser では、serve 時に明示的な token 入力がなければ内部の初期値 `{248045}` を置きます（`src/program/generate.cpp:3168-3172`）。

Qwen3.6 family の model を `--native` / `--model` で指定すると、通常 parser の処理前に専用 `qwen35::run` parser へ振り分けられます。その parser に `--tokens-file` の分岐はありません。serve 時は未知 option として警告して値を読み飛ばし、非 serve 時は usage を出して終了コード 2 となります。Qwen3.6 の token 入力は別形式の `--tokens` です（`src/program/generate.cpp:2393-2408`; `src/qwen35/q36_engine.cu:3742-3795`）。

## 出力とエラー

この option 固有の成功メッセージはありません。token 入力・ファイル読込・内容解析・prompt と context の不整合によるエラーは stderr に出て終了コード 2 になります。ファイルを開けない、または内容が読めないときの診断は上記の通りです。unknown option は `unknown argument: ...` と usage を stderr に出して終了コード 2 です（`src/program/generate.cpp:2787-2792`）。正常終了時は標準出力に prompt ID と生成 ID を出力します（`src/program/generate.cpp:16867-16875`）。

## 根拠

- parser help と option 宣言: `src/program/generate.cpp:806-813, 418-423`
- PATH 取得、ファイル読込、重複指定と形式検証: `src/program/generate.cpp:2416-2443`
- ID 列の区切り・範囲・空入力 validation: `src/program/generate.cpp:1097-1114`
- token 入力必須条件、serve 既定入力、prompt/context 上限: `src/program/generate.cpp:3168-3179, 3302-3310, 3970-3973`
- prompt と出力での利用: `src/program/generate.cpp:7122-7123, 15850-15855, 16867-16875`
- family dispatch と Qwen3.6 専用 parser: `src/program/generate.cpp:2393-2408`; `src/qwen35/q36_engine.cu:3742-3795`
