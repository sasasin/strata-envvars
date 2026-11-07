# `STRATA_PROMPT_KPROF`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal の prompt-chain で、1 chunk の各 GPU dispatch を個別に実行して GPU 時間を集計し、kernel 名と形状ごとの表を出す診断用フックです。一般の CUDA/HIP/SYCL 実装や Metal の streaming prompt 経路にはこの名前の読み取りがありません。Metal prompt-chain を選んだ場合でも、chunk が 1024 行未満なら集計処理は呼ばれません。

集計は単なる時計測ではありません。個別 dispatch 群を実行し、その後 chunk 全体も計測のために実行してから、通常の chunk 実行へ進みます。実装コメントは、この profiling により GDN state が 2 回進むと記しています。実際の呼び出し列は個別 dispatch 実行、profiling 用 chunk 実行、通常 chunk 実行です。コードコメントの「2 回」がどの状態更新を数えた表現かはコードだけでは特定できないため、profiling 有効時の内部状態や生成結果を通常実行と同一とは扱えません。通常利用では設定しない診断用の動作です。

## 値と判定

| 状態 | 判定・出力先 |
|---|---|
| 未設定 | 最初の `pc_chunk` で無効。既定で profiling しない。 |
| 設定あり（空文字を含む） | 値の内容を判定せず有効。`0`、`false`、空文字も有効値。 |
| profiling 有効時の値が `/` で始まる | その値をファイルパスとして `fopen(path, "w")` で開く。書き込みごとにファイルを切り詰める。 |
| profiling 有効時の値が `/` で始まらない | `stderr` に出力する。例: `1`, `0`, `false`, 空文字、相対パス。 |
| `/` で始まるがファイルを開けない | `stderr` に fallback する。 |

値を数値や真偽値へ変換せず、設定有無だけを `getenv(...) != nullptr` で判定します。大文字小文字、空白、値の全体は検査しません。profiling の有効判定は `pc_chunk` 内の function-local `static const bool` に保存され、初回 `pc_chunk` で一度だけ評価されます。以後に環境を変更しても有効・無効は切り替わりません。一方、出力先の値は各 qualifying chunk の `pc_kprof` 呼び出し時に改めて読みます。

## 有効になる条件

- Metal backend の非 streaming prompt-chain 経路であること。`prompt_run_rows` は `STRATA_METAL_PROMPT=window` なら window 経路を選び、非 streaming の場合は prompt の行数が `STRATA_METAL_PROMPT_MIN`（既定 32）以上のとき `Window::prompt` に進みます。streaming 時は別の prompt GEMM 経路です。
- `Window::prompt` が作る個々の chunk の行数 `nT` が 1024 以上であること。prompt 全体が 1024 行以上でも、1024 行未満の末尾 chunk は profiling されません。
- 初回 `pc_chunk` の時点で変数が設定されていること。

この経路の chunk サイズは `STRATA_METAL_PROMPT_CHUNK`（既定 2048、64..8192 に clamp）で決まり、prompt はそのサイズで分割されます。これは対象変数の値域ではなく、1024 行条件に影響する別設定です。CLI 引数による KPROF 専用上書きは見つかりません。

## 実行時の詳細

`pc_chunk` は prompt chunk の dispatch 一覧を組み立てた後、`kprof && nT >= 1024` のとき `pc_kprof` を呼びます。`pc_kprof` は一覧の各 dispatch について `cx_->run({d}, 1, false, false)` を呼び、kernel 名ごとに GPU 時間と回数を累積します。GEMM dispatch には M/N/K、dequant dispatch には入力・出力幅を名前に付加します。続いて同じ chunk を `cx_->run(ds)` で実行し、その時間と個別時間の合計を記録します。その後、呼び出し元の `pc_chunk` が通常の処理として `cx_->run(ds)` をもう一度実行します。ソースコメントは、この診断実行により GDN state が 2 回進むと説明しています（`prompt_chain.inc:522-538`）。

表は累積値を kernel・shape ごとに GPU 時間降順で書き出します。`KPROF-TABLE`、`KPROF ...`、`KPROF chunk ...` の各行に総時間、構成比、回数、chunk の位置・行数・dispatch 数、個別実行合計時間、chunk 一括実行の wall/GPU 時間が含まれます。各 qualifying chunk の出力時にファイルを `"w"` で開き直しますが、集計 map は process 内 static で累積するため、ファイルにはその時点までの全 profiled chunk の集計が書かれます。

`cx_->run` の command buffer が失敗した場合、Metal runtime は stderr に `mtl: command buffer failed: <説明>` を出し、終了コード 5 でプロセスを終了します。KPROF 固有の値検証エラーや警告はありません。出力ファイルが開けないときは警告ではなく stderr fallback です。

## 根拠

- `metal/src/engine/prompt_chain.inc:142-187`: profiling 集計、dispatch ごとの実行、chunk 一括計測、出力先判定と表の出力。
- `metal/src/engine/prompt_chain.inc:522-538`: 設定有無の static cache、1024 行条件、profiling 後の通常 chunk 実行、state に関する実装コメント。
- `metal/src/engine/prompt_chain.inc:564-578`: chunk サイズの既定値 2048 と 64..8192 の clamp、prompt の分割と `pc_chunk` 呼び出し。
- `metal/src/engine/window.cpp:3581-3605`: Metal prompt の入口、window/非 streaming/streaming の経路選択、最低行数条件。
- `metal/src/mtl_rt.h:114-121`, `metal/src/mtl_rt.mm:914-991`: `Context::run` が dispatch を command buffer で実行し、command buffer 失敗時に stderr 出力後 `exit(5)` する実装。
