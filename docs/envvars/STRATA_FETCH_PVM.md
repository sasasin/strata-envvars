# `STRATA_FETCH_PVM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows の `FileExpertSource::fill_many` が、ファイル mapping から stage buffer へ読み出す前に呼ぶ `PrefetchVirtualMemory` を止めるための切り替えである。`0` と判定される値では当該バッチのページ先読みを行わず、その後の `fill_stage` による読み出しは続く。`PrefetchVirtualMemory` が利用可能な Windows では、既定では関数を動的に取得して先読みを試みる（`engine/src/core/expert_source.cpp:2692-2751`、`engine/sycl/src/core/expert_source.cpp:979-1034`）。

この変数は `warm()` が行う別の先読みを制御しない。CUDA/HIP と SYCL の `warm()` は独自に `GetProcAddress` した関数ポインターから PVM を呼ぶ（`engine/src/core/expert_source.cpp:3467-3505`、`engine/sycl/src/core/expert_source.cpp:1408-1441`）。

## 値と判定

各実装は `std::getenv` で値を取り、未設定でなければ `std::atoi` の結果が `0` かを判定する。文字列全体の検証や許容範囲の検査はない。

| ビルド・経路 | unset | 設定時に先読みを行う値 | 設定時に先読みを止める値 |
|---|---|---|---|
| Windows、CUDA/HIP または SYCL の buffered mapping `fill_many` | `PrefetchVirtualMemory` を動的取得して使用を試みる | `atoi` が非 0。例: `1`、`-1`、`1abc` | `atoi` が 0。例: `0`、`-0`、空文字、`true`、`0anything` |
| Windows 以外 | この変数を読むコードがなく、当該 PVM 分岐もコンパイルされない | 該当なし | 該当なし |

`atoi` は先頭の空白と符号を許し、数値として読める先頭部分だけを変換するため、`1abc` は非 0、`0anything` は 0 になる。先頭が数値でない文字列（`true` など）と空文字は 0 になる。大文字小文字の扱いを比較する処理はない。数値の妥当性や後続文字は検査されず、境界値への clamp もない（`engine/src/core/expert_source.cpp:2727-2730`、`engine/sycl/src/core/expert_source.cpp:1012-1015`）。

## 有効になる条件

- Windows 用ビルドであること。読み取りと PVM 呼び出しは `#if defined(_WIN32)` 内にある。CUDA/HIP 側と SYCL 側に同じ判定がある（`engine/src/core/expert_source.cpp:2721-2744`、`engine/sycl/src/core/expert_source.cpp:1006-1029`）。
- `fill_many` に空でない `todo` が渡されること。空なら環境変数を読む前に戻る（同 `expert_source.cpp:2692-2693`、`engine/sycl/src/core/expert_source.cpp:979-980`）。
- unbuffered direct 読み出しではないこと。`direct_` が空でない場合は direct batch 読み出しを行って return するため、この変数は読まれない（`engine/src/core/expert_source.cpp:2694-2719`、`engine/sycl/src/core/expert_source.cpp:981-1005`）。
- `atoi` が 0 でない場合でも、`GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "PrefetchVirtualMemory")` が null なら PVM 呼び出しは行われない（`engine/src/core/expert_source.cpp:2727-2732`、`engine/sycl/src/core/expert_source.cpp:1012-1017`）。
- CLI 引数や別の環境変数による上書きは、この読み取り箇所にはない。モデルの読み出し方式や上記の経路条件によって、値を読む場面自体がない場合がある。

## 実行時の詳細

`fill_many` は `todo` の各 `Fill` について role 3 個の範囲を作り、1 回の PVM 呼び出しにまとめる。その後、通常の worker thread 群が各要素を `fill_stage` へ渡してファイルから stage buffer を埋める（`engine/src/core/expert_source.cpp:2732-2757`、`engine/sycl/src/core/expert_source.cpp:1017-1040`）。この処理は `prefetch` から呼ばれ、CUDA/HIP 側では `prefetch_begin` の mode 4 経路からも `fill_many` に到達する（`engine/src/core/expert_source.cpp:2449-2477,2547-2573`、SYCL 側 `engine/sycl/src/core/expert_source.cpp:920-944`）。

環境変数の判定と関数ポインターの取得は、`fill_many` 内の関数ローカル `static` 初期化で行われる。したがって、空でない `todo` があり `direct_` が空の状態で初めて Windows 分岐に到達した時に一度だけ読み、以後の変更はそのプロセス内で反映されない。子プロセスへの設定転送や上書きはこのコードにない（`engine/src/core/expert_source.cpp:2725-2731`、`engine/sycl/src/core/expert_source.cpp:1010-1016`）。

## ログと測定値

この判定、PVM 関数が取得できない場合、および PVM の戻り値について専用のログやエラー処理はない。戻り値は破棄され、後続の `fill_stage` は実行される。コピーに失敗した場合は stage を失敗状態として公開し、待機側はその stage key が変わった場合に `nullptr` を返すが、これはこの環境変数固有の経路ではない（`engine/src/core/expert_source.cpp:2732-2751,2362-2384,2435-2446`、SYCL 側 `engine/sycl/src/core/expert_source.cpp:1017-1034,876-898`）。

`docs/DETAILS.md` にこの変数の説明や対応する測定値は見つからなかった。性能差は本調査では測定していない。

## 根拠

- `engine/src/core/expert_source.cpp:2721-2757` — CUDA/HIP 実装の Windows 条件、値判定、PVM 呼び出し、後続読み出し。
- `engine/sycl/src/core/expert_source.cpp:1006-1040` — SYCL 実装の同じ処理。
- `engine/src/core/expert_source.cpp:2449-2477,2547-2573` — CUDA/HIP 側から `fill_many` に到達する同期 prefetch 経路。
- `engine/sycl/src/core/expert_source.cpp:920-944` — SYCL 側の prefetch 呼び出し。
- `engine/src/core/expert_source.cpp:3467-3505`、`engine/sycl/src/core/expert_source.cpp:1408-1441` — 環境変数判定とは別に存在する `warm()` の PVM 経路。
- `engine/src/core/expert_source.cpp:2362-2384,2435-2446`、`engine/sycl/src/core/expert_source.cpp:876-898` — stage 読み出し失敗時の処理。
