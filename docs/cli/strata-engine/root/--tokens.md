# `--tokens`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | カンマまたは空白区切りの、事前トークン化済み token ID リスト。1 個以上の 0〜2,147,483,647 の整数 |

## 役割

tokenizer を内蔵しないエンジンへ、生成の条件となる prompt を token ID 列として渡す。通常の生成では必須で、モデルの prefill に入力され、生成完了時には prompt と生成結果の ID 列が stdout に出力される。テキスト文字列を受け取るオプションではない。

## 使い方

```sh
# ID 1、2、3 を prompt として pack/full から生成する
strata generate --pack pack/full --tokens "1,2,3" --max-new 16

# 長い prompt はファイルから渡す（--tokens との併用不可）
strata generate --pack pack/full --tokens-file prompt.ids --max-new 16
```

`--tokens-file` は `--tokens` と同じ共通入力枠の代替指定である。例の `--tokens-file` の仕様は [同オプションの文書](--tokens-file.md)を参照。

## 値と既定値

- 各 ID は10進整数で、範囲は `[0, 2147483647]`。要素はカンマ、空白、タブ、改行などで区切れる。区切りの連続は空要素として読み飛ばされる。
- リストが空、数値でない、整数範囲外、または負数の場合は受理されない。トークン列自体に既定値はなく、通常の生成では `--tokens` または `--tokens-file` のどちらかが必要。
- `--tokens` と `--tokens-file` はどちらか一方だけ指定できる。同じ指定を複数回行った場合もエラーとなる。オプションに値が続かない場合は `--tokens needs a value` を stderr に出し、終了コード 2 で終了する。
- prompt の長さは `--max-context` と `--max-new` の合計制約を受ける。既定値はそれぞれ 4096 と 16。`max-context` が prompt と生成分を収容できない場合はエラーとなる。

## 実行時の動作

parser は `--tokens` の値を `parse_i64_list` で読み、各要素を `int32_t` として検証したうえで `Options::tokens` に格納する。推論経路ではその配列を `prefill.run` に渡し、prompt の各位置をモデルの入力として処理する。単独の token ID 指定によるテキスト化や tokenizer 処理はこの parser にはない。

`--serve` を使う経路ではリクエストが token 列を持ち込むため、起動時にどちらの token 入力もない場合、実装は内部の初期値 `{248045}`、`--max-new 1`、EOS 停止を設定して起動要件を満たす。この分岐は通常の生成に対する `--tokens` の既定値ではない。

## 適用条件と副作用

- `--tokens` は `strata-engine` の共通エンジン parser に属する。索引上の `strata-engine/qwen36` にある同名オプションは Qwen3.6 専用 parser の別文書・別スコープである。
- 値の構文検査は token ID の非負整数範囲までである。parser ではモデル語彙にその ID が存在するか検査していない。モデル実行時に発生する個別 ID の扱いは、モデルと実行経路に依存し、この調査では一律の検証結果を確認できなかった。
- ファイルを指定する場合は `--tokens-file` が読み込みを行う。`--tokens` 自体はファイルを作成・変更しない。

## 出力とエラー

- 不正な ID は `invalid token id: expected an integer in [0, 2147483647]`、空の列は `token list was empty` を stderr に出し、終了コード 2 で終了する。
- 両入力オプションの重複は `supply one token input only` を stderr に出し、終了コード 2 で終了する。
- token 入力がない通常起動では、必須指定を示すエラーと usage を stderr に出し、終了コード 2 で終了する。
- prompt と生成数が context に収まらない場合は `--max-context` と prompt / generation の長さを示すエラーを stderr に出し、終了コード 2 で終了する。
- 生成後、stdout に `prompt  :` と `output  :` の ID 列を出す。

## 根拠

- `engine/src/program/generate.cpp:1208-1214` — usage が `--tokens LIST` を必須のカンマ区切り token ID 入力として示し、ファイル入力を代替として記載。
- `engine/src/program/generate.cpp:756-760` — prompt 配列に空の初期値があり、`--max-new` と `--max-context` の既定値を定義。
- `engine/src/program/generate.cpp:1554-1581` — 区切り文字、整数変換、ID 範囲、空リストの検証。
- `engine/src/program/generate.cpp:3838-3868` — parser が `--tokens` を格納し、`--tokens-file` と重複指定を拒否する処理。
- `engine/src/program/generate.cpp:4996-5007` — serve 時の内部 token 初期化、および通常起動で入力がない場合のエラーと終了コード。
- `engine/src/program/generate.cpp:5222-5225`、`6152-6155` — prompt 長と生成数に対する context 制約。
- `engine/src/program/generate.cpp:10714-10715`、`24163-24166` — prompt の先頭 token の使用と prefill への prompt 配列の受け渡し。
- `engine/src/program/generate.cpp:25403-25415` — 生成完了時の prompt / output ID 列の stdout 出力。
- `docs/cli/README.md:1036-1047`、`1218-1227`、`1240-1275` — `strata-engine` 共通 root scope、`--tokens` と `--tokens-file` の索引位置、および Qwen3.6 専用 parser の別 scope。
