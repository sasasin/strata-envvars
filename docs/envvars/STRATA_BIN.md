# `STRATA_BIN`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この名前を読むのは、Strata 本体ではなく SYCL の Arc A750 prompt deadlock 回帰確認用シェルスクリプト `sycl/tools/test_prompt_deadlock.sh` です。テスト対象の `strata` 実行ファイルのパスを指定します。一般の起動設定やエンジン内部の環境変数ではありません。

## 値と判定

| `STRATA_BIN` の状態 | スクリプトの扱い |
|---|---|
| 未設定または空文字 | `BIN` は空になり、使用条件を満たさない |
| 空でない文字列 | その文字列を実行ファイルのパスとして使用。`[ -x "$BIN" ]` が真である必要がある |

値の文字列比較や数値変換はありません。パスに空白があっても実行時の `"$BIN"` は一つの引数として渡されます。相対パスは呼び出し元の作業ディレクトリ基準です。スクリプトは `HERE` を計算しますが、それはテスト用 token ファイルの場所に使い、`STRATA_BIN` の基準ディレクトリには使いません。

`STRATA_BIN` が空、実行可能でない、または `MODEL_ARGS` が空なら、usage を標準出力に表示して終了コード `2` で終了します。

## 有効になる条件

この変数は `sycl/tools/test_prompt_deadlock.sh` を起動した場合だけ参照されます。Strata のエンジン実行ファイル自身がこの名前を読む箇所は、調査対象 HEAD のソース全体検索では確認できませんでした。

使用時には `MODEL_ARGS` にエンジン引数を指定する必要があります。スクリプトのコメントは、Arc A750 用の通常環境（render group、`ONEAPI_DEVICE_SELECTOR`、`IGC_EnableDPEmulation=1` など）も必要としています。これらはこのスクリプトによる `STRATA_BIN` の値判定条件ではなく、テスト実行環境についての記述です。

## 実行時の詳細

スクリプトは `STRATA_BIN` を `BIN` に代入し、`timeout "${DEADLOCK_TIMEOUT:-900}" "$BIN" ...` としてエンジンを起動します。エンジンへ `MODEL_ARGS` を渡し、固定の `sycl/tools/test_prompt_deadlock.sh` 隣接データ `data/prompt_deadlock_2744.tok` を `--tokens-file` に、`--max-new 4 --greedy` を追加します。標準出力と標準エラーは一時ファイルにまとめられます。

実行後、出力に `^prefill  *2743 tokens` がある場合は `PASS` を表示し、一時ファイルを削除して `0` で終了します。見つからない場合は `FAIL`、エンジンの終了コード、一時ファイルの場所を表示し、末尾5行を出して `1` で終了します。制限時間の既定値は別変数 `DEADLOCK_TIMEOUT` による900秒です。

## 根拠

- `sycl/tools/test_prompt_deadlock.sh:7-12` — 使用例、回帰テストの目的、環境についての説明。
- `sycl/tools/test_prompt_deadlock.sh:13-18` — `STRATA_BIN` の読み取り、空・実行権限・`MODEL_ARGS` の検証、エンジン起動と timeout。
- `sycl/tools/test_prompt_deadlock.sh:19-26` — 出力判定、一時ファイルの扱い、終了コード。
- `docs/INTEL.md:794-795` — このスクリプトを2,744-token prompt の回帰テストとして挙げている。
