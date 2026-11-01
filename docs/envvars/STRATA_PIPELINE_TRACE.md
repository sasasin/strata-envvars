# `STRATA_PIPELINE_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` の pipelined decode loop が記録するイベントと相対時刻を、指定ファイルへ追記します。モデル計算や decode の選択を変える設定ではなく、診断用の記録先です。

この名前を読むコードは CUDA/HIP 系の `src/program/generate.cpp` と SYCL の `sycl/src/program/generate.cpp` にあります。いずれも `pipe_dbg_env("STRATA_PIPELINE_TRACE")` を通すため、`STRATA_PIPELINE_DEBUG` が有効でなければこの変数は読み取られず、記録も行われません。

## 値と判定

| 状態 | 挙動 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | helper が `nullptr` を返す。TRACE の値は参照せず、記録しない |
| `STRATA_PIPELINE_DEBUG` の先頭文字が `0` 以外 | TRACE の環境値を取得する。`STRATA_PIPELINE_TRACE` が未設定なら記録しない |
| TRACE にパスが設定されている | 文字列を変換せずファイルパスとして使用し、リクエスト終了時に append mode (`"a"`) で開く |
| TRACE が空文字 | 空文字列も未設定ではないため記録バッファは作られるが、`fopen("", "a")` が失敗する。失敗は無視され、ログやエラーにはならない |

どちらの値も真偽値や数値として parse しません。`STRATA_PIPELINE_DEBUG=false` は先頭文字が `0` 以外なので有効です。一方、`STRATA_PIPELINE_DEBUG=0anything` は無効です。TRACE の設定値はパスとしてそのまま渡されます。

## 有効になる条件

- pipelined decode loop が実際に実行される必要があります。CUDA/HIP 側では `pipe && pl_pw >= 2 && pl_snap_ok` が要求条件で、さらに serial fallback がなく、キャンセル中でなく、生成上限に達していない場合にループへ入ります。SYCL 側も `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` と serial fallback 等の条件で分岐します。
- `pipe` / `pl_pw` は `--pipeline-windows` の設定・適用条件に依存します。パイプラインが無効、準備失敗、またはそのリクエストが serial fallback になった場合、この trace loop は実行されません。
- TRACE を読むためには、上記に加えて `STRATA_PIPELINE_DEBUG` の gate が有効でなければなりません。Strata の `docs/MULTI_GPU.md` も `STRATA_PIPELINE_*` の tuning/test 変数は `STRATA_PIPELINE_DEBUG=1` の場合だけ読むと説明しています。

## 実行時の詳細

`pipe_dbg_env` 内の `STRATA_PIPELINE_DEBUG` 判定は function-local `static const bool` で、プロセス内の最初の helper 呼び出し時に一度だけ評価されます。従って、その後に環境値を変更しても gate 判定は再評価されません。TRACE のパスも各 backend の pipelined decode block 内の `static const char*` に保存され、最初にその block に入った時に一度取得されます。後続リクエストで値を変更してもパスは再取得されません。

trace が有効な場合、loop の開始時に時刻基準を作り、イベントごとに「経過ミリ秒、イベント名、連番、整数引数 1、整数引数 2」の行をメモリ上へ追加します。主なイベント名は `F0`, `F1`, `U`, `CE`, `CD`, `L0`, `L1`, `V`, `CL` です。loop の drain 後、ファイルを `"a"` で開き、`# request p0=<値>` の区切り行とイベント行を追記して閉じます。同じ出力先に複数リクエストを記録する設計です。

ファイルを開けなかった場合は記録を捨てます。`fopen` の戻り値が null の場合に分岐するだけで、`perror`、stderr/stdout の警告、終了コード変更はありません。write/close の戻り値も確認していません。trace 処理自体に失敗終了経路はありません。

## 根拠

- helper の gate と値判定: `src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303`。
- CUDA/HIP 側の loop 適用条件と trace パス取得・イベント記録: `src/program/generate.cpp:16079-16103,16182-16192`。
- CUDA/HIP 側のイベント追加箇所と追記処理: `src/program/generate.cpp:16206,16348,16400,16424,16453,16502,16520,16556,16568,16611,16642,16671,16685-16701`。
- SYCL 側の loop 適用条件と trace パス取得・イベント記録: `sycl/src/program/generate.cpp:11038-11052,11157-11166`。
- SYCL 側のイベント追加箇所と追記処理: `sycl/src/program/generate.cpp:11180,11360,11404,11432,11461,11510,11524,11558,11570,11609,11675,11698,11710-11724`。
- CLI の `--pipeline-windows` 値の境界と適用判定: `src/program/generate.cpp:3258,4970-5021`。
- パイプラインの backend・サーバー・draft layer 条件と debug gate の文書説明: `docs/MULTI_GPU.md:176-197`。
