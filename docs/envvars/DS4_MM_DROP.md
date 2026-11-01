# `DS4_MM_DROP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek V4.1 の IQ expert down 行列積 dispatch で、選択した引数バッファを 64 MiB のダミーバッファへ差し替えます。値の内容を通常の設定値として解釈するものではなく、down 計算へ渡すバッファを意図的に置き換える経路です。`iq_set_dn` から呼ばれる down 経路だけが対象で、gate/up 計算には適用されません。

## 値と判定

`mm_set()` は `DS4_MM_DROP` の設定有無を `getenv()` で判定し、設定されていれば値をもう一度読みます。数値変換や文字列全体の parse はせず、値の中に各文字が含まれるかを `strchr()` で調べます。

| `DS4_MM_DROP` | 動作 |
|---|---|
| 未設定 | 引数バッファを差し替えない。 |
| 空文字 | down 経路で2個のダミーバッファを用意するが、選択文字がないので引数は差し替えない。 |
| `0`〜`3` のいずれかを含む文字列 | 文字に対応する引数を差し替える。複数の数字を含めば該当する複数引数を差し替える。 |
| それ以外の文字列 | down 経路でダミーバッファを用意するが、引数は差し替えない。 |

文字の位置、重複、空白、大文字小文字、文字列の他の部分は検証しません。たとえば `x2x` は引数2を選び、`10` は引数0と1を選びます。

差し替え対象は dispatch の引数番号 0〜3 です。

| 番号 | down kernel の引数 | 元の Strata バッファ |
|---:|---|---|
| 0 | 重み `W` | expert 重みバッファ |
| 1 | 出力 `YEH` | `g_mm_ys` |
| 2 | 入力 `HS` | `g_mm_hs` |
| 3 | tile 一覧 | `bt` に格納した tile 一覧 |

`DS4_MM_D2` も設定され、その `atoi()` の結果が選択中の番号 `k` と一致する場合、その番号には2個目のダミーバッファを使います。それ以外は1個目を使います。`DS4_MM_D2` は文字列全体の検証をせず `atoi()` で変換するため、数値の後ろの文字は無視され、数値に変換できない文字列は 0 になります。したがって `DS4_MM_D2=2junk` は番号2に一致し、空文字や非数値文字列は番号0に一致します。`DS4_MM_D2` 単独ではこの差し替え経路を有効にしません。

## 有効になる条件

この分岐へ到達するには、次の条件が必要です。

- `STRATA_METAL` を定義した Metal engine の build である。CMake は `metal/src/engine/ds4_finish.cpp` を `strata_ds4` のソースとして含め、Metal 以外の CUDA/HIP/SYCL build はこの実装を使わない。
- DeepSeek V4.1 の IQ expert down 処理で `set_down()` が呼ばれ、`a.hbounds != nullptr` である。
- `mm_set(false, ...)` の早期判定を通る。具体的には `n_exp` と `total_rows` が正、両 expert type が `iq_bs()` の対応 type、`n_embd` と `n_ff` が 256 の倍数、down の stride 条件が成立し、Metal kernel library の準備に成功する必要がある。
- `mm_set()` が down 処理を行う段階で `DS4_MM_DROP` が設定されている。

これらの条件に届かないとき、`DS4_MM_DROP` の分岐は評価されません。`mm_set()` が `false` を返す条件では `set_down()` は通常の TQ または IQ kernel 経路へ進みます。Metal の GPU dispatch が失敗したときの処理はこの変数による分岐としては定義されていません。

## 実行時の詳細

環境変数は down の `mm_set()` 呼び出しごとに読みます。`static` cache はなく、プロセス起動後に環境が変更されれば以降の呼び出しはその値を参照します。分岐に入ると、1個目・2個目の `mtl::Buffer` をそれぞれ `1 << 26` byte で static に遅延確保し、以後の呼び出しで再利用します。選択したバッファ番号について、`DS4_MM_D2` の変換結果と番号が一致すると2個目、それ以外は1個目の buffer を `d.args[k]` に設定します。

kernel は番号0で重み、1で down 出力先、2で gate/up 結果、3で tile 情報を受け取ります。差し替え後も `DS4_MM_NODN` による早期 return がなければ `g_cx->run({d})` を呼び、down 経路では続けて `g_mm_ys` の内容を engine の出力行へコピーします。そのため、選択した引数が通常バッファではなくなった状態で計算が進みます。Strata のコードはこの変更に伴う出力の正しさを保証する処理を設けていません。

この分岐自体はログを出しません。ダミーバッファ確保に失敗すると Metal runtime は stderr に `mtl: alloc 67108864 failed` を出して終了コード 4 で終了します。別の down debug 変数 `DS4_MM_DBG` が設定されていれば、後続の引数ログに差し替え後の buffer サイズや pointer などを出します。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2484,2606-2618` — 入力条件、設定有無、文字による選択、dummy buffer 差し替え、dispatch の実行。
- `metal/src/engine/ds4_finish.cpp:2619-2633` — down dispatch 後に `g_mm_ys` から engine 出力へコピーする経路。
- `metal/src/engine/ds4_finish.cpp:2637-2643` — gate/up と down の公開 wrapper。`iq_set_dn` のみ `mm_set(false, ...)` を呼ぶ。
- `src/dsv41/ds4_iq.cu:1604-1619` — Metal で bounds がある場合に wrapper を呼び、失敗時は通常の down kernel 経路に進む。
- `metal/src/engine/msl/ds4_mm.metal:88-102` — down kernel の引数番号と、重み・出力・入力・tile 一覧の対応。
- `metal/CMakeLists.txt:132-171` — Apple/Metal 固有 build、`STRATA_METAL` 定義、および `strata_ds4` のソース構成。
- `metal/src/mtl_rt.mm:547-566` — runtime buffer 確保。失敗時の stderr 文言と終了コード4。
