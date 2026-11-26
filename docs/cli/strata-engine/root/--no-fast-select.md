# `strata generate --no-fast-select`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-fast-select` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

QSA 層の indexer で使う高速な block score / top-k 選択を無効にし、従来の index score と `topk_512_step` を使う切り替えです。選択方式の A/B 比較などに使えます。通常は高速選択が有効で、このフラグは `strata generate` が実行する QSA 層の選択に作用します（`engine/src/program/generate.cpp:959,4267,6111`、`engine/src/core/layer.cpp:1277-1283`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --no-fast-select
```

この例では必須のトークン列を指定して推論を実行し、QSA 選択に旧経路を使います。`--pack` を省略した場合の pack ディレクトリ既定値は `pack/full` です（`engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

値を取りません。parser は引数が `--no-fast-select` と一致すると `no_fast_select` を `true` にします。未指定時は `false` で、層側の初期値 `g_fast_select = true` により高速選択が有効です。複数回指定しても同じ真偽値を設定するだけです。個別の範囲検証や値検証はありません（`engine/src/program/generate.cpp:959,4267`、`engine/src/core/layer.cpp:47`）。

## 実行時の動作

引数解析後、エンジンは `layer_set_fast_select(!o.no_fast_select)` を呼び、プロセス内の選択スイッチを設定します。QSA 層の処理では、既定の有効状態なら `qsa_block_scores` と `qsa_block_topk` を呼びます。このフラグを指定すると `qsa_index_step` と `topk_512_step` に分岐します。選ばれた block ID はどちらの経路でも後続の KV 解決へ渡されます（`engine/src/program/generate.cpp:6108-6112`、`engine/src/core/layer.cpp:1277-1285`）。

serve の会話セッション設定 fingerprint にも `no_fast_select` が含まれます。そのため、この切り替えの有無はセッション設定の識別に反映されます（`engine/src/program/generate.cpp:14023-14029`）。

## 適用条件と副作用

選択分岐は `qsa_layer` 内の indexer score / top-k 部分にあります。したがって、QSA 層を含まない処理では、このフラグに対応する選択分岐は実行されません（`engine/src/core/layer.cpp:1153,1273-1285`）。高速 attention など他の最適化スイッチとは別に設定され、ここで確認した呼び出し箇所ではこのフラグからファイルや環境変数を変更しません（`engine/src/program/generate.cpp:6108-6115`）。

同じ `--no-fast-select` parser とスイッチ設定は SYCL 版にもあります。SYCL build は `engine/sycl/CMakeLists.txt:375-377` で同じ実行ファイル名 `strata` を作成し、その parser も同じ `layer_set_fast_select(!o.no_fast_select)` を設定します（`engine/sycl/src/program/generate.cpp:625,2213,3223-3227`、`engine/sycl/src/core/layer.cpp:47,1299-1307`）。

## 出力とエラー

このフラグ固有のメッセージや失敗経路は parser・切り替え箇所にありません。未知の引数は `unknown argument` と usage を標準エラーへ出して終了コード 2 になります。また `--tokens` なしで通常実行すると、必須引数のエラーと usage を標準エラーへ出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274,5002-5007`）。

## 根拠

- `engine/src/program/generate.cpp:959,4267` — 既定値 `false` の option state と値なし parser。
- `engine/src/program/generate.cpp:6108-6112` — fast-select switch の設定。
- `engine/src/core/layer.cpp:47,1153,1273-1285` — 既定で有効な switch、QSA 層の選択分岐、選択後の KV 解決。
- `engine/src/program/generate.cpp:14023-14029` — serve の設定 fingerprint への反映。
- `engine/sycl/CMakeLists.txt:375-377`、`engine/sycl/src/program/generate.cpp:625,2213,3223-3227`、`engine/sycl/src/core/layer.cpp:47,1299-1307` — SYCL 実行ファイルと同等の parser・動作。
- 索引との範囲差: `docs/cli/000_cli_tools.md:10` は `engine/src/program/generate.cpp` と Qwen3.6 側を parser 所在として挙げますが、現行 checkout には上記の SYCL parser もあります。索引の更新は今回の編集対象外です。
