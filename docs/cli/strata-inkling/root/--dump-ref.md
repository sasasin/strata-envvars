# `strata-inkling --dump-ref`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（ルート） |
| オプション | `--dump-ref` |
| 別名 | なし |
| 値 | 出力ファイルのパスを1個取る |

## 役割

モデルと選択中の backend で入力 token 列を teacher-forced 実行し、各 token の FP32 logits を参照データとしてファイルに保存します。実装コメントでは `--kld-eval` による形式・backend 間の parity 確認用とされています（`engine/src/inkling2/ink_main.cpp:323-325`）。

## 使い方

```sh
# モデルと token ID 列から参照データを作成する
strata-inkling --native model.strata --prompt-ids 1,2,3,4 --dump-ref /tmp/reference.bin

# --prompt-ids を省略すると、組み込みの token ID 列で作成する
strata-inkling --native model.strata --dump-ref /tmp/reference.bin
```

`--native`（別名 `--model`）でモデルを指定します。`--dump-ref` は出力パスを受け取り、`--prompt-ids` は任意の comma 区切り ID 列を渡します（`engine/src/inkling2/ink_main.cpp:402-405,482-483`）。

## 値と既定値

- `--dump-ref` の直後の引数が出力先です。値が欠けていると `missing value after --dump-ref` を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:381-384,402-403`）。
- `--prompt-ids` がなければ ID 列 `[1, 2, 3, 4, 5, 6, 7, 8]` を使います（`engine/src/inkling2/ink_main.cpp:334-339`）。指定した場合は `parse_id_list` が10進整数を読み、カンマを区切りとして列にします。空の列や整数として読めない要素は解析失敗になります。ここでは token ID の語彙範囲を検査していません（`engine/src/inkling2/ink_serve.h:256-270`）。
- `--dump-ref ""` のように空文字を渡すと、dump 分岐条件が成立せず、後続の通常モード選択へ進みます。同じオプションを複数回指定した場合も最後の値が残るため、最後が空文字なら同様です（`engine/src/inkling2/ink_main.cpp:402-403,548-549`）。

## 実行時の動作

`--dump-ref` の値が空でなければ、通常の直接生成経路より先に dump 処理へ分岐します。モデルを開き、compile-time の backend 選択（`--cpu` 指定時は CPU）で初期化し、slot 0 を確保してから token 列を組み立てます（`engine/src/inkling2/ink_main.cpp:326-345,546-549`、`engine/src/inkling2/ink_backend.h:150-165`）。モデルファイルを開けない場合は `open: ...`、backend 初期化または slot 確保に失敗した場合は `init: ...` を stderr に出して終了コード 1 です。forward に失敗した場合は `forward: ...` を stderr に出して終了コード 1 です（`engine/src/inkling2/ink_main.cpp:326-347`）。

成功すると、各 ID を slot 0 の位置 0 から順に投入して logits を取得し、出力ファイルを binary write モードで開きます。既存ファイルがあれば切り詰めます。ファイル形式は4-byte単位で、token 数、語彙数、token ID 配列、FP32 logits 配列の順に書かれます（`engine/src/inkling2/ink_main.cpp:340-355`）。書込み後は `[dump-ref] wrote ...` を stdout に出します（同 `:356`）。

## 適用条件と副作用

- `--dump-ref` を指定した経路は、一般の直接生成と異なり、モデルパス未指定時の共通チェックより前に実行されます。その場合は空のモデルパスでモデルを開こうとして失敗し、終了コード 1 になります。`--native` / `--model` で有効なモデルを指定してください（`engine/src/inkling2/ink_main.cpp:544-554`）。
- `--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval` が同時に指定されると、処理選択の順序上それらが `--dump-ref` より先に実行されます（`engine/src/inkling2/ink_main.cpp:544-549`）。
- 出力先を開けない場合は `dump-ref: cannot write <path>` を stderr に出して終了コード 1 です（`engine/src/inkling2/ink_main.cpp:349-350`）。`fwrite` と `fclose` の戻り値は検査されないため、書込み途中の I/O エラーを検出・報告する経路はこの関数内にありません（同 `:351-356`）。

## 出力とエラー

成功時は stdout に出力先、token 数、語彙数、backend 名を表示します。上記のモデル読込・初期化・forward・出力先オープンの失敗は stderr と終了コード 1、token ID 列の解析失敗は stderr と終了コード 2 です（`engine/src/inkling2/ink_main.cpp:328-356`）。

内蔵 `--help` の表示一覧には `--dump-ref` がありませんが、引数 parser と実行分岐には定義されています（`engine/src/inkling2/ink_main.cpp:402-403,488-497,548-549`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:381-384,402-403` — 値を取る parser と値欠落時のエラー。
- `engine/src/inkling2/ink_main.cpp:323-357` — モデル/backend の準備、入力列、forward、binary 出力と結果表示。
- `engine/src/inkling2/ink_main.cpp:482-483,544-554` — `--prompt-ids` との連携、dump 分岐順、モデルパス未指定時の経路。
- `engine/src/inkling2/ink_serve.h:256-270` — token ID 列の解析規則。
- `engine/src/inkling2/ink_backend.h:150-165` — ビルド条件と `--cpu` による backend 選択の入口。
