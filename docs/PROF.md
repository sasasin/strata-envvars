# `PROF`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`PROF` は Strata の実行ファイルが直接読む環境変数ではなく、同梱ツール `tools/batch_test.py` が子エンジンに GPU verify stage のプロファイルを要求するためのスイッチです。スクリプトは `PROF` が truthy なら、起動するエンジンの環境に `STRATA_VERIFY_PROFILE=1` を追加します。常に設定する `STRATA_DECODE_TIMING=1` と組み合わせるため、サーバーの request ごとの decode timing と GPU stage timing をログに出せます。

## 値と判定

Python の `os.environ.get("PROF")` の真偽値で判定します。文字列全体の比較や数値変換はありません。

| `PROF` の状態 | `batch_test.py` が子エンジンに渡す値 |
|---|---|
| 未設定 | `STRATA_VERIFY_PROFILE` をこのスクリプトからは追加しない |
| 空文字 | 同上（空文字列は Python で false） |
| 空でない文字列 | `STRATA_VERIFY_PROFILE=1`（`0`、`false`、大小文字を問わず、空でなければ true） |

子プロセスの環境は親の環境をコピーしたうえで `extra_env` を適用します。このため、`PROF` が未設定または空でも、親環境に既に `STRATA_VERIFY_PROFILE` があればその値は継承されます。`PROF` が非空ならスクリプトが値を `1` に上書きします。コマンドライン引数による上書きはありません。

## 有効になる条件

このスイッチは `python3 tools/batch_test.py ...` の実行経路でのみ使われます。Strata エンジンを直接起動しても `PROF` 自体は効果がありません。`batch_test.py` は `PROF` の有無にかかわらず、`--serve` で起動するエンジンへ `STRATA_DECODE_TIMING=1` を渡します。

GPU stage profiling の実装は `STRATA_VERIFY_PROFILE` 側にあります。Verifier は環境変数の設定有無だけで有効化し、値が `0` や空文字でも、エンジンがそれを受け取れば有効です。ただし GPU profile 用 `cudaMalloc` に失敗すると profiling を無効化します。また、pipelined window は pinned host buffer の確保に失敗した場合、その window をプロファイルしません。したがって `PROF` を設定しただけで毎回 stage timing が出るとは限りません。

## 実行時の詳細

スクリプトは `main()` 内で環境を組み立て、`Engine` が `subprocess.Popen` に `env` を渡して子エンジンを起動します。`PROF` の読み取りは1回で、既に起動した子プロセスへ後から親環境を変更しても反映されません。スクリプト自身は `PROF` を子へ転送しません。

Verifier は初期化時に `STRATA_VERIFY_PROFILE` の設定有無を読み、GPU profile buffer を確保して stage ごとの GPU stamp を記録します。プロファイル結果は `profile_report()` が stage 名、平均 ms/window、window 数の形で組み立てます。`docs/DETAILS.md` によると、`STRATA_DECODE_TIMING=1` と `STRATA_VERIFY_PROFILE=1` を併用すると、request ごとに `strata decode timing:` と `strata decode GPU stages (ms/window):` の行がエンジンログに出ます。イベントで各 stage を計時するため decode が遅くなり、速度測定用途ではなく比較用途とされています。

## 根拠

- `tools/batch_test.py:47-62,105-108`: `PROF` の読み取り、親環境と追加環境の合成、`--serve` 子プロセスへの環境受け渡し。
- `src/core/verify.cpp:829-834,1017-1019`: `STRATA_VERIFY_PROFILE` の設定有無による有効化、GPU buffer 確保、stage stamp。
- `src/core/verify.cpp:2201-2224,3950-3954,4015-4024`: report の生成、pipelined window の host buffer 条件と profiling 処理。
- `src/program/generate.cpp:6749-6754`: native pack の場合に serve path の stage timing を使う案内。
- `docs/DETAILS.md:373-380`: 出力ログと計測による slowdown についての説明。
