# `FNX_ROUTE_TRACE_FILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`src/split` の FNX ツールがルーティング trace を書き出すファイルパスです。`fnx_run` の `mtp` モードは実行後に指定先へ書き、`sfnx` は各 reply の後に指定先へ書きます。ファイルパスだけでは trace 収集は有効になりません。収集バッファは別変数 `FNX_ROUTE_TRACE` が正の値のときに作られます。

対象名の直接参照は `src/split/tools/fnx_run.cpp:1155` と `src/split/tools/sfnx.cpp:534,1011` です。`rg -n --hidden --glob '!.git/**' 'FNX_ROUTE_TRACE_FILE'` で得た候補名の全参照を確認しました。Strata の通常エンジンやサーバー共通設定ではなく、FNX の split ツール用です。

## 値と判定

この変数は文字列のパスとして読み、数値変換や文字列比較はしません。`getenv()` が null かどうかで未設定を判定します。

| 状態 | `fnx_run` (`mtp`) | `sfnx` |
|---|---|---|
| 未設定 | trace 出力を試みず、正常終了可能 | `FNX_ROUTE_TRACE` が正ならモデル読み込み前にエラー。そうでなければ出力しない |
| 設定あり・空文字 | 空パスで `fopen` を試し、書き込み失敗として stderr に出して status 1 | 起動時の存在確認は通る。trace があり最初に保存すると書き込み失敗を stderr に出し、以降の trace 保存を止める |
| 設定あり・非空文字 | その文字列を出力先に使う | その文字列を出力先に使う |

値の相対パス解決、正規化、別パスへの fallback は Strata 側では行いません。`sfnx` は `FNX_ROUTE_TRACE > 0` の場合に限り、`FNX_ROUTE_TRACE_FILE` が未設定だと `FNX_ROUTE_TRACE needs FNX_ROUTE_TRACE_FILE` を stderr に出し、モデルをロードせず status 2 で終了します。`FNX_ROUTE_TRACE_FILE` を設定しても `FNX_ROUTE_TRACE` が未設定・0・負数なら trace バッファはなく、ファイル出力は起きません。後者の判定は `env_int` による符号付き整数全体の厳密 parse で、未設定は 0、空文字や不正な整数文字列はエラーです。

## 有効になる条件

- 実装は `src/split/src/engine.cu` の CUDA FNX エンジンです。別の backend 共通の設定ではありません。
- `FNX_ROUTE_TRACE` を正の整数にして収集バッファを確保する必要があります。値 `M` に対して容量は `M * 1,000,000` picks です。ファイル変数はこの容量を変えません。
- `sfnx` は起動時に必要なパスの有無を検査しますが、パスの書き込み可能性は検査しません。書き込み可能性は最初の trace 保存時に判明します。
- `fnx_run` では出力処理が `mtp` モードの処理内にあります。ファイル変数は他モードの出力先にはなりません。

## 実行時の詳細

エンジン初期化時、`FNX_ROUTE_TRACE > 0` なら card 0 に mapped host memory の trace バッファと長さカウンタを確保します。モデルの FFN ルーティング時に、各 expert pick を `layer << 16 | expert` の unsigned 値として記録します。GPU kernel は pick ごとに atomic counter で書き込み位置を取るため、同じ kernel launch 内の並びが入力 row 順になる保証はありません。記録数が容量を超えると `route_trace()` は `FNX_ROUTE_TRACE: ... picks, room for ...: raise it` の例外を投げます。

`FNX_ROUTE_TRACE_FILE` の扱いはツールで異なります。

- `fnx_run` は `mtp` の計算後に変数を読み、全 trace を `wb` で開いたファイルへ書きます。出力は unsigned 値の4バイト列です。trace が空、ファイルを開けない、または全量を書けない場合は `FNX_ROUTE_TRACE_FILE <path>: no trace (FNX_ROUTE_TRACE=M?) or not written` を stderr に出して status 1 を返します。正常に書ければ `mtp` 処理は続いて status 0 になります。
- `sfnx` は `save_routes()` のたびに変数を読みます。最初の非空 trace は `wb`、以降は `ab` で追加します。これは reply 終了後に呼ばれます（単独 reply と batch slot の完了経路）。書き込み失敗時は `sfnx: FNX_ROUTE_TRACE_FILE: cannot write ...: route tracing stopped after ... picks` を stderr に出し、trace の保存だけを停止してサーバー処理は続けます。

ルーティング記録のカーネル呼び出しは FFN 層の実行経路にあり、prompt の行も同じ関数経路を通ります。そのため、ソース上の記録条件は「decode のみ」には限定されていません。`sfnx` のコメントは decode picks と説明していますが、実際の分岐は trace バッファの有無と有効な layer index を条件にしています。

## 根拠

- `src/split/tools/fnx_run.cpp:994-1000,1145-1164`: `mtp` モードでの実行後の route trace 出力、`wb`、失敗時の stderr と status 1。
- `src/split/tools/sfnx.cpp:1007-1012,1040-1049`: 起動時のパス要件検査と、モデルロード前の stderr / status 2。
- `src/split/tools/sfnx.cpp:514-540,554-570,846-855`: reply 完了後の保存、最初の `wb` と後続 `ab`、保存失敗時のログと継続。
- `src/split/src/env.hpp:15-21,33-40`: `FNX_ROUTE_TRACE` 用整数全体の parse、未設定既定値と不正値の例外。
- `src/split/src/engine.cu:193-205,672-683,905-915`: trace 容量確保、読み出しと容量超過判定、FFN 層での記録。
- `src/split/src/kernels.cu:1790-1795,1858-1860`: atomic counter で位置を取得して pick を `layer << 16 | expert` として格納。
