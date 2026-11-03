# `FNX_ROUTE_FILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

split エンジンの expert 選択回数を出力する測定用ファイルのパスです。Strata の同梱ツール `sfnx` と `fnx_run` がこの値を読みます。通常の Strata CLI 全般の設定ではありません。対象名の参照はこの 2 ツールに限られます（`src/split/tools/sfnx.cpp:546`, `src/split/tools/fnx_run.cpp:1146`）。

## 値と判定

値は数値に変換せず、`getenv()` が返す文字列をファイルパスとして使います。空白除去、パス正規化、CLI 引数との優先順位はありません。`sfnx` の起動時検査は値そのものではなく設定の有無だけを見るため、空文字も設定済みです（`src/split/tools/sfnx.cpp:1007-1012`）。

| 状態 | `sfnx` | `fnx_run` の MTP モード |
|---|---|---|
| 未設定 | `FNX_ROUTE_COUNT` が有効なら、モデル読み込み前に起動エラー。無効なら route 出力なし | この変数を読む分岐に入らず、route 出力なし |
| 空文字 | 設定済みとして検査を通る。保存時に書き込みに失敗し、stderr に警告。route counting を停止してサーバーは続行 | 空パスへの書き込みに失敗し、stderr にエラー。終了コード 1 |
| 非空文字列 | その文字列を出力先として使用。書き込み失敗時は警告し、route counting を停止 | その文字列を出力先として使用。失敗時はエラー、終了コード 1 |

`FNX_ROUTE_COUNT` は別設定です。split engine は環境値を整数全体として読み、0 以外ならカウント領域を確保します。未設定時は 0、空文字・不正な数値・整数範囲外は `env_int` の変換エラーです（`src/split/src/env.hpp:15-21,33-40,51-52`; `src/split/src/engine.cu:193-196`）。`sfnx` では有効な route count に対して `FNX_ROUTE_FILE` が必須ですが、`fnx_run` には同じ事前検査がありません（`src/split/tools/sfnx.cpp:1009-1012`）。

`fnx_run` でファイルパスが設定されている場合、`FNX_ROUTE_COUNT` が無効だと空の tally vector のため保存エラーになります（`src/split/tools/fnx_run.cpp:1146-1151`）。

## 有効になる条件

- split エンジンを含む CUDA または HIP のビルドが対象です。`engine.cu` は split ターゲットの一部で、HIP ビルドでは HIP 言語としてコンパイルされます（`src/split/CMakeLists.txt:64-80`）。
- `sfnx` では `--serve` の起動経路で使います（`src/split/tools/sfnx.cpp:1040-1059`）。route カウント領域が作られるのは `FNX_ROUTE_COUNT` が非 0 のときだけです。`FNX_ROUTE_FILE` だけを設定しても `route_counts()` は空を返すため、保存処理は何も出力せず、警告もしません（`src/split/src/engine.cu:193-196,663-669`; `src/split/tools/sfnx.cpp:543-546`）。
- `fnx_run` では `mtp` モードの実行結果を保存する箇所でのみ `FNX_ROUTE_FILE` を読みます。ほかのモードや `fnx_run_cmd` の lab mode はこの出力箇所を通りません（`src/split/tools/fnx_run.cpp:958-982,994,1145-1164`）。`FNX_ROUTE_COUNT` が無効なら `route_counts()` は空で、ファイルを開いた後に「no tallies」エラーとなります。

## 実行時の詳細

engine 初期化時にカード 0 用の `route_cnt` を確保・ゼロ初期化します。route kernel が decode 側を layer 添字 `l`、prompt 側を `NL + l` に加算します（`src/split/src/engine.cu:193-196,912-914`; prompt 側は `src/split/src/prefill.cu:1280`）。`Engine::route_counts()` は領域がなければ空 vector、あればその全データを host にコピーします（`src/split/src/engine.cu:663-669`）。

`sfnx` は各応答終了時に `save_routes()` を呼びます。値は起動時にキャッシュせず、保存のたびに `getenv()` で読み直します。カウント vector が空でなければ、まず `<パス>.tmp` に書き、成功後に `rename()` して指定パスへ置き換えます。失敗すると `sfnx: FNX_ROUTE_FILE: cannot write ...: route counting stopped` を stderr に出し、以降のカウント保存を止めますが、サーバー処理は続きます（`src/split/tools/sfnx.cpp:514-529,543-551,554-570,839-854`）。

`fnx_run` の MTP モードは実行後に値を読み、`wb` で直接開いて vector を書きます。各要素を 4 byte で書き、結果は sfnx 形式の route tally です。vector が空、ファイルを開けない、書き込みまたは close が失敗した場合、`FNX_ROUTE_FILE <値>: no tallies (FNX_ROUTE_COUNT=1?) or not written` を stderr に出し、その処理から 1 を返します（`src/split/tools/fnx_run.cpp:1145-1152`）。`sfnx` ではファイル保存の失敗が測定を止めるだけなのに対し、`fnx_run` では当該コマンドが失敗します。

## 根拠

- 候補一覧上の名前: `docs/envvars/000_envvers.md:598-601`（候補名が並ぶ箇所。実装の根拠は上記 Strata ソース）。
- 値の有無検査、起動失敗経路: `src/split/tools/sfnx.cpp:1007-1012,1040-1048`。
- カウントの有効条件と領域の確保: `src/split/src/env.hpp:33-52`, `src/split/src/engine.cu:193-196`。
- tally 生成と取得: `src/split/src/engine.cu:663-669,905-914`, `src/split/src/prefill.cu:1280`。
- `sfnx` の書き込みと失敗処理: `src/split/tools/sfnx.cpp:522-550,554-570,839-854`。
- `fnx_run` の適用モードと書き込み・終了経路: `src/split/tools/fnx_run.cpp:958-982,994,1145-1164,1364-1373`。
