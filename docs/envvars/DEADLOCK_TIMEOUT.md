# `DEADLOCK_TIMEOUT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この名前を参照するのは SYCL 向け回帰確認スクリプト `sycl/tools/test_prompt_deadlock.sh` だけである。スクリプトが起動する `timeout` コマンドの時間引数を選ぶために使い、Strata エンジン本体の処理や通常の CLI 実行を制御する環境変数ではない。スクリプトのコメントも、A750 の 2,744-token prompt が所定時間内に prefill 行を出すか確認する用途としている（`sycl/tools/test_prompt_deadlock.sh:2-12,18`）。

## 値と判定

スクリプトは Bash の `${DEADLOCK_TIMEOUT:-900}` を使う。未設定または空文字なら文字列 `900` を `timeout` の第 1 引数にし、空でない値は文字列のまま渡す（`sycl/tools/test_prompt_deadlock.sh:18`）。スクリプト内で数値変換、書式検証、範囲制限はしないため、例えば `1`、`30s`、`0`、`abc` はいずれもそのまま渡される。これらを `timeout` がどう解釈するかは Strata のコード外であり、本調査では規則を断定しない。

| スクリプト内の環境値 | `timeout` に渡す値 | Strata 側の処理 |
|---|---|---|
| 未設定 | `900` | デフォルト展開 |
| 空文字 | `900` | `:-` によりデフォルト展開 |
| 空でない任意の文字列（例: `1`, `30s`, `0`, `abc`） | 入力文字列そのまま | 検証・変換・clamp なし |

大小文字や空白を判定する処理もありません。空白を含む値も Bash の引用により一つの引数として渡されます（`sycl/tools/test_prompt_deadlock.sh:18`）。

## 有効になる条件

- `sycl/tools/test_prompt_deadlock.sh` を実行すること。Strata のエンジン本体、通常のサーバーモード、その他の起動経路がこの名前を読む箇所はありません（リポジトリ全体の完全一致検索で参照は同スクリプト内のコメントと実行行のみ）。
- スクリプトは `STRATA_BIN` が実行可能で、`MODEL_ARGS` が空でないことを要求する。満たさない場合は usage を表示して終了コード 2 とし、`timeout` は呼び出さない（`sycl/tools/test_prompt_deadlock.sh:15-18`）。
- 実行ファイルにはスクリプト固定の `--tokens-file`, `--max-new 4`, `--greedy` が付加される。この環境変数による CLI 上書きや別環境変数との優先順位は実装されていません（`sycl/tools/test_prompt_deadlock.sh:18`）。

## 実行時の詳細

環境値はスクリプトが実行行に到達した時に Bash のパラメータ展開で評価され、その値が `timeout` の時間引数になります。スクリプト側で値をキャッシュしたり、後から再読込したりする処理はありません（`sycl/tools/test_prompt_deadlock.sh:18`）。同じ行で `$BIN` を起動し、その stdout と stderr を一時ファイルへまとめてリダイレクトします。

続いて出力に `^prefill  *2743 tokens` があるかを判定し、あれば `PASS: ...` を表示して一時ファイルを削除し終了コード 0、なければ `FAIL: no prefill line (engine exit code $rc); output kept in $OUT` と末尾 5 行を表示して終了コード 1 にします。従ってスクリプトの成功判定は終了コード単独ではなく prefill 行の有無です（`sycl/tools/test_prompt_deadlock.sh:19-26`）。`timeout` コマンド自身の時間文字列の文法や期限到達時のプロセス処理はこのスクリプトでは定義されていません。

## ログと測定値

引数不足時は `usage: STRATA_BIN=<strata> MODEL_ARGS="..." $0` を標準出力に出します。成功時は `PASS: the 2,743-token prompt was read (...)`、失敗時は上記の `FAIL: ...` 行を出し、失敗時には保存先出力の末尾 5 行も標準出力へ出します（`sycl/tools/test_prompt_deadlock.sh:16,20-26`）。コメントはデフォルト 900 秒、A750 では起動後の prompt 処理に約 60 秒と記していますが、これはスクリプトの説明コメントにある値で、今回の実行で測定した値ではありません（`sycl/tools/test_prompt_deadlock.sh:10-12`）。

## 根拠

- `sycl/tools/test_prompt_deadlock.sh:2-12` — 回帰確認用途、対象症状、既定時間に関するスクリプト記述。
- `sycl/tools/test_prompt_deadlock.sh:15-18` — 必須入力確認と環境値のデフォルト展開、`timeout` への引き渡し。
- `sycl/tools/test_prompt_deadlock.sh:19-26` — prefill 出力による判定、表示、終了コード。
- `docs/INTEL.md:511-515` — この回帰確認スクリプトへの関連記載。
