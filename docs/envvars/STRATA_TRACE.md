# `STRATA_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata engine と同梱の vision ツールが、起動・prompt 処理・serve 処理などの状態や所要時間を stderr に記録する診断スイッチ。engine の選択や通常処理は主に変えず、CUDA/HIP engine のメモリ記録では値が `2` で始まる場合に限り追加の GPU 同期とエラー状態の記録を行う。SYCL engine にはこの追加同期はない。vision tool は追加の F16 数え上げも行う。主な実装は `engine/src/program/generate.cpp`、`engine/src/prefill/prefill.cpp`、SYCL 版の同名ファイル、および `terminal/tools/vision/own/vit_gpu.cu` にある（例: `engine/src/program/generate.cpp:2218-2234`, `engine/sycl/src/program/generate.cpp:1363-1375`, `terminal/tools/vision/own/vit_gpu.cu:721-727, 952-954`）。

この名前を読むコードは複数の実行経路にある。serve loop では request の drain、prompt read、checkpoint、slot の貸し借りなどの時間・状態を記録し、prefill では prompt chunk と routed stream の ring entry 数を記録する（`engine/src/program/generate.cpp:16069-16078, 23728-23742`; `engine/src/prefill/prefill.cpp:4387-4395, 7735-7740`）。これらの診断出力は CLI 引数で有効・無効を切り替える実装ではない。

起動時にも、GPU memory mark、KFD quiet の設定状態、ROCm kpack path、card node の CPU 配置、prompt buffer を loan しない判定、file tier の切替理由などを条件付きで記録する。HIP の launch probe が成功した場合の trace 行もある。probe が失敗した場合は `STRATA_TRACE` の有無によらず診断理由を出して終了コード 2 で終わる（`engine/src/program/generate.cpp:2200-2214, 3760-3767, 4352-4363, 4684-4693, 9554-9566, 12231-12243`）。

## 値と判定

engine のほとんどの読み取りは `getenv` の返り値が null かどうかだけを見る。したがって未設定なら無効、設定されていれば空文字を含めて有効であり、文字列の数値変換や真偽値 parse はしない。`0`、`false`、`no`、空文字も通常の診断を有効にする。例外は CUDA/HIP 共通 engine の `mem_mark` で、診断有効判定は同じく設定有無だが、追加同期は値の先頭文字だけを `'2'` と比較する（`engine/src/program/generate.cpp:2218-2234`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| engine の通常の trace 判定 | trace 出力なし | 空文字、`0`、`1`、`true`、その他すべての非 null 値 | なし（設定されていれば有効） |
| CUDA/HIP `mem_mark` の追加同期 | trace なし、同期なし | `2`、`2anything` など先頭が `2` の値 | 空文字、`0`、`1`、` 2` など先頭が `2` 以外の値。VRAM 空き量の trace は出る |
| SYCL `mem_mark` | VRAM trace なし | 空文字を含むすべての設定値 | なし（設定されていれば有効）。`2` 固有の同期分岐はない |

文字列全体の検証、大文字小文字の扱い、空白除去、数値範囲検査は行わない。CLI・設定ファイル・他の環境変数より優先する値の選択処理もなく、ここでの判定は設定有無または `mem_mark` の先頭文字判定のみ。

## 有効になる条件

- 対象の Strata engine build に該当する診断コードが含まれ、そのコード経路が実行されること。共通 engine の `mem_mark` は CUDA/HIP 側、別実装は SYCL 側にあり、両者で追加同期の有無が異なる（`engine/src/program/generate.cpp:2218-2234`; `engine/sycl/src/program/generate.cpp:1363-1375`）。
- request の timing 行は serve loop の処理を通った場合に出る。prompt chunk / routed stream の行はそれぞれ該当する prefill 経路が使われた場合に限られる（`engine/src/program/generate.cpp:16069-16078`; `engine/src/prefill/prefill.cpp:4387-4395, 7735-7740`; `engine/sycl/src/prefill/prefill.cpp:2826-2829`）。
- KFD quiet の arena 登録、load order、signal handler、staged copy に関する trace は Linux HIP build の条件付きコード内にあり、該当する KFD quiet 分岐が成立した場合だけ出る（`engine/src/program/generate.cpp:3750-3762, 4346-4364, 16341-16344`）。
- SYCL prefill の Battlemage grouped projection 行は `fp16_group` が使われる場合だけ、expert window fallback の理由行は fallback がまだ記録されておらず、window mode が enabled か `STRATA_TRACE` が設定されている場合に出る（`engine/sycl/src/prefill/prefill.cpp:4931-4937, 5945-5954`）。
- 同梱 vision ツールでは GPU vision model の読込時に設定有無を `m.trace` に保存する。BF16 matrix を F16 へ扱う経路で、行列の F16 表現に関する数え上げと stderr の `vit-f16 trace:` 行が有効になる（`terminal/tools/vision/own/vit_gpu.cu:721-727, 952-954, 1014-1018`）。
- CLI オプションや他の環境変数が `STRATA_TRACE` 自体を無効化・上書きする処理は確認できなかった。個々のログには上記の実行経路・追加条件がある。

## 実行時の詳細

読み取りの時期はコード経路ごとに異なる。`engine/src/program/generate.cpp` の通常の分岐や CUDA/HIP trace 出力の多くは各箇所で `getenv` を評価する。一方、CUDA/HIP `mem_mark` は初回呼出し時に環境文字列へのポインタを関数内 static に保存し、後続の各マークでそれを使う。値が `2` で始まる場合、各 `mem_mark` は空き VRAM を記録した後 `cudaDeviceSynchronize` と `cudaGetLastError` を呼び、`ok` / `ERROR` と両 API のエラー文字列を出すが、結果で Strata の処理を中止・失敗扱いにはしない（`engine/src/program/generate.cpp:2218-2234`; 呼出し例: `6036-6036, 6058-6058, 7765-7765, 9047-9047, 10589-10590`）。

SYCL の `mem_mark` は初回呼出し時に設定有無を static bool に保存し、以後はその値で VRAM 空き量を記録する。serve loop の `trace` と checkpoint の `ckpt_trace` も各処理のセットアップ時に bool として読み取られ、その serve 処理中の複数ログで共有される（`engine/sycl/src/program/generate.cpp:1363-1375`; `engine/src/program/generate.cpp:14579-14585, 16069-16078`）。vision tool はモデル初期化時に `m.trace` へ保存する（`terminal/tools/vision/own/vit_gpu.cu:952-954`）。Strata 内でこの環境変数を書き換える処理は見つからなかった。よって通常はプロセス起動前に設定する。実行中に環境を書き換える仕組みが外部から使われる場合でも、static/local に保存済みの判定には反映されない一方、その都度 `getenv` する箇所は次回評価時に読む。

trace が出ない場合でも同じ状態・計算を進める診断分岐が大半である。例外として CUDA/HIP の `mem_mark` で値が `2` から始まると同期を挿入するため、診断に追加待ち時間が入り、遅延していた GPU エラーをそのマークで観測できる。Strata はその結果をログに記すだけで、この分岐から終了・失敗経路へは移らない（`engine/src/program/generate.cpp:2225-2234`）。

## ログと測定値

出力先は stderr。代表的な実装文字列は次のとおり。

- CUDA/HIP startup memory trace: `strata trace: %lld MiB free after %s`。値が `2` で始まると続けて `strata trace: device %s after %s (sync: %s, last error: %s)` を出す（`engine/src/program/generate.cpp:2220-2233`）。
- prompt 処理: `strata trace: prompt chunk ...`、`strata trace: routed stream: ... ring entries copied, ... dropped ...`（`engine/src/prefill/prefill.cpp:4387-4395, 7735-7740`; SYCL の chunk 行は `engine/sycl/src/prefill/prefill.cpp:2826-2829`）。
- serve timing: `strata trace: %s %lld %lld %.1f ms`。checkpoint や batch admission では sync/save/evict や各 phase の時間を別の `strata trace:` 行に出す（`engine/src/program/generate.cpp:16069-16078, 14663-14707, 23728-23742`）。
- vision BF16/F16 count: `vit-f16 trace: ...`（`terminal/tools/vision/own/vit_gpu.cu:1014-1018`）。

`docs/DETAILS.md:1322-1330` は routed stream の chunk ごとの copied/dropped ring entry を `STRATA_TRACE=1` で記録すると説明しており、実装の presence 判定とログ内容に一致する。ここに記載した調査では新たな性能測定をしていない。

## 根拠

- `engine/src/program/generate.cpp:2218-2234` — CUDA/HIP `mem_mark` の設定有無、値先頭 `2` の同期とログ。
- `engine/src/program/generate.cpp:14579-14585, 16069-16078, 18419-18431, 23728-23742` — checkpoint・serve timing の読み取りと trace 出力。
- `engine/src/program/generate.cpp:3750-3767, 4346-4364, 4684-4693, 9554-9566, 12231-12243, 16341-16344` — 条件付き KFD quiet、card node、file tier、prompt buffer などの診断出力。
- `engine/src/prefill/prefill.cpp:4387-4395, 7735-7740` — prompt chunk と routed stream trace。
- `engine/sycl/src/program/generate.cpp:1363-1375, 9461-9467` — SYCL VRAM mark と request trace。
- `engine/sycl/src/prefill/prefill.cpp:2826-2829, 4931-4937, 5891-5899, 5945-5954` — SYCL prompt・Battlemage・expert window 診断。
- `terminal/tools/vision/own/vit_gpu.cu:721-727, 952-954, 1014-1018` — vision tool の設定読取と F16 count trace。
