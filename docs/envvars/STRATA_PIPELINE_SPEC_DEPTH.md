# `STRATA_PIPELINE_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の pipelined decode で、推測 window B を先行実行する front stage 数の上限を指定します。深さ `k` の場合、B は先頭から最大 `k` 個の front stage まで speculative に進みます。最後の stage は front stage ではなく、この値の対象外です。

これはデバッグ用の調整値です。Strata は `STRATA_PIPELINE_DEBUG` が有効な場合に限り値を読みます。既定値は十分大きい `1 << 20` で、実際の stage 数によって上限が決まります。

## 値と判定

`pipe_dbg_env()` が返した文字列を `std::atoi` で変換し、`std::max(1, ...)` を適用します。文字列全体の検証はせず、`atoi` が変換できる先頭の整数部分を使います。

| 状態 | `pl_spec_depth` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効 | 既定値 `1 << 20`（対象変数は helper が `nullptr` を返すため、実質読み取られない） |
| debug 有効、対象変数が未設定 | `1 << 20` |
| debug 有効、値が `3`、`3tail`、`+3` | `3` |
| debug 有効、値が `0`、負数、空文字、数値に変換できない文字列 | `1` |

深さ 0 や負数で speculative 実行を完全に止めることはできません。最低 1 に丸められます。正の値に明示的な上限はありませんが、条件式 `B.fr < pl_nf` によって front stage 数以上には進みません。CLI 引数や `STRATA_PIPELINE_SWITCH` の値でこの深さを上書きする処理はありません。

`STRATA_PIPELINE_DEBUG` は未設定、空文字、先頭が `0` の文字列で無効です。それ以外の設定値（例: `1`, `true`, `false`）で有効です。debug 判定は `pipe_dbg_env()` の static 値として初回呼び出し時に cache されます。

## 有効になる条件

対象値が有効に読み取られても、次を満たさなければ decode の speculative 深度には影響しません。

- `--serve` の複数 GPU layer split で各 stage が別 GPU にあり、`pipe` が成立する。
- `--pipeline-windows 2` が有効である。`--pipeline-windows 1` は decode loop を pipelined にせず、この変数の分岐も使わない。
- MTP drafter と `--spec` 2 以上が設定され、`--batch`, `--peer-device`, helper cache など pipeline を無効にする条件に当たらない。
- GDN snapshot の確保に成功し、要求中の decode が repetition penalties (`penalty_last_n`) や coupled draft sampling により serial 実行へ切り替えられない。
- request がキャンセル済みでなく、生成上限に達していない。

CLI から pipeline を要求した場合の非対応条件は `--pipeline-windows ... is off: ...` と stderr に出し、その設定を 0 にします。`generate.cpp` の自動選択は `STRATA_USE_HIP` build でのみ有効で、server、GPU split、stage 数、MTP、batch、peer/helper cache 等の条件で決まります。NVIDIA builds は自動ではなく opt-in とする説明があります。深さの値自体がこれらの条件を変えることはありません。

2 stage split では front stage は 1 個なので、深さ 1 以上の値は同じ実効範囲です。3 stage 以上では、深さを小さくすると B の speculative 実行が早い front stage で止まり、A の通常の進行は全 stage を通ります。

## 実行時の詳細

`pipe_dbg_env()` は初回に `STRATA_PIPELINE_DEBUG` を調べ、debug が有効な場合だけ引数名を `std::getenv()` に渡します。対象環境変数の直接参照はこの helper 呼び出しだけです。`pl_spec_depth` は pipelined decode branch 内の `static const int` で、一度だけ対象値を変換します。したがって、debug 判定後に環境を変更しても helper 判定は変わらず、深さを初回評価後に変更しても実行中の値には反映されません。

各 loop で B を次の front stage に進める条件に `B.fr < pl_spec_depth` が含まれます。この条件を満たす間は、A の commit、B 用 snapshot、B の speculative launch を行います。深さに達した後はこの launch 分岐を通らず、B はそれ以上の front stage で speculative launch されません。通常の verify・commit の結果に応じて B は採用または破棄されます。

この変数固有のログ、警告、終了コードはありません。pipeline decode の診断ログは `STRATA_DECODE_TIMING` 等で出る一般統計であり、この深さの設定値は表示されません。pipeline の準備や verify が失敗した場合は別の一般エラー経路があり、たとえば `pl_prepare()` 失敗時に `ERR` を出して `1` を返す処理がありますが、深さ値がその失敗を直接起こす判定はありません。

## 根拠

- 対象名の全一致検索では `src/program/generate.cpp:16524-16527` のコメントと helper 呼び出しだけが見つかる。実際の判定条件と B の処理は `src/program/generate.cpp:16522-16559`。
- helper の debug gate、値の有無に応じた読み取り: `src/program/generate.cpp:461-467`。全 pipeline debug/tuning 変数を debug 有効時だけ読む旨も同所にある。
- `pipe` の成立条件と front stage 数: `src/program/generate.cpp:10000-10005,10279-10284`。pipelined decode の実行条件、serial fallback の request 条件: `src/program/generate.cpp:16079-16103`。
- CLI の `--pipeline-windows` 値域と pipeline の対応条件、自動選択の backend 条件: `src/program/generate.cpp:3258,4985-5003,5005-5020`。pipeline の stage 数に関する概要、debug gate の説明: `docs/MULTI_GPU.md:174-197`。
- pipeline 準備失敗時の `ERR` と終了: `src/program/generate.cpp:16098-16103`。深さ専用のログやエラーはない。
