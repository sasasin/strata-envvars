# `--dump-routing`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--dump-routing` |
| 別名 | なし |
| 値 | 出力先ファイルパス（`PATH`） |

## 役割

推論中に各層・各位置で選ばれた expert ID と router weight をバイナリトレースへ記録します。プロンプトや生成内容に応じたルーティングを後から集計し、expert cache 用 profile の作成や cache policy のオフライン評価に使えます。

## 使い方

```sh
strata --native MODEL.gguf --tokens-file prompt.tokens --max-new 1 --dump-routing routing-new.bin
```

`routing-new.bin` は新しい出力先の例です。既存ファイルを指定すると上書きされます。`tools/make_profile.py` はこの形式のトレースを入力として受け取ります。

## 値と既定値

- `PATH` は必須の次引数です。オプションの後に引数がなければ parser の `next()` が `--dump-routing needs a value` を stderr に出し、終了コード 2 で終了します。
- PATH の形式や存在確認は parser では行わず、記録開始時に `fopen(PATH, "wb")` します。空文字列は option 値として消費されますが、後段の空文字判定によりファイルを開かず記録も無効になります。
- 同じオプションを複数回指定した場合の重複拒否はありません。parser は都度値を代入するため、最後に指定した値が使われます。
- 既定値は空文字列で、未指定時はトレースを書きません。

## 実行時の動作

指定された非空 PATH をバイナリ書き込みモードで開きます。通常の pool dispatch では、各記録は `int32 layer`、`int32 k`、`k` 個の `int32 expert ID`、`k` 個の `float weight` の順です。1位置・1層ごとのルーティング記録を追記していき、重み付きの順位付けに使える値を保存します。記録はホストの `int32` / `float` 表現で書かれます。

複数 token をまとめる verify dispatch では、token ごとに同じ形式の記録を出しますが、dispatch 側で router weight が公開されないため weight 部分はゼロ埋めです。`tools/make_profile.py` は ID の出現頻度で集計し、weight 部分を読み飛ばすため、頻度ベースの profile 作成には使えますが、この経路の weight 値を重み付き統計として解釈できません。

`--dump-routing` は expert pool が動作することを前提にします。`--no-pool` と併用すると、空ファイルを誤って出さないよう明示的に拒否します。記録は pool dispatch 内で実行され、pool を必要とする他のエンジン動作はそのままです。

## 適用条件と副作用

- 通常の `src/program/generate.cpp` parser のオプションです。Qwen3.6-35B-A3B のモデルは、同ファイル内の parser より前に family 専用 `strata::qwen35::run()` へ委譲されます。この専用 parser での `--dump-routing` の受理は本調査では確認していません。
- `--no-pool` との併用は失敗します。別の backend、build 構成、Release 配布バイナリでの挙動はこの checkout からは確認していません。
- `"wb"` で開くため、同名の既存ファイルは切り詰められます。パスが書き込み不可などで開けない場合は stderr に `strata generate: cannot write PATH` を出し、終了コード 1 です。
- ファイルへの `fwrite()` の戻り値と終了時の `fclose()` の戻り値を検査していません。書き込み途中の I/O エラーや終了時 flush エラーを検出・報告できない経路があります。
- routing 層番号が `0..47` の範囲外の場合、stderr にエラーを出してその記録 callback を戻ります。ここでは engine 全体の終了にはしていません。

## 出力とエラー

- 正常終了時は stdout に `routing dumped PATH (N records of layer, k, ids, weights)` を表示します。カウンター `N` は pool callback 呼び出し数です。multi-token dispatch は1 callbackで複数 token 分を書けるため、常にファイル内レコード数とは一致しません。
- 値の欠落は stderr と終了コード 2、`--no-pool` との併用は stderr と終了コード 2、ファイルを開けない場合は stderr と終了コード 1 です。
- 書き込み失敗・close 失敗専用のエラー出力はありません。

## 根拠

- `src/program/generate.cpp:502-508` — `dump_routing` の既定値とオプションの用途コメント。
- `src/program/generate.cpp:886` — built-in help の説明。
- `src/program/generate.cpp:2393-2407` — Qwen3.6-35B-A3B を別 parser に委譲する早期分岐。
- `src/program/generate.cpp:2416-2421` — parser の値取得と値欠落時の終了処理。
- `src/program/generate.cpp:2472` — `--dump-routing PATH` の parser 定義。
- `src/program/generate.cpp:1129-1154` — pool dispatch 後の layer、k、expert ID、weight の書き込みと層番号検査。
- `src/program/generate.cpp:1158-1178` — multi-token verify dispatch の token ごとの記録とゼロ埋め weight。
- `src/program/generate.cpp:6914-6926` — `--no-pool` 検査、`fopen(..., "wb")`、ファイルを開けない場合のエラー。
- `src/program/generate.cpp:6928-6936` — pool callback の選択。
- `src/program/generate.cpp:16859-16864` — 終了時の close と stdout 表示。
- `tools/make_profile.py:47-58` — トレースの record 形式を読む処理。expert ID を集計し、weight 部分を読み飛ばす。
