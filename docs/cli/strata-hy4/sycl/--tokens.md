# `strata-hy4-sycl --tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL のトップレベル実行） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | トークン ID を記したテキストファイルへのパス |

## 役割

通常の推論実行で、入力プロンプトを表す整数 token ID 列のファイルを指定します。読み込んだ ID 列はモデルの prefill に使われ、`--gen` が正なら末尾から greedy decode を続けます。`--serve` のサーバー実行ではこのファイル入力経路を通りません。

## 使い方

```sh
# prompt-ids.txt の整数 ID 列を入力し、続けて 32 token 生成する
strata-hy4-sycl --model SQ32.strata --tokens prompt-ids.txt --gen 32
```

## 値と既定値

- 値は次の引数文字列をそのままファイルパスとして受け取ります。相対パスの基準はプロセスの作業ディレクトリです。値が末尾にない場合は標準出力へ `ERR --tokens needs a value` を出し、終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,154`）。
- 既定値は空文字列です。同じオプションを複数回指定した場合は、parser が順に代入するため最後のパスが残ります（`engine/src/hy4flash/sycl/sy_main.cpp:93,107-115,154`）。
- ファイルは空白区切りの整数として `long` に読み込み、各値を `int32_t` に変換します。明示的なファイル open 検査や token ID の範囲検査は見当たりません（`engine/src/hy4flash/sycl/sy_main.cpp:266-275`）。
- ファイルを開けない場合、空ファイル、または数値を一つも読み取れない場合は ID が空のままとなり、標準エラーへ `no tokens` を出して終了コード 2 になります。数値の後に不正な文字列が現れた場合、ストリーム読み取りはそこで止まります。既に一つ以上読み取れていれば、この経路では末尾の不正部分をエラーとして拒否しません（同上）。
- 負数や語彙サイズを超える ID の拒否・補正は parser にありません。埋め込みカーネルは ID を埋め込み行のオフセットとして直接使うため、有効な token ID のみを含む入力が必要です。範囲外 ID を実行した場合の具体的な障害結果はソースからは確定できません（`engine/src/hy4flash/sycl/sy_kernels.h:9-20`）。

## 実行時の動作

通常モードではモデルのロード後にファイルを読み、トークン数 `T0` を決めます。`--ctx` が正でなければコンテキスト長は `max(T0 + gen + 16, 131072)` となり、入力は chunk ごとに `forward_chunk` へ渡されて prefill されます（`engine/src/hy4flash/sycl/sy_main.cpp:255-277,341-349`）。

`--gen` の既定値は 0 です。正の値なら prefill 後に greedy decode を最大その回数行います。生成結果は `generated ids:` として標準出力に表示され、`<--out の値>/gen_ids.txt` にも書かれます。`--out` の既定値は `.` です。load-only ではない通常推論が最後まで進むと、`<--out の値>/top5.txt` も書き込まれます（`engine/src/hy4flash/sycl/sy_main.cpp:104,527-549,577-605`）。

`--load-only` が指定されると token ファイルを読まず、初期化後に終了します。この場合 `--tokens` は実質的に使われません（`engine/src/hy4flash/sycl/sy_main.cpp:165,266-275,318-319`）。`--serve` では server options を組み立てて `hy4s_serve_main` に移るため、`--tokens` のパスは参照されません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。

## 適用条件と副作用

- 対象は `strata-hy4-sycl` の非 server 推論経路です。索引では `strata-hy4-sycl`（SYCL; `engine/src/hy4flash/sycl/sy_main.cpp`）のトップレベル option として掲載されています（`docs/cli/README.md:1452-1504`）。
- 通常実行では `--model` でモデルを指定する必要があります。モデル指定がない場合は usage を標準エラーへ出して終了コード 2 となります（`engine/src/hy4flash/sycl/sy_main.cpp:250-254`）。
- `--tokens` 自体は入力ファイルの内容を変更しません。推論出力先の書き込みは `--out` の設定に従い、生成時には `gen_ids.txt`、全通常実行では `top5.txt` が書き込まれます（`engine/src/hy4flash/sycl/sy_main.cpp:596-605`）。
- `--serve` と `--load-only` は別経路・条件で、指定パスの読み込みを行いません。`--serve` は `hy4s_serve_main` に委譲されます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。

## 出力とエラー

- `--tokens` の値が省略された場合: 標準出力 `ERR --tokens needs a value`、終了コード 2（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 読み取った ID が空の場合: 標準エラー `no tokens`、終了コード 2（`engine/src/hy4flash/sycl/sy_main.cpp:266-274`）。
- prefill の `forward_chunk` が失敗した場合: 標準エラー `forward: <理由>`、終了コード 1（`engine/src/hy4flash/sycl/sy_main.cpp:344-350`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-115,154`: 空の初期値、引数取り出し、および `--tokens` parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:250-277`: 通常モードのモデル必須判定、token ファイル読み込み、空入力の失敗、コンテキスト既定値。
- `engine/src/hy4flash/sycl/sy_main.cpp:318-349`: load-only の終了と token 列の prefill 処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:527-605`: 生成時の decode と出力ファイル書き込み。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248`: server 経路への分岐と `--tokens` の非使用。
- `engine/src/hy4flash/sycl/sy_graph.h:1382-1395`、`engine/src/hy4flash/sycl/sy_kernels.h:9-20`: token ID 列を GPU へ転送し、埋め込み行を ID で参照する処理。
- `docs/cli/README.md:1452-1504`: 対象コマンドの実装ファイルと option スコープ。

調査時点のソースからは token ID の語彙範囲検証、ファイル読み取りの詳細な診断、範囲外 ID を与えた場合の具体的な実行結果を確認できません。安全な既存同一 revision の CLI help は確認していません。
