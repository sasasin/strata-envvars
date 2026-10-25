# `STRATA_PIPELINE_FORCE_MISS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

パイプライン検証ループのテスト用フックです。指定した間隔で、次の推測 window の先頭 token を意図的に誤らせ、推測が外れたときの rollback を通します。通常の生成設定ではなく、`STRATA_PIPELINE_DEBUG` が有効なときだけ使われます。CUDA と SYCL の `generate.cpp` に同じ判定・処理があります。

## 値と判定

`pipe_dbg_env()` がこの変数を読む前に `STRATA_PIPELINE_DEBUG` を確認します。未設定または空文字、あるいは先頭文字が `0` の場合は、この変数の値を無視して既定値 `0` にします。それ以外の `STRATA_PIPELINE_DEBUG` 値では、この変数を読むことができます。

| `STRATA_PIPELINE_DEBUG` が有効な場合の値 | `pl_force_miss` |
|---|---:|
| `STRATA_PIPELINE_FORCE_MISS` 未設定 | 0 |
| 設定済み | `atoi` で変換した値と 0 の大きい方 |

したがって `0`、負数、空文字、数値に変換できない文字列は 0 になります。`2x` のように数字の後ろに文字があっても、`atoi` が読む先頭の数値部分が使われます。先頭の空白や符号も `atoi` の変換規則に従います。文字列全体の妥当性検査はありません。`STRATA_PIPELINE_SWITCH` で指定したファイルが読み取れ、その内容に `force_miss=<値>` があれば、そちらの整数変換結果（0 以上）が環境変数から得た値を上書きします。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` は `pipe_dbg_env()` 内の `static` 値として初回判定時にキャッシュされます。最初の判定後に環境を変更してもデバッグ用変数の可視性は変わりません。
- pipeline debug が有効でも、パイプライン用の読み取り・decode 経路が実行されなければ効果はありません。`--pipeline-windows` 等で該当する pipeline loop が使われる必要があります。
- `STRATA_PIPELINE_FORCE_MISS` 自体の変換結果は request 処理箇所で計算されます。`STRATA_PIPELINE_SWITCH` が使われている場合は、同ファイルの `force_miss=` がその request の値に優先します。

## 実行時の詳細

`pl_force_miss=k` は `make_b()` で作られる chain 由来の次 window `B` について、`k > 0` のときだけ使われます。`B` が作られるたび `pl_fm` を増やし、`pl_fm` が `k` の倍数になる回に限って `B.tok[0]` を `0` と `1` の間で切り替えます。残りの token や確率、モデルの出力そのものはここでは書き換えません。この候補の変更で推測ミスと rollback を試験できますが、切り替え後の token が検証先の正解と必ず異なることまではコードは保証しません。

この変数専用のログやエラー出力はありません。switch ファイルを読み取れた場合は、`strata pipeline switch: ... force_miss=<値> ...` を stderr に出します。`docs/MULTI_GPU.md` は4段 GPU の測定条件で、全推測を誤らせる設定として `STRATA_PIPELINE_FORCE_MISS=1` を使ったと記録しています。これはその資料に書かれた測定・検証条件であり、一般の性能や正確性の保証ではありません。

## 根拠

- `src/program/generate.cpp:340-345`, `sycl/src/program/generate.cpp:296-301` — pipeline 用環境変数の共通ゲートと `STRATA_PIPELINE_DEBUG` の判定・static cache。
- `src/program/generate.cpp:12924-12948`, `sycl/src/program/generate.cpp:10167-10191` — request 処理での値の読み取り、変換、switch ファイルによる上書きとログ。
- `src/program/generate.cpp:14118-14131,14138-14139,14218-14222`, `sycl/src/program/generate.cpp:10918-10934` — chain 由来 window 作成時の間隔カウントと先頭 token の反転。
- `docs/MULTI_GPU.md:489-493,498-500` — 記載された4段 GPU の測定条件と debug gate の説明。
