# `STRATA_PREFILL_WARM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は prefill の二つの warm-up 経路に使われる。GPU の GEMM ライブラリ warm-up は CUDA/HIP build の生成開始時（Metal ではない）に BF16 と FP16 の小さな GEMM を実行し、初回 prompt に乗るライブラリ初期化を先に行う。もう一つは、対応するファイル expert source を使う短い prefill chunk で、ルーティング済み expert のファイルページを別 thread から先読みする機能である。前者は主に `0` で停止し、後者は `atoi` の非ゼロで開始するため、同じ文字列判定ではない。warm-up は scratch 出力またはページ先読みを行うもので、モデルの expert 選択や stager がコピーするデータを変えない（`engine/src/prefill/prefill.cpp:2375-2380, 2425-2429`、`engine/include/strata/core/expert_source.hpp:300-311`）。

## 値と判定

| 経路 / build | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| GEMM warm-up / CUDA | 実行する | 空文字、`1`、`true`、その他先頭文字が `0` 以外 | 先頭文字が `0`（`0`、`0anything`、`00` など） |
| GEMM warm-up / HIP | 同一 architecture（または device 列挙失敗）の場合に実行 | 先頭文字 `1` は architecture にかかわらず実行。先頭文字 `0` は停止 | 先頭文字 `0`。それ以外は architecture が異なると停止 |
| file-tier ページ warm-up | 実行しない | `std::atoi` の結果が非ゼロ（例 `1`, `01`, `-1`, ` 1`, `1tail`） | 空文字、`0`, `0tail`, `true` など `atoi` が 0 を返す値 |

GEMM 経路は `std::getenv` の結果について `e[0] == '0'` を調べる。文字列全体の parse ではなく、大文字小文字・後続文字・数値としての妥当性は検査しない。HIP の architecture policy は先頭文字 `0` と `1` のみを明示 override とし、空文字を含むその他の値は未指定と同じ architecture 判定に進む（`engine/src/prefill/prefill.cpp:2381-2402`、`engine/include/strata/prefill/warm_policy.hpp:17-27`）。CUDA build にはこの HIP architecture policy がなく、先頭文字 `0` 以外は warm-up を許可する。たとえば `01` は CUDA/HIP の GEMM warm-up を止める一方、ページ warm-up では `atoi("01") == 1` となり有効である。

ページ warm-up 経路は `std::atoi(wv) != 0` で判定するため、C `atoi` が読み取る先頭の整数部分だけが使われる。空文字や整数で始まらない値は 0、先頭空白や符号は許され、非ゼロの負数も有効扱いになる。両経路とも値の範囲を独自に clamp しない（`engine/src/prefill/prefill.cpp:2558-2565`）。

## 有効になる条件

- GEMM warm-up は CUDA/HIP の生成経路で GPU が特定できた場合に呼び出される。HIP は `STRATA_USE_HIP` build のみ architecture を列挙して判定する。空の device 一覧は policy 上 warm-up を許可し、device 列挙 API の失敗も `arch_ok` の初期化処理では許可側へ進む。Metal/SYCL 経路からこの GEMM warm-up の呼び出しは確認できない（`engine/src/program/generate.cpp:8498-8524, 8565-8585`、`engine/src/prefill/prefill.cpp:2384-2402`）。
- HIP では、未設定または先頭文字が `0`/`1` 以外の値の場合、列挙した最大 32 個の見える GPU の `gcnArchName` から `:` 以降を除いた architecture がすべて一致すると warm-up する。異なる architecture が一つでもあればしない。`1...` は混在時も強制し、`0...` は同一 architecture でも停止する。device 数の取得に失敗したときは policy 上 warm-up を許可する（`engine/src/prefill/prefill.cpp:2387-2400`、`engine/include/strata/prefill/warm_policy.hpp:19-27`）。
- ページ warm-up は `Prefill::init` 時点で `src != nullptr && src->warms()` かつ `atoi(value) != 0` の場合に worker を作る。`FileExpertSource::warms()` は role mapping があるか `io_pf_` が有効で、かつ unbuffered `direct_` source でない場合に true を返す。`RemoteExpertSource` はこの `warm` / `warms` を fallback source に転送する。該当しない source、direct I/O source、未設定・空文字・atoi が 0 の値では worker を作らない（`engine/src/prefill/prefill.cpp:2558-2565`、`engine/include/strata/core/expert_source.hpp:992-1001`、`engine/include/strata/core/remote_experts.hpp:160-166`）。
- worker のページ先読みは `stream_all` でない staged walk 内に限られる。`stream_all` は `m.ring > STAGE && T >= stream_all_min() && m.src != nullptr` のとき true なので、通常の該当 file source では chunk が `stream_all_min()` 未満の staged 経路で先読み候補が送られる（`engine/src/prefill/prefill.cpp:4625-4629, 7019-7051`）。

## 実行時の詳細

GEMM warm-up は `warm_gemm_libraries` 内の function-local `static` で停止値を初回に cache する。HIP の architecture 判定も `static const bool` で初回に一度だけ行う。`generate.cpp` は arena 読み込み前に起動し、Linux HIP と CUDA では別 thread、Windows HIP では同期実行する。必要な経路では VRAM 空き容量を測る前に thread を join する。さらに `Prefill::init` からも呼び出されるが、device ごとの `done_mask` は GPU 操作より前に立つため、後続呼び出しはその device を再試行しない。実行中の環境変更は GEMM 側の static 判定に反映されない（`engine/src/prefill/prefill.cpp:2381-2409, 2443-2445, 2753-2755`、`engine/src/program/generate.cpp:8515-8524, 8577-8585, 9077-9080`）。

GEMM 側は専用 stream と一時 GPU buffer を用意し、BF16/FP16 GEMM を一度ずつ呼んで同期し、buffer と stream を解放する。出力は scratch なので後続の計算値には使わない。資源確保や `Gemm::init` に失敗した場合、関数は成功ログを出さずに戻る。`done_mask` は処理前に設定されるため、その device の再試行はしない（`engine/src/prefill/prefill.cpp:2404-2440`）。

ページ warm-up 側は `Prefill::init` で `warmer` が未作成の場合に値を読み、worker と層ごとの `warm_prev` を初期化する。その後 staged walk で現在層の routed な非 resident / 非 pinned expert を worker に送り、前の chunk で記録した次層候補も送る。queue は最大 4 job で、満杯時は古い job を落とす。worker は `src->warm` を呼び、完了時に終了する（`engine/src/prefill/prefill.cpp:1494-1527, 1529-1540, 2558-2565, 7020-7051`）。

`FileExpertSource::warm` は RAM copy にある expert を飛ばし、それ以外の対象を warm stamp に記録する。`io_pf_`、buffered source、open gate の条件を満たすと I/O read-ahead queue に enqueue し、そうでなく mapped roles が使える場合は Windows で `PrefetchVirtualMemory`、他 OS で `madvise(MADV_WILLNEED)` を要求する。これは Strata が行う先読み要求の範囲であり、OS がどの程度実際にページを常駐させるかはここでは保証されない（`engine/src/core/expert_source.cpp:3467-3505`）。

## ログと測定値

- GEMM warm-up 成功時: `strata prefill: warmed the BF16 and FP16 GEMM libraries on GPU %d in %.0f ms (STRATA_PREFILL_WARM=0 skips)`。`ok` の場合だけ出る（`engine/src/prefill/prefill.cpp:2438-2440`）。
- HIP architecture policy が warm-up を止める場合: `strata prefill: no hipBLAS warm-up: the cards are of more than one architecture (it slows prompts there, #3204); the first prompt loads the libraries (STRATA_PREFILL_WARM=1 asks for it)`。ただし実装は明示 `0` による停止でも同じ文言を出す（`engine/src/prefill/prefill.cpp:2396-2400`）。先頭 `0` による GEMM の早期停止はこのログより前に return するのでログなし（同 `2381-2384`）。
- file-tier worker 作成時: `prefill: STRATA_PREFILL_WARM=1: the per-layer walk warms this layer's and the next layer's file-tier experts`。値が非ゼロでも source 条件を満たさず worker を作らない場合は出ない（同 `2558-2565`）。
- `docs/release-notes-0.2.1.md:48` は mixed-architecture HIP での測定と `0`/`1` override を記す。これは資料の記載であり、現 checkout で再測定していない。コード上の現行条件は `warm_policy.hpp:19-27` を参照。

## 根拠

- `engine/include/strata/prefill/warm_policy.hpp:17-27` — HIP の override 値と architecture 判定。
- `engine/src/prefill/prefill.cpp:2375-2440` — GEMM warm-up の読み取り・cache・処理・ログ。
- `engine/src/program/generate.cpp:8500-8524, 8565-8585, 9077-9080` — GPU/build 起動経路、同期/非同期起動、VRAM 計測前 join。
- `engine/src/prefill/prefill.cpp:1490-1540, 2558-2565, 4625-4629, 7019-7051` — staged walk worker の作成と expert 候補送信。
- `engine/include/strata/core/expert_source.hpp:300-311, 992-1001`、`engine/include/strata/core/remote_experts.hpp:160-166`、`engine/src/core/expert_source.cpp:3467-3505` — source が warm 可能か、wrapper からの転送、および file source の先読み処理。
- `docs/release-notes-0.2.1.md:48` — HIP mixed-architecture に関する測定値の出典。
