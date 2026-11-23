# `--tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | 空白区切りの整数 token ID を記したテキストファイルのパス |

## 役割

オフライン推論でモデルに与える prompt の token ID 列をファイルから読み込みます。読み込んだ列は prefill の入力になり、`--gen` が正数ならその続きの生成に使われます。`--serve` 経路ではこのファイル読込処理を通りません。

## 使い方

```sh
# ids.txt の整数列を prompt として読み、続けて 32 token 生成する
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32
```

この例は CUDA/HIP 版のオフライン実行です。モデル名はコマンドの使用例に合わせたプレースホルダーです。

## 値と既定値

- 値は次の argv 要素をそのままパスとして受け取ります。別名や明示的な型変換はありません。parser は `tok_path = nxt()` と代入します（`engine/src/hy4flash/run/hy4_main.hip.cpp:483-486`）。
- 省略時はパスが空のままなのでファイルを読みません（同 `:347`、`:632-639`）。空文字列も空パスとして読込をスキップし、後続で token がなければエラーになります。
- ファイル内容は `long` として空白区切りで読み、各値を `int32_t` にキャストして追加します。明示的な値域検査はこの読込箇所にありません。数値として読めない箇所に達すると抽出ループが終わり、そこまでの値だけが残ります（同 `:634-638`）。
- 同じオプションを複数回指定すると parser ループで都度代入されるため、最後の値が使われます（同 `:383-485`）。

## 実行時の動作

parser がパスを保持し、`--serve` 分岐を抜けたオフライン経路でファイルを開きます。読み込んだ token 数が 0 以下の context 指定（`--ctx` 省略時も該当）では、token 数 + `--gen` + 16 を context 上限の初期値にします。画像入力で token 列中の image pad を展開する場合は、展開後の長さでも自動 context を再計算します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-612, 632-639, 666-685`）。

続いて `T0` を token 数として prefill を行い、token 列が空なら `stderr` に `no tokens` を出して終了コード 2 で終了します。prefill 中の forward が失敗した場合は `forward: ...` を `stderr` に出し、終了コード 1 になります（同 `:686-689, 748-762`）。ファイルを開けない場合に専用の open error は出さず、読込結果が空なら上記 `no tokens` 経路になります。

## 適用条件と副作用

- 対象は索引上の `strata-hy4` CUDA/HIP root parser です。Metal/SYCL 版にも同名フラグがありますが、別 scope・別文書です（`docs/cli/README.md:1279-1284, 1348, 1358-1362`）。
- `--serve` を指定した場合は token ファイルを `ServeOpts` に渡さず、server 起動経路へ進みます。その経路では `--tokens` は offline prompt として使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-612`）。
- ファイルは入力として読みます。読込処理自体は書き込みません。推論後の結果ファイルの出力は `--out` 等の別処理が担います。
- 開く前に GPU 情報を問い合わせるため、この入力指定だけで GPU を使わずに token ファイルを検証する動作ではありません（同 `:613-639`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347, 483-485` — パス変数の初期値と parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-612` — server 分岐が token file 読込より先に実行され、serve options に token パスを渡さないこと。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-639, 686-691` — ファイル読込、整数抽出、context 初期値、空入力時のエラー。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:748-762` — prompt prefill と forward 失敗経路。
- `docs/cli/README.md:1277-1284, 1348` — `strata-hy4` root の索引項目と作成先リンク。
