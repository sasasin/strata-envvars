# `--dump-logits`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（root） |
| オプション | `--dump-logits` |
| 別名 | なし |
| 値 | 出力先ファイルのパス（`PATH`） |

## 役割

通常の token loop が計算した各位置の raw logits を、後から比較・解析できるバイナリファイルに保存します。既定では出力しません。CUDA/HIP 系 `engine/src/program/generate.cpp` の parser と実行箇所を確認しました。この parser はパスの形式や拡張子を検証せず、指定先を `wb`（書き込み・既存内容を切り詰めるモード）で開きます。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" \
  --ple-gguf ./path/to/ple.gguf --dump-logits ./logits.bin
```

`--tokens` は pack に対応した token ID 列、`--ple-gguf` は必要な PLE テーブルを指定する例です。入力やモデルに必要な他の設定は利用環境に合わせてください。

## 値と既定値

- `PATH` は次の argv 要素からそのまま取得されます。省略すると `--dump-logits needs a value` を stderr に出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3842-3847,3886`）。
- 既定値は空文字列で、空のままなら dump を開きません（同 `engine/src/program/generate.cpp:766,10652-10658`）。
- 値の形式、拡張子、重複指定を個別に検証する処理はありません。複数回指定すると parser は同じフィールドを上書きし、最後に読んだ値が使われます（同 `engine/src/program/generate.cpp:3842-3847,3886`）。

## 実行時の動作

- dump を有効にすると、生成開始前に `PATH` を `fopen(..., "wb")` で開きます。既存ファイルは切り詰められます。開けない場合は `strata generate: cannot write PATH` を stderr に出し、終了コード `1` です（`engine/src/program/generate.cpp:10652-10667`）。
- ファイルはテキスト行ではなく、ソース上はバイナリです。最初にヘッダーとして `int32` 2個（語彙数、書き込み行数）を1組書き、その後に各行の語彙数分の `float` を保存します。各値は `d_logits` から host の `float` 配列へ読み戻されて出力されます（同 `engine/src/program/generate.cpp:10652-10677,24358-24365,24375-24385`）。ソースはファイルのバイト順を別途規定していません。
- `--logits-stride` が既定値 `1` のとき、対象位置を連続して保存します。総対象位置数は prompt token 数 `- 1 + --max-new` として算出されます（同 `engine/src/program/generate.cpp:759,767,10657-10677`）。`--logits-stride N` を併用すると、0 始まりの位置で `N` の倍数にあたる行と最終位置が保存されます（`engine/include/strata/program/logits_selection.hpp:20-28`）。stride を `1` より大きくする場合は `--max-new 1` と `--dump-logits` の両方が必須です。条件を満たさなければ stderr にエラーを出して終了コード `2` です（`engine/src/program/generate.cpp:5201-5203`）。
- native pack では prompt 処理後に通常の per-token loop を抜けて speculative loop に移るため、この dump の読み戻し・書き込み箇所を通りません。ヘッダーも最初のデータ行と同時に書く設計なので、native pack でこのパスを指定すると、ソースの経路上はファイルが切り詰められた後に空のままになります（同 `engine/src/program/generate.cpp:10653-10655,24237-24240,24358-24385`）。

## 適用条件と副作用

- `--logits-stride > 1` を使う場合、`--max-new` は `1` でなければなりません。stride は保存する行を選ぶだけで、prompt token をモデルへ与える処理を省く設定ではありません（`engine/src/program/generate.cpp:5201-5203`、`engine/include/strata/program/logits_selection.hpp:9-23`）。
- 書き込み開始時に指定ファイルを切り詰めます。保存内容を残す必要がある場合は既存ファイルを指定しないでください（`engine/src/program/generate.cpp:10663-10667`）。
- 語彙数または計算された位置数が `int32` の上限を超える場合は、ファイルを開く前にエラー終了します（同 `engine/src/program/generate.cpp:10657-10662`）。
- logits の device-to-host 読み戻しに失敗した場合、または値に非有限値がある場合は stderr にエラーを出して終了します（同 `engine/src/program/generate.cpp:24361-24372`）。ヘッダー・行の書き込み失敗もエラーとなり、正常終了時の close に失敗した場合は `cannot finish logits dump` で終了します（同 `engine/src/program/generate.cpp:24375-24385,25379-25382`）。

## 出力とエラー

正常に dump を閉じると、stdout に `logits dumped` と出力先パスを表示します（`engine/src/program/generate.cpp:25379-25382,25553`）。dump に関する主な失敗は、出力先を開けない・次元が `int32` を超える場合（それぞれ終了コード `1` / `2`）、読み戻しまたは書き込みに失敗した場合（`1`）、stride の条件違反（`2`）です。エラーメッセージは stderr に出力されます（同 `engine/src/program/generate.cpp:5201-5203,10659-10666,24361-24385,25379-25382`）。

## 根拠

- `docs/cli/000_cli_tools.md:10` — `strata-engine` の parser 所在と root scope。
- `engine/src/program/generate.cpp:766-767,1283-1284` — dump path と stride の既定値、help 表示。
- `engine/src/program/generate.cpp:3842-3847,3886-3892` — parser、値の取得、隣接する stride の検証。
- `engine/src/program/generate.cpp:5201-5203` — stride との相互作用と失敗経路。
- `engine/src/program/generate.cpp:10652-10677,24358-24385,25379-25382` — ファイル形式、通常 loop での読戻しと書込み、close。
- `engine/include/strata/program/logits_selection.hpp:9-28` — stride 値の構文、行選択、行数。
- `engine/src/program/generate.cpp:24237-24240,25173-25175` — native pack が per-token dump 読み取り箇所を通らない条件。
