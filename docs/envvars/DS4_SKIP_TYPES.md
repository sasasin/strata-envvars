# `DS4_SKIP_TYPES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek 4.1 エンジンの IQ 行列ベクトル積で、指定した `type` の job を GPU dispatch 用のグループに入れずに飛ばします。実装コメントは `(timing only)` としています。通常の計算設定ではなく、計時時に特定 type の仕事を除外するためのフックです。

CUDA/HIP 側の `mv()` にはこの環境変数の参照がありません。この処理は `strata_ds4` の Metal ビルドで `STRATA_METAL` を定義し、Metal host 実装を組み込む経路に限られます。

## 値と判定

値は数値として parse されず、`std::strstr` で環境変数文字列内に `,` + job の `type` の10進表記 + `,` があるかを検索します。完全一致の要素リストではなく部分文字列検索です。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | job を飛ばさない |
| 空文字 | job を飛ばさない |
| `,16,` | `type == 16` の job を飛ばす |
| `,16,18,` | `type == 16` と `type == 18` の job を飛ばす |
| `16`、`16,`、`,16` | `type == 16` は一致せず、飛ばさない |
| `,016,`、`,16 ,` | `type == 16` は一致せず、飛ばさない |

要素の空白除去、数値変換、大文字小文字変換、入力検証はありません。空白を含まない整数 type を前後カンマで囲む必要があります。現在の Metal IQ job 分類では、switch に列挙された `13, 14, 16, 17, 18, 22, 19, 29` などの `q.type` が検索対象です（同じ switch の `default` を含め、全 job がこの判定を通ります）。

## 有効になる条件

- `strata_ds4` の Metal 実行経路であること。`metal/CMakeLists.txt` は `ds4_finish.cpp` を `strata_ds4` のソースに含め、同 target に `STRATA_METAL=1` を定義します。`src/dsv41/ds4_iq.cu` は `STRATA_METAL` 時、job 数 `n` が 1〜64 の場合に Metal host の `iq_mv()` へ渡します。それ以外の `n` ではこの環境変数は評価されません。
- `iq_mv()` が呼ばれ、`nj > 0` で、Metal runtime の `ensure()` が成功すること。これらを満たさない場合、この環境変数による判定箇所へ進みません。
- `DS4_SKIP_TYPES` は初回の `iq_mv()` 呼び出し時に関数内 `static` として読み取られます。その後の環境変更は、このプロセス内の同関数では再読込されません。

CLI 引数、設定ファイル、別環境変数との優先順位や上書き処理は見つかりません。`DS4_NO_MVN` は別の kernel 選択分岐ですが、skip 判定の後に評価され、skip 対象 job はどちらの kernel 経路にも追加されません。

## 実行時の詳細

`iq_mv()` は `DS4_DBG_JOBS` が設定されていれば、skip 判定より前に全 job の type 等を stderr に `iq_mv call: [t... n... k... c...]` と出力します。その後、`DS4_SKIP_TYPES` に一致した job は `continue` され、最大行数の更新、kernel 名の決定、dispatch グループへの追加を行いません。残った job は type と列数に応じて Metal kernel に渡されます。

一致する job が一部だけなら残りの job は通常どおり dispatch されます。全 job が一致して飛ばされると `max_n` は 0 のまま `iq_mv()` が `true` を返します。呼び出し元の `mv()` は `true` を受けて成功扱いで戻るため、CUDA 側の別実装などへの fallback はありません。飛ばした job の出力領域はこの呼び出しによって計算・書き込みされません。値を設定した際の専用警告や診断ログはなく、`DS4_DBG_JOBS` の job 一覧には skip 前の job が表示されます。

## 根拠

- `metal/src/engine/ds4_finish.cpp:727-778` — Metal `iq_mv()`、debug 出力、`DS4_SKIP_TYPES` の静的読み取りと部分文字列判定、job のグループ化、全 skip 時の早期成功。
- `metal/src/engine/ds4_finish.cpp:780-810` — 残った job 群の Metal dispatch と成功戻り値。
- `src/dsv41/ds4_iq.cu:1694-1697` — `STRATA_METAL` での Metal host 呼び出しと `true` 時の早期成功。
- `metal/CMakeLists.txt:135-142,165-171` — `ds4_finish.cpp` を `strata_ds4` に含め、target に `STRATA_METAL=1` を定義する構成。
