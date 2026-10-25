# `--dump-final-r`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数） |
| オプション | `--dump-final-r` |
| 別名 | なし |
| 値 | 出力ファイルパス（文字列） |

## 役割

通常の token 処理経路で、各位置の最終層後の residual `R` をホストへコピーし、位置・入力 token とともにバイナリファイルへ追記します。ソースコメントでは MTP draft head の入力を調べる用途とされ、token path だけが対象です（`src/program/generate.cpp:647-649,15952-15956`）。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --dump-final-r /tmp/final-r.bin
```

`--pack` 等、モデルを読み込んで通常の CLI 生成経路を開始する引数と併用します。`--dump-final-r` 自体はファイル名以外の形式・拡張子を要求しません。

## 値と既定値

- 値は必須です。省略すると parser の `next()` が stderr に `<option> needs a value` を出し、終了コード 2 で終了します（`src/program/generate.cpp:2418-2420,2607`）。空文字列を値にした場合は空として保持され、出力は無効になります（`src/program/generate.cpp:15708`）。
- 未指定時の既定値は空文字列で、ファイルを開きません（`src/program/generate.cpp:649,15708`）。
- 同じオプションを複数回指定したときは parser が値を順に代入するため、最後の値が使われます（`src/program/generate.cpp:2416-2420,2607`）。値として次のオプション文字列を渡しても特別扱いされず、パスとして消費されます。

## 実行時の動作

通常の非 server 経路に入ると、指定パスを `fopen(..., "wb")` で開きます。したがって既存ファイルは切り詰められ、親ディレクトリ作成や追記モードはありません（`src/program/generate.cpp:15693-15709`）。server 経路の処理はこの地点より前に分岐・終了するため、`--serve` ではこのファイルを開きません（`src/program/generate.cpp:15690-15708`）。

token loop の各位置で層処理が成功した後、`ss.R` を `g.hc * g.n_embd` 個の `float` として device から host へコピーし、次の順で1レコードを書きます（`src/program/generate.cpp:15952-15956`）。

1. `int64_t` 2個: `{pos, tok}`（位置とその位置で処理した token ID）
2. `float` `g.hc * g.n_embd` 個: 最終層後の residual `R`

明示的なファイルヘッダーや次元メタデータは書かれません。数値は C++ のネイティブ表現で出力され、残差部分の長さはモデルの `hc` と `n_embd` に依存します。読み取り側はこの形状を別途把握する必要があります。prompt の事前処理に chunked prefill を使っても、ソースコメント上この dump は token path に限定され、prefill chunk 自体の中間状態を出力する処理は確認できません（`src/program/generate.cpp:647-649,15712,15952-15956`）。

## 適用条件と副作用

- ファイルを開く箇所は `--serve` 分岐後の通常処理にあります。server リクエストごとの dump 設定としては使われません（`src/program/generate.cpp:15690-15708`）。
- `fopen` に失敗すると `final_r` は null のままになり、以後の書き込み条件を通らないため、エラーメッセージを出さず dump が行われません（`src/program/generate.cpp:15708-15709,15952`）。
- `cudaMemcpy` と `fwrite` の戻り値はこの書き込み箇所で検査されていません（`src/program/generate.cpp:15952-15956`）。書き込み失敗時の明示的なエラー報告・終了コードはここからは確認できません。
- `--dump-final-r` は parser で受理されますが、組み込み usage 表示には記載がありません。同 usage は別名に見える `--dump-residual PATH` を掲載しています（`src/program/generate.cpp:881-884,2607`）。両者が同じオプションであることは parser から確認できず、`--dump-residual` とは別の名前として扱います。

## 出力とエラー

値を省略した場合は stderr にエラーを出して終了コード 2 です。未知の引数は `unknown argument: ...` と usage を stderr に出し終了コード 2 ですが、`--dump-final-r` は parser に登録されているため未知引数扱いにはなりません（`src/program/generate.cpp:2418-2420,2607,2787-2793`）。

出力先を開けない場合や書き込み失敗に対する専用エラー処理は、確認した使用箇所にはありません（`src/program/generate.cpp:15708-15709,15952-15956`）。

## 根拠

- parser 用 option 値の宣言と token path 限定の説明: `src/program/generate.cpp:647-649`
- 必須値の取得と parser 登録: `src/program/generate.cpp:2416-2420,2607`
- root usage における別の dump option 表示: `src/program/generate.cpp:881-884`
- server 経路の後にファイルを開く処理、binary write mode: `src/program/generate.cpp:15690-15712`
- residual の device-to-host copy とレコード書き込み: `src/program/generate.cpp:15952-15956`
- 索引上の配置・tool scope: `docs/cli/README.md:1128-1134,1162`
