# `DS4_FLUSH_FINISH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 実装の DS4 `finish` dispatch の後、指定条件に一致した呼び出しで `ds4_metal_flush()` を実行します。ソースコメントでは、どの finish 呼び出しの後に drain が必要かを調べるデバッグ用とされています。これは GPU 処理の選択や値の計算を切り替える変数ではなく、対象 dispatch の後に同期処理を挿入するものです。

## 値と判定

`std::getenv()` で設定有無を確認し、設定されていれば値を `std::atoi()` に渡します。文字列全体の妥当性検査はありません。

| 値（`atoi` の結果） | flush を行う finish 呼び出し |
|---|---|
| 未設定 | なし |
| `1` | `f.dst` が null でない |
| `2` | `f.rd > 0` |
| `3` | `f.w` が null でない |
| `4` | `f.quant` が 0 でない |
| `5` | `f.dst` が null |
| `6` | `f.dst` が null かつ `f.rd == 0` |
| `7` | `f.rd > 0` かつ `f.inverse` が true |
| `8` | `f.rd > 0`、`f.inverse` が false、かつ `f.dst` が null |
| `9` | `f.rd > 0` かつ `f.dst` が null |
| `10` | `f.dst` が non-null、または `f.inverse` が true |
| `11` | `f.rd > 0` かつ `f.inverse` が false |
| 上記以外 | なし |

たとえば空文字や数字で始まらない文字列は `atoi` により 0 となるため、対象条件に一致しません。先頭の空白と符号は `atoi` の変換対象で、数値の後ろに文字があっても数値部分が使われます（例: `4debug` は 4）。負数や 0 はどの条件にも一致しません。`atoi` が表現できる範囲外の値について、実装は特別な処理をしていません。

## 有効になる条件

- `src/dsv41/ds4_kernels.cu` が `STRATA_METAL` 定義下で Metal host の `finish()` を呼び、その関数が成功経路を進む必要があります。通常の CUDA fallback や Metal host が false を返して fallback する経路では、この環境変数の読み取り箇所には到達しません。
- `n_vec <= 0` または `len <= 0` の呼び出し、Metal の初期化・host view・buffer wrap・pipeline 取得に失敗して早期 return する呼び出しでは読み取られません。
- `f.pdst` の有無に応じて DS4 finish は packed rows と通常の finish に分岐しますが、両方とも Metal host `finish()` を通れば同じ環境変数判定を受けます。
- CLI、サーバーモード、モデル状態、OS 名による追加判定は、この変数の読み取り箇所にはありません。適用範囲は Metal host finish 経路です。

## 実行時の詳細

環境変数は `finish()` の dispatch 後、毎回読み直されます。値を `static` に cache していないため、プロセス内で環境を変更した場合は次の finish 呼び出しに反映されます。該当条件に一致すると `ds4_metal_flush()` が呼ばれます。同関数は Metal runtime の GPU stream について保留中の処理を flush し、submitted 値まで wait した後、Metal host `Context` の `flush_runs()` を呼びます。同期関数自身はログを出さず、この分岐による終了・エラー処理もありません。

同じ位置で別の設定も評価されます。`DS4_FINISH_SPLIT` が設定され、`f.quant` が真なら先に `split_runs()` が呼ばれます。また `DS4_FLUSH_FINISH_CTX` が設定されて `f.quant` が真なら、値の `atoi` 結果が 2 のとき `split_runs()`、それ以外のとき `flush_runs()` が、対象変数の判定より先に呼ばれます。これらは `DS4_FLUSH_FINISH` の条件判定を変更しませんが、同じ finish の前段で処理を追加することがあります。

## 根拠

- `metal/src/engine/ds4_finish.cpp:136-141` — Metal host finish の入口と早期 return。
- `metal/src/engine/ds4_finish.cpp:176-189` — dispatch 後の順序、`DS4_FINISH_SPLIT`、`DS4_FLUSH_FINISH_CTX`、対象変数の `atoi` 判定と全条件。
- `src/dsv41/ds4_kernels.cu:2196-2218` — DS4 finish 呼び出し、`STRATA_METAL` guard、Metal host 成功時の return と fallback。
- `metal/src/engine/ds4_finish.cpp:2728-2736` — `ds4_metal_flush()` が呼ぶ stream 同期と `flush_runs()`。
- `metal/src/gpu/runtime.cpp:549-559` — 保留中 stream の flush と submitted 値までの wait。
- `docs/envvars/000_envvers.md:192-193` — 候補一覧には `DS4_FLUSH_FINISH` と `DS4_FLUSH_FINISH_CTX` が掲載されています。候補名の直接参照は対象ソースで `metal/src/engine/ds4_finish.cpp:184` の読み取り箇所のみ確認しました。
