# `--dump-logits`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root parser） |
| オプション | `--dump-logits PATH` |
| 別名 | なし |
| 値 | 出力ファイルのパス。文字列を1つ取る。 |

## 役割

生成位置ごとの語彙 logits を raw float データとしてファイルへ保存します。推論結果の比較・検査など、後段ツールで各位置の logits を読む用途向けです。トークナイザーはこのエンジンに含まれず、入力 token は `--tokens` または `--tokens-file` で別途与えます。

## 使い方

```sh
strata --pack pack/full --tokens 1,2,3 --max-new 1 --dump-logits /tmp/strata-logits.f32
```

モデル pack や必要な追加データの指定は環境に合わせてください。この例は `--dump-logits` の引数形式を示すもので、モデル固有の実行条件を保証するものではありません。

## 値と既定値

- `PATH` は `next("--dump-logits")` でそのまま受け取り、数値形式・拡張子・親ディレクトリの事前検証は行いません。値を省略すると parser が stderr に `--dump-logits needs a value` を出して終了コード 2 で終了します。空文字列は代入されますが、後段の `empty()` 判定で dump 無指定と同じ扱いになります。【`src/program/generate.cpp:2418-2420,2460,7066-7071`】
- 未指定時は空文字列で、dump ファイルを作りません。【`src/program/generate.cpp:428,7066`】
- 同じオプションを複数回指定した場合、値は単純代入されるため最後の指定が残ります。【`src/program/generate.cpp:2460`】
- 出力は `fopen(PATH, "wb")` で開くため、既存ファイルは切り詰められます。作成・上書きされる可能性があるパスを指定してください。【`src/program/generate.cpp:7071`】

## 実行時の動作

- 出力は先頭に2個の `int32_t`（`n_vocab`, `n_rows`）を置き、その後に各行の語彙 logits を `float` で連続出力するバイナリです。ヘッダーは最初の logits 行と同時に書かれます。行データは位置ごとに `n_vocab` 個の float です。【`src/program/generate.cpp:7060-7065,7083-7084,16010-16020`】
- 通常の生成ループでは `dump_positions = tokens.size() - 1 + max_new` を位置範囲とし、`--logits-stride` が既定の 1 なら各位置を保存します。stride を指定すると0始まりの stride 倍の位置と最後の位置を選び、重複する最後の位置は1回だけ記録します。【`src/program/generate.cpp:7065,15994-15995`; `include/strata/program/logits_selection.hpp:20-28`】
- `--logits-stride` が1より大きい場合は `--max-new 1` と `--dump-logits` の併用が必須です。条件を満たさないと stderr に要件を表示し、終了コード2になります。stride 自体は正の10進 int64 のみ受理し、符号、空白、接尾辞、ゼロ、範囲外値は拒否されます。【`src/program/generate.cpp:2461-2466,3286-3288`; `include/strata/program/logits_selection.hpp:9-18`】
- logits が通常ループで取得されるとき、このオプションは GPU から host への読み戻しを必要にし、全語彙値の有限値検査を経て行を書き込みます。したがってファイル I/O とデータ転送・走査の追加コストがあります。性能向上を意味するオプションではありません。【`src/program/generate.cpp:15994-16008,16017-16020`】

## 適用条件と副作用

- `--serve` では parser が受理し、通常の生成ループより前にファイルを開きますが、serve の要求処理からは logits dump の行書き込み経路へ進みません。そのため指定先は空ファイルとして作成・切り詰められたままになり得ます。serve 用途にはこの dump を使わないでください。【`src/program/generate.cpp:7066-7075,8354-8359,15685-15694`】
- native pack の経路は通常の per-token ループへ入らず verify window を使うため、このオプションでは logits 行が記録されません。ソースコメントも native pack は per-token dump 箇所に到達しないと説明しています。ファイルは先に開かれるので、空ファイルが残り得ます。【`src/program/generate.cpp:7061-7063,15873-15875,16651-16654`】
- ファイルを開けない場合は `strata generate: cannot write PATH` を stderr に出して終了コード1です。次元が int32 に収まらない場合は `strata generate: logits dump dimensions exceed int32`、終了コード2です。ヘッダー・行の書き込みや close に失敗した場合も stderr にエラーを出し、終了コード1になります。【`src/program/generate.cpp:7066-7074,16011-16020,16843-16845`】
- 生成処理が書き込み後に別のエラーで中断すると、部分ファイルが残る可能性があります。ヘッダーは最初の行が得られるまで書かれないため、dump 行に到達する前の失敗ではファイルが空のままの場合があります。【`src/program/generate.cpp:7061-7063,16010-16020`】

## 根拠

- 索引上のスコープとリンク: `docs/cli/README.md` の `strata-engine` root 節（`--dump-logits` は `--dump-layers` と `--dump-mixed` の間）。
- parser、値の取得、既定値: `src/program/generate.cpp:418-429,2416-2420,2460`。
- stride 検証と制約: `src/program/generate.cpp:2461-2466,3286-3288`、`include/strata/program/logits_selection.hpp:9-28`。
- ファイル形式・オープン・行出力・終了処理: `src/program/generate.cpp:7060-7085,15994-16020,16843-16845`。
- serve/native の適用範囲: `src/program/generate.cpp:8354-8359,15685-15694,15873-15875,16651-16654`。

調査はこの checkout のソースに限定しました。既存 `bin/strata` は POSIX shell wrapper であり、この checkout と同一 revision のビルド済みエンジン CLI help であることを確認できなかったため、help 出力を根拠には使用していません。出力バイナリの読み手側ツールの仕様までは調査していません。
