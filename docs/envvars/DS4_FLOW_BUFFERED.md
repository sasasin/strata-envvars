# `DS4_FLOW_BUFFERED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 の prompt flow がモデルファイルから expert を読む際、実行中の合計 token 数が指定値以下なら direct file descriptor を使わず、通常の `pread_par` 経路を使う上限を指定します。未設定時の既定値は `0` なので、この page-cache 経由を選ぶ条件は通常成立しません。環境変数を読んでいるのは `src/dsv41/ds4_model.cu` の flow 実行経路です。

## 値と判定

`run_dev_chunks()` 内の関数ローカル `static const int` として、最初にこの箇所を通ったときだけ読み取られます。設定があれば `std::atoi`、未設定なら `0` です。文字列全体の妥当性検査、clamp、明示的な無効値エラーはありません。

| 環境変数 | 判定結果 |
| --- | --- |
| 未設定 | `buf_max = 0` |
| 空文字 | `atoi("")` の結果 `0` |
| 数字で始まる文字列 | `atoi` が先頭の整数部分を使用。例: `12tail` は `12` |
| 先頭に空白・符号がある文字列 | `atoi` の規則で空白を読み飛ばし、符号付き整数を変換 |
| 整数として読めない文字列 | `atoi` の結果 `0` |
| `0` または負数 | `buf_max` は 0 以下。`run_n` は token 数の合計なので、通常の非負値では buffered 条件を満たさない |
| 正数 `N` | `run_n <= N` のとき `c.buffered = true` |

`run_n` は当該 `Run` の `run.T` 全要素の合計です。コマンドライン引数によるこの閾値の上書きはありません。プロセス起動後に環境を書き換えても、最初の評価後は反映されません。整数変換の範囲外入力に対する結果は、ここで使う `atoi` の仕様に委ねられています。

## 有効になる条件

- flow 自体が初期化されている必要があります。`DS4_FLOW` は未設定なら有効で、`atoi` が 0 になる値なら無効です。
- file-backed expert の処理が必要です。GGUF は `file_experts` が有効になり、flow の初期化では各デバイスの対象 trunk layer が MXFP4 であることを要求します。tensor-parallel の複数 member では `DS4_FLOW_TP` が非 0 で、down 行の分割条件も満たす必要があります。
- prompt が chunk 経路に入り、`run_dev_chunks()` の flow 分岐に到達する必要があります。chunk の既定値や `--prefill-chunk` が chunk 経路を決め、`DS4_CHUNK_MIN` は開始 token 数を上書きします。flow が全デバイスで有効で `DS4_CHUNK_MIN` が未設定の場合、初期化時の最小値は 2 です。さらに `pick_path()` が windows 経路を選べば flow は実行されません。
- `c.lm`（layer-major）経路では `run_dev_chunks()` が `run_dev_layers()` に移ります。この経路の file read job は `c.buffered` を参照せず direct descriptor を設定するため、この変数による切り替えは適用されません。

したがって、値を正に設定しただけでは常に効くわけではありません。flow と通常の `copy_ahead()` が実行され、file read job が発生した run に限り、閾値との比較が読み取り方式に影響します。RAM からコピーする job には影響しません。

## 実行時の詳細

flow の実行開始時、`run.T` の token 数を合計し `run_n <= buf_max` を `c.buffered` に保存します。通常の flow 読み込みでは、file job の direct descriptor (`dfd`) が設定され、`IoQueue` は対象ページが resident でない場合に direct read を試み、失敗時は `pread_par` に fallback します。`c.buffered` が true の場合はその job の `dfd` を無効値にし、direct read を試さず `pread_par` を通します。ページがすでに resident の場合や direct read が失敗した場合も、`IoQueue` 自身が `pread_par` を使います。

この環境変数専用のログや警告はありません。`--verbose` または `DS4_FLOW_STATS` が有効なら `ds4 prompt stream, CUDA...` の集計行に、disk unbuffered と page cache 経由の読み取り byte 数が表示されます。これは実際の読み取り経路の集計で、`DS4_FLOW_BUFFERED` の値を直接表示するものではありません。読み取りに失敗した場合は `copy_ahead()` が `reading layer <n> expert <n> from the model's files failed` を `err` に設定して失敗を返します。

## 根拠

- `src/dsv41/ds4_model.cu:744-750,762-785`: flow、file-backed reads、`c.buffered` の役割。
- `src/dsv41/ds4_model.cu:2750-2771,2788-2803`: `file_experts` の決定、prompt chunk の設定。
- `src/dsv41/ds4_model.cu:3670-3726`: `DS4_FLOW` / `DS4_FLOW_TP`、MXFP4 条件、flow 初期化、chunk 最小値。
- `src/dsv41/ds4_model.cu:12035-12080`: `DS4_FLOW_BUFFERED` の読み取り・cache、run token 数との比較、layer-major への分岐。
- `src/dsv41/ds4_model.cu:14862-14875,14877-14891,14894-14924`: prompt feed が chunk path / windows path を選ぶ箇所。
- `src/dsv41/ds4_model.cu:4833-4847,4861-4865`: buffered 条件の direct descriptor 設定と読み取り失敗経路。
- `src/dsv41/ds4_model.cu:13133-13158`: verbose または `DS4_FLOW_STATS` 時の読み取り byte 数ログ。
- `src/dsv41/ds4_pool.hpp:135-139,223-245`: direct read と `pread_par` の選択、fallback、byte 集計。

`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。ソース内コメント (`src/dsv41/ds4_model.cu:12067-12072`) には、短い prompt は page cache 経由にして decode で使う cache を保ち、1 GPU の長い run では `DS4_FLOW_BUFFERED` を 1024 にするという過去の計測文脈があります。コメントは特定環境の観察であり、この調査では性能を再測定していません。
