# `DS4_IQ1S_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 の CPU expert lane で、IQ1_S の gate/up/down 計算に Strata 独自の multi-token rows 実装を使うことを許可します。未設定時は one-GPU decode path の判定に従います。設定すると初期判定を上書きできますが、初期 one-GPU 判定が成立した実行では、その後 PCIe lane が何も stream しないと判明した際にこの許可も解除されます。

この変数が切り替えるのは CPU 側の IQ1_S 行計算です。単一 token の計算では独自 rows を使わず、2 token 以上の計算に限って許可が参照されます。

## 値と判定

`env_tri()` は環境変数が未設定または空文字なら「未指定」として `-1` を返し、それ以外は `atoi()` の結果が 0 かどうかで判定します。したがって文字列全体の検証はありません。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定、空文字 | 未指定 | 初期 one-GPU 判定 `one` を使う |
| `0`、`false`、数値に変換できない文字列 | 0 | 独自 IQ1_S rows を無効化 |
| `1`、`-1`、`2`、`1tail` | 0 以外 | 独自 IQ1_S rows を許可 |

`atoi()` は先頭の空白と符号を読み、数値部分以降は無視します。数値として読める接頭辞がない場合は 0 です。空文字だけは `atoi()` に渡す前に未指定として扱われます。根拠: `src/dsv41/ds4_model.cu:6090-6093,6130-6135`。

## 有効になる条件

- 対象は DS4 の GGUF CPU expert lane です。IQ1_S の gate/up と down は `iq_cpu_gate_up()` / `iq_cpu_down()` を通り、独自 rows が選ばれない場合は native CPU rows にフォールバックします（`src/dsv41/ds4_model.cu:8257-8281`, `src/dsv41/ds4_iq_cpu.cpp:855-893`）。
- 独自実装は `STRATA_NATIVE_EXPERTS` 有効時にだけ実装され、x86-64 の AVX2 が必要です。非 x86 または `STRATA_NATIVE_EXPERTS` 無効の分岐では `iq_cpu_iq1s_rows()` は空実装です（`src/dsv41/ds4_iq_cpu.cpp:32-50,747-770,898-920`; `CMakeLists.txt:176`）。
- `DS4_IQ_OWN=0` の場合、独自 rows 自体が無効です。`own()` はこの設定を初回評価時に読むため、`DS4_IQ1S_ROWS` を有効にしてもこの条件を越えません（`src/dsv41/ds4_iq_cpu.cpp:743-770`）。
- 独自 IQ1_S rows は `nt < 2` では選ばれません。2 token 以上で、許可フラグが true の場合にだけ `own(type)` が選択を試します（`src/dsv41/ds4_iq_cpu.cpp:823-828`）。
- `DS4_IQ1S_ROWS` 未設定時の `one` は、HIP 以外で GPU が 1 台、1 group、group 内 memory が 1 台で、CUDA device property が discrete と判定された場合に true です。それ以外は false です（`src/dsv41/ds4_model.cu:6103-6115`）。
- `one` が true だった場合、後続の `one_gpu_plan()` が lane の測定結果を調べ、CPU lane から stream する layer がなく、`DS4_STREAM=2` でも `DS4_STREAM_FORCE` でもないと、IQ1_S rows を明示設定していても無効化します。初期 `one` が false の経路では、この後続判定は早期 return し、明示設定の許可を解除しません（`src/dsv41/ds4_model.cu:6143-6158`）。

## 実行時の詳細

`one_gpu_path()` はモデル初期化中、GPU/group 構成が確定した後に一度呼ばれ、ここで環境変数を読み、CPU rows 実装の atomic 許可フラグへ設定します（`src/dsv41/ds4_model.cu:2793-2798,6130-6135`; `src/dsv41/ds4_iq_cpu.cpp:823-828,897`）。この箇所に static cache はありませんが、同じモデル初期化中に繰り返し読むコードでもありません。初期化後にプロセス環境を変えてもこの設定には反映されず、モデルを再初期化した場合は再評価されます。上記の `one_gpu_plan()` は lane の計画後にフラグを false にすることがあります。

変数専用のログやエラーはありません。GGUF では one-GPU path の起動ログが出ますが、そこに表示されるのは `DS4_STREAM_WIN` と `DS4_LAND` の指定であり、この変数の値ではありません。lane が何も stream しない場合は path を off にするログが出ます（`src/dsv41/ds4_model.cu:6136-6138,6148-6174`）。独自 rows の採用可否を確認する診断ログは別変数 `DS4_IQ_VERBOSE` が設定されている場合に出ます（`src/dsv41/ds4_iq_cpu.cpp:812-815`）。`DS4_IQ1S_ROWS` 自体による終了・失敗経路は見つかりませんでした。

## 根拠

- 候補名の Strata ソース全体検索では、実参照は `src/dsv41/ds4_model.cu:6133` の `env_tri("DS4_IQ1S_ROWS")` の 1 箇所です。値の取得と変換は同ファイル `:6090-6093` の helper を通ります。
- one-GPU path の構成判定と環境値の適用: `src/dsv41/ds4_model.cu:6103-6138`。
- lane 計画後の無効化とログ: `src/dsv41/ds4_model.cu:6143-6174`。
- CPU rows の multi-token 条件、AVX2 / `DS4_IQ_OWN` 条件、fallback: `src/dsv41/ds4_iq_cpu.cpp:743-828,855-893`。
- `docs/DETAILS.md` にこの変数の個別説明はありませんでした。
