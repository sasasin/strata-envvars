# `strata-hy4-sycl --dump`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（単体推論モード） |
| オプション | `--dump` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

単体推論の forward 処理で各層の診断用テンソルをホストへコピーし、NumPy `.npy` 形式の float32 ファイルとして `--out` で指定したディレクトリに保存します。通常のトークン出力に加え、最終チャンクの logits も保存します。`--dbg-layers` を併用すると、MoE 層内部の追加診断配列も出力します（parser と Runner への設定は `engine/src/hy4flash/sycl/sy_main.cpp:155-169,284-288`、dump 処理は `engine/src/hy4flash/sycl/sy_graph.h:797-807,1215-1227,1412-1419`）。

## 使い方

```sh
# ./dump は事前に作成しておく。入力ファイルは実際のモデルと token ID ファイルに置き換える。
strata-hy4-sycl --model model.strata --tokens prompt.ids --dump --out ./dump
```

`--dump` 自体は出力先を指定しません。`--out` の既定値はカレントディレクトリ `.` です。出力先の親ディレクトリを作成する処理はこの保存経路にありません（`engine/src/hy4flash/sycl/sy_main.cpp:93,155,287`、`engine/src/hy4flash/sycl/sy_graph.h:52-72`）。

## 値と既定値

オプションは値を取らず、parser は指定されると `dump = true` にします。既定値は `false` です。重複指定も同じ真偽値を設定するだけで、専用の validation や重複エラーはありません。値を後ろに置く構文ではなく、余分な引数は通常の未知引数経路でエラーになります（`engine/src/hy4flash/sycl/sy_main.cpp:99,105-116,166,190-197`）。

## 実行時の動作

parser の真偽値は `Runner::dump` に渡され、`Runner::dump_dir` には `--out` の値が渡されます（`engine/src/hy4flash/sycl/sy_main.cpp:155,284-288`）。forward の各チャンクで、Engram が有効な層の出力 `x_L{層番号}_engram.npy`、各層の attention 後 `x_L{層番号}_attn.npy`、MLP 後 `x_L{層番号}_mlp.npy` を保存します。通常の形状は `[T, 4, HID]` です。保存処理は device から host へコピーして待機した後に実行されます（`engine/src/hy4flash/sycl/sy_graph.h:797-807,1382-1423`）。

最後の prefill チャンクの logits は `logits.npy` に保存され、形状は `[n, vocab]` です。`n` は通常1で、`--all-logits` を併用した場合は Runner が保持する最終チャンクの行数になります。プロンプト全体が複数チャンクに分かれても、ここで保存する logits は最終チャンク分です（`engine/src/hy4flash/sycl/sy_main.cpp:343-363`）。同じファイル名で各チャンクの dump を行う層出力は後続チャンクで上書きされ、最後に保存されたチャンクの内容が残ります。

`--dbg-layers` も指定したときは、各 MoE 層について `L{層番号}_z_folded.npy`、`topk_idx.npy`、`topk_w.npy`、`z_out.npy`、`shared_out.npy` が追加されます。これらは層ごとに別名です（`engine/src/hy4flash/sycl/sy_main.cpp:167`、`engine/src/hy4flash/sycl/sy_graph.h:1215-1227`）。

## 適用条件と副作用

- `--serve` 経路では parser の後、`--dump` を `ServeOpts` に渡さず `hy4s_serve_main` へ戻ります。そのため、このオプションの単体推論向け dump 処理は server 経路には適用されません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。
- dump 中は SYCL command graph の forward/head 経路を使わず、decode 用 fused kernel も `!dump` 条件で選ばれません（`engine/src/hy4flash/sycl/sy_graph.h:961,1053,1077,1092,1107,1386-1391,1435-1439`）。また各テンソルの device-to-host コピーと待機が入ります（同 `:797-807`）。そのため計算経路と同期・転送量が変わりますが、性能への定量的影響はこのソース調査では確認していません。
- `.npy` は `fopen(path, "wb")` で開かれるため、同名ファイルがあれば上書きされます。出力ディレクトリが存在しない、またはファイルを開けない場合、保存関数は何も出力せず戻ります。書き込み結果も検査していません（`engine/src/hy4flash/sycl/sy_graph.h:52-72`）。

## 出力とエラー

引数値の validation はありません。値を要求する別オプションの値欠落時には stdout に `ERR <option> needs a value` を出して終了コード2、未知引数では stderr に `unknown arg <arg>` を出して終了コード2になります（`engine/src/hy4flash/sycl/sy_main.cpp:109-116,190-197`）。dump 保存の `fopen` 失敗は無言で無視され、保存失敗を示す専用終了コードや診断出力はありません（`engine/src/hy4flash/sycl/sy_graph.h:52-72`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-104,155-169` — 出力先と `dump` の既定値、および `--out` / `--dump` の parser 定義。
- `engine/src/hy4flash/sycl/sy_main.cpp:190-197,215-248` — 未知引数の失敗経路、および server 分岐で dump 値が転送されないこと。
- `engine/src/hy4flash/sycl/sy_main.cpp:284-288,343-363` — Runner への値の設定と最終チャンク logits の保存。
- `engine/src/hy4flash/sycl/sy_graph.h:52-72,797-807,1215-1227,1382-1423` — `.npy` の書き込み形式・失敗時の扱い、テンソル名・形状・保存箇所。
- `engine/src/hy4flash/sycl/sy_graph.h:961,1053,1077,1092,1107,1386-1391,1435-1439` — dump 時に graph/fused 経路を避ける条件。
