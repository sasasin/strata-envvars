# `STRATA_PIPELINE_FORCE_MISS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

パイプライン decode の診断用フックです。正の整数 `k` を指定すると、作られた投機窓の先頭予測 token を `k` 回に 1 回だけ意図的に別の token ID に変え、不一致時の rollback 経路を検証できるようにします。通常利用向けの生成設定ではなく、`--pipeline-windows 2` の decode loop が動く場合の検証用です。

同じ処理が CUDA 側の `src/program/generate.cpp` と SYCL 側の `sycl/src/program/generate.cpp` にあります。

## 値と判定

環境変数を直接読む処理は `pipe_dbg_env("STRATA_PIPELINE_FORCE_MISS")` 経由です。値は `std::atoi` で整数に変換し、`std::max(0, ...)` で負値を 0 にします。

| 状態・値 | 結果 |
| --- | --- |
| `STRATA_PIPELINE_DEBUG` が無効 | helper が対象変数を読まず、既定値 0 になる |
| 対象変数が未設定、または空文字 | `atoi` の結果は 0。強制 miss なし |
| `0`、負数、数字で始まらない文字列 | 変換結果が 0 以下となり、強制 miss なし |
| 正の整数 `k` | 投機窓を作るたびに数え、`k` 回目ごとの窓で強制 miss |
| 数字の後ろに文字がある値（例: `2abc`） | `atoi` が読む数値接頭部を使うため 2 |

`atoi` は文字列全体の妥当性を検査しません。先頭空白や符号は `atoi` の規則で解釈されます。正値に上限 clamp はありません。変換が `int` の範囲を超える場合の値は、この実装では定義していません。

値を読む前に `pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` を確認します。これは関数内 `static const bool` で最初の helper 呼び出し時に一度だけ評価され、値が未設定、空文字、または先頭文字が `0` なら無効、それ以外なら有効です。そのため、プロセス実行中に `STRATA_PIPELINE_DEBUG` を変更しても gate は変わりません。一方、force-miss 値自体は request 処理の設定箇所で読み直されます（ただし下記 switch ファイルが値を上書きできます）。

根拠: `src/program/generate.cpp:461-467,14785-14788`; `sycl/src/program/generate.cpp:298-303,10436-10439`。

## 有効になる条件

環境値が正でも、それだけでは強制 miss は発生しません。

- `STRATA_PIPELINE_DEBUG` が上記の判定で有効であること。
- Strata の serve 経路で pipeline が有効であること。`--pipeline-windows` は `--serve` の layer split 用で、通常 `--pipeline-windows 2` が decode pipeline を選びます。自動設定もありますが、コード上の自動 ON は HIP の条件付き経路です。
- pipeline の準備条件を満たすこと。実装は MTP drafter と `--spec` 2 以上を要求し、batch slots、peer device、helper cache などとの併用を拒否して pipeline を OFF にします。
- 対象 request が pipeline decode 対象であること。pipeline 2 と GDN snapshot が有効で、repetition penalty (`hist_n > 0`) や coupled draft sampling のため serial decode に切り替わっておらず、キャンセル中でも生成上限到達後でもない場合に decode loop に入ります。

`--pipeline-windows 1` は prompt の short read のみを重ねるモードで、force-miss の変更箇所（decode の `make_b`）は使われません。`--pipeline-windows 0` や pipeline 非対応条件では、環境変数が正でも効果はありません。

根拠: `src/program/generate.cpp:891-896,4970-5020,10000-10005,14777-14788,16079-16099`; `sycl/src/program/generate.cpp:10428-10439,11029-11048`。

## 実行時の詳細

pipeline request の設定時に値を読み、decode loop 内の `force_miss` に渡します。`pl_fm` はその decode loop ごとに 0 から始まります。`make_b()` が次の投機窓 `B` を作るたびに、正の `k` なら `pl_fm` を増やし、`pl_fm % k == 0` のとき `B.tok[0]` を 0 と 1 の間で反転します。したがって毎 `k` 個目の `make_b()` で予測 token を元の値と異なる値にします（`k=1` なら毎回）。この処理は実際の token ID 0/1 を固定出力するものではなく、元の予測値が 0 なら 1、それ以外なら 0 に変えます。変更後の token が検証結果と一致する可能性まではコードで排除していないため、実際に rollback になるかは verdict との比較で決まります。

後続の verdict で `B.tok[0]` と検証結果の token が一致しなければ on-path と判定されず、既に走らせた窓は doomed 扱いになります。CUDA 経路では snapshot と verifier commit を戻して再実行し、SYCL 経路でも snapshot と commit を戻します。強制変更自体に専用の警告やログはありません。`STRATA_PIPELINE_DEBUG` が有効で `STRATA_PIPELINE_SWITCH` のファイルを開けた場合は、ファイル内の最初の `force_miss=` 指定が環境変数の値を上書きし、stderr に実効値を含む `strata pipeline switch: ...` を出します。このファイルの読み込みは request ごとです。`--dec-timing` による集計では `rolled back` の数を観測できます。

根拠: `src/program/generate.cpp:14777-14801,16141-16150,16219-16234,16603-16661,16713-16723`; `sycl/src/program/generate.cpp:10428-10452,11122-11131,11195-11209,11420-11432,11601-11602,11667-11691,11735-11747`。

## 根拠

- 対象名の全コード参照は `src/program/generate.cpp:14786` と `sycl/src/program/generate.cpp:10437`。いずれも `pipe_dbg_env()` 経由で、helper の gate は各ファイル `src/program/generate.cpp:464-467`、`sycl/src/program/generate.cpp:300-303`。
- pipeline の CLI 説明と初期値: `src/program/generate.cpp:891-896,1041-1044`。CLI 値の parse: `src/program/generate.cpp:3258`。
- pipeline の起動条件・unsupported 条件: `src/program/generate.cpp:4970-5020,10000-10005`。
- force-miss の値読み取りと switch による上書き: `src/program/generate.cpp:14777-14801`、SYCL 対応箇所 `sycl/src/program/generate.cpp:10428-10452`。
- 投機窓の先頭 token の変更: `src/program/generate.cpp:16219-16234`、SYCL 対応箇所 `sycl/src/program/generate.cpp:11195-11209`。
- 不一致後の rollback: CUDA `src/program/generate.cpp:16603-16661,16404-16424`、SYCL `sycl/src/program/generate.cpp:11601-11602,11667-11691,11420-11432`。
- switch と timing 集計のログ: CUDA `src/program/generate.cpp:14789-14801,16713-16723`、SYCL `sycl/src/program/generate.cpp:10440-10452,11735-11747`。

`docs/DETAILS.md` には本変数固有の説明や測定値を確認できませんでした。ここではソースで確認できる診断動作のみを記載しています。
