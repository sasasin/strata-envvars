# `STRATA_ROUTE_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_ROUTE_DUMP` は、CUDA/HIP エンジンの `expert_pool_dispatch_multi` が処理する layer-window ごとに、ルーティングされた distinct expert、各 expert の行数、GPU キャッシュ上の状態をテキストで追記出力する診断用フックです。値を読んでファイルを開く以外に、ルーティング、expert の選択、出力計算を変更する処理はありません。読み取りと書き込みは `engine/src/core/expert_source.cpp` にあります（`engine/src/core/expert_source.cpp:5426-5429,5528-5542`）。コードコメントは「bench only」としますが、実装にbench専用の条件分岐はなく、通常の generate 経路からも multi dispatch が呼ばれます（`engine/src/core/expert_source.cpp:5528-5532`; `engine/src/program/generate.cpp:1631-1636,14886,24547-24549`）。

## 値と判定

関数内 `static` 初期化子で `std::getenv` を呼び、値が未設定（null）または空文字なら無効、それ以外なら値全体をファイル名として `std::fopen(path, "a")` に渡します。真偽文字列や数値への変換はありません。したがって `0`、`false`、空白だけの値も空でないパスとして扱われます。ファイルを開けない場合はポインターが null となり、その後の記録を行いません（`engine/src/core/expert_source.cpp:5531-5532`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の multi dispatch で GPU plan と容量条件を満たす場合 | 記録なし | `trace.txt`、`0`、`false`（いずれもパス） | 空文字。パスを開けない場合も記録なし |
| 上記以外 | 読み取り箇所に到達しない | なし | なし |

CLI 引数や他の環境変数との優先順位はありません。CLI の `--dump-routing` は別経路で routing ID と weights を記録する機能であり、この変数の設定を上書きしません（`engine/src/program/generate.cpp:1608-1626,3898`）。

## 有効になる条件

- CUDA/HIP 用の共有 GPU engine に含まれるコードです。CPU-only build にはこの `strata_engine` ソースの組み込みはありません（`engine/cmake/strata_gpu_engine.cmake:305-316`）。
- `expert_pool_dispatch_multi` が呼ばれ、`d.plan != nullptr` かつ `n_tok * k <= kMaxWindowEntries` および `n_tok * k <= d.plan->cap` の分岐に入る必要があります。関数は `n_tok` が 1 以上 `kWindowMaxT` 以下であることも先に確認します（`engine/src/core/expert_source.cpp:5426-5434,5443-5449,5479`）。通常の generate 経路では verify の plan sink を `d.plan` に設定します（`engine/src/program/generate.cpp:14886,24547-24549`）。条件を満たさない場合は環境変数を読む処理にも到達しません。
- `STRATA_ROUTE_TAIL_SKIP` が有効な場合、出力される `nmiss` と `res` に tail-skip の状態が反映されます。この変数自体は tail-skip の有効化条件ではありません（`engine/src/core/expert_source.cpp:5502-5525,5533-5539`）。

## 実行時の詳細

環境変数はプロセス起動時ではなく、この関数内の出力ブロックが初めて実行された時に一度読みます。`static` に保存した `FILE*` を以後の呼び出しで再利用するため、プロセス実行中に環境値を変更しても反映されず、出力先も切り替わりません（`engine/src/core/expert_source.cpp:5531-5532`）。

出力ファイルは追記モードで開きます。各行は `layer n_tok nd nmiss |` に続けて、routing 順の各 distinct expert を `expert_id:rows:res` で記録します。`rows` はその window 内で expert ID が現れた回数、`res` は GPU cache resident が `1`、tail-skip が `2`、それ以外が `0` です。`nmiss` は distinct 数から GPU cache、peer/helper 所有分などを除き、tail-skip 分も差し引いた値です（`engine/src/core/expert_source.cpp:5491-5500,5519-5525,5533-5542`）。

ファイルを開けない場合も警告・エラー出力やプロセス終了はなく、書き込み戻り値も検査しません（`engine/src/core/expert_source.cpp:5531-5542`）。この変数による計算結果や生成 token の変更はコード上ありません。

## ログと測定値

ログ出力ではなく、指定ファイルへのテキスト記録です。1 行の書き込みは `fprintf` と改行の `fputc` で行われます。失敗時の Strata ログはありません。Strata の `docs/DETAILS.md` が説明している `--dump-routing` は別形式の routing trace であり、本変数の記録形式や挙動の根拠にはしていません（`docs/DETAILS.md:84-87,364-368`; `engine/src/program/generate.cpp:1608-1626`）。この変数に関する測定値はありません。

## 根拠

- `engine/src/core/expert_source.cpp:5426-5449,5479` — 関数入口、window 範囲、plan/capacity 条件。
- `engine/src/core/expert_source.cpp:5491-5500,5519-5542` — miss と skip の判定、出力列、ファイル書き込み。
- `engine/src/program/generate.cpp:1631-1636,14886,24547-24549` — multi dispatch の呼び出しと generate 経路での plan sink 設定。
- `engine/cmake/strata_gpu_engine.cmake:305-316` — CUDA/HIP 共通 GPU engine への組み込み。
- `engine/src/program/generate.cpp:1608-1626,3898` — CLI `--dump-routing` は独立した binary routing trace。
- `docs/DETAILS.md:84-87,364-368` — 文書中の routing trace 説明との照合。
