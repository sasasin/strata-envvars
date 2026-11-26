# `STRATA_HOST_CORE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

生成エンジンの host thread（GPU の layer loop を進めるスレッド）に割り当てる論理 CPU を選びます。`last` は通常の先頭コアから最後の物理コアへ host を移し、先頭コアを worker pool に戻します。`sibling` は先頭物理コアの SMT sibling に host を移し、その論理 CPU を worker pool から外します。いずれもスレッド配置の変更で、計算結果を変える設定ではありません。CUDA/HIP 経路では `first|last|sibling`、SYCL 経路では `first|last` が扱われます（`engine/src/program/generate.cpp:4696-4702`、`engine/sycl/src/program/generate.cpp:2232-2237`、`engine/src/kernels/cpu/pool.cpp:249-267`）。

## 値と判定

エンジン初期化時、CLI の `o.host_core` が空の場合だけ `std::getenv("STRATA_HOST_CORE")` の値を文字列のまま取得し、完全一致で判定します。空白除去、大小文字変換、部分一致、数値変換はありません。未設定と空文字はどちらも設定を変えず、既定の `First` のままです。CLI に `--host-core first` を指定すると、環境変数より優先して `First` が選ばれます（`engine/src/program/generate.cpp:3947-3953,4696-4702`、`engine/sycl/src/program/generate.cpp:1977-1982,2232-2237`）。

| 経路 | 未設定 / 空文字 | 有効値 | 判定されない値 |
|---|---|---|---|
| CUDA/HIP (`engine/src/program/generate.cpp`) | `First` | `last`, `sibling`。`first` も既定値を明示する値として無操作 | `LAST`, ` last`, `last `, `true`, `1` などは無視され、警告なしで `First` |
| SYCL (`engine/sycl/src/program/generate.cpp`) | `First` | `last`。`first` は既定値を明示する値として無操作 | `sibling` を含むその他の値は無視され、警告なしで `First` |

既定値は `pool.cpp` の process-wide atomic `g_host_core` の初期値 `HostCore::First` です（`engine/src/kernels/cpu/pool.cpp:80-85`）。環境変数で有効なのはコードが小文字の `last` / `sibling` と完全一致した場合だけです。環境変数の無効値は CLI と異なりエラーになりません。CLI は CUDA/HIP で `first|last|sibling`、SYCL で `first|last` 以外をエラー終了コード 2 にします（同上 CLI parser の行）。

## 有効になる条件

- 起動した実行ファイルが該当する generate 経路に入り、設定ブロックまで進む必要があります。設定は pool と session がスレッドを pin する前に行われます（`engine/src/program/generate.cpp:4696-4702`、`engine/sycl/src/program/generate.cpp:2232-2237`）。
- `last` の配置変更は topology が hybrid ではなく、host と worker core が検出できる場合だけ適用されます。条件を満たさない hybrid CPU では `First` 相当の配置のままです（`engine/src/kernels/cpu/pool.cpp:249-258`）。
- `sibling` は検出された host core の SMT sibling がある場合だけ適用されます。sibling がない、または topology を取得できない場合は host core の変更がありません（`engine/src/kernels/cpu/pool.cpp:259-265`）。SYCL 経路は環境変数から `sibling` を設定しません（`engine/sycl/src/program/generate.cpp:2232-2237`）。
- macOS の topology 分岐は host core / sibling を埋めずに戻ります。その場合、session は設定値に基づく pin をせず fallback の `physical_cores(false)` を試しますが、この関数も同じ topology の空の worker 列を返すため、ここからは pin されません（`engine/src/kernels/cpu/pool.cpp:206-209,618-620`、`engine/src/core/session.cpp:558-566`）。
- host thread の pin に失敗しても生成を止めず、直前の affinity を保ちます。Windows は CPU Set 選択失敗、その他の実装は affinity 設定失敗を stderr に出します（`engine/src/kernels/cpu/pool.cpp:699-722`）。

## 実行時の詳細

CUDA/HIP と SYCL はそれぞれ generate 初期化時に一度環境を読み、`set_host_core` で process-wide atomic 設定を更新します。設定ブロック内に static cache はなく、起動後にプロセス環境を変更しても読み直されません。各リクエストごとの評価ではありません（`engine/src/program/generate.cpp:4696-4702`、`engine/sycl/src/program/generate.cpp:2232-2237`、`engine/src/kernels/cpu/pool.cpp:80-85`）。

pool の topology 検出では、`last` のとき先頭の予約 core を worker 列の先頭へ戻し、最後の worker core を host にします。`sibling` のとき sibling を worker 列から外し、その sibling を host core にします（`engine/src/kernels/cpu/pool.cpp:249-267`）。session 開始時に `planned_host_core()` の結果を取得して host thread を pin し、成功状態を保持します。host core が検出できない場合は physical core 列の先頭を試します（`engine/src/core/session.cpp:550-570`、SYCL は `engine/sycl/src/core/session.cpp:775-793`）。

## ログと測定値

pool の初期化後、stderr に `strata generate: N pool workers on logical processors ..., the host thread on ... (--host-core last|sibling|first)` の形式で worker / host の論理 CPU と設定値を出します（`engine/src/program/generate.cpp:9022-9036`、SYCL は `engine/sycl/src/program/generate.cpp:4810-4820`）。topology 条件により配置変更されない場合も括弧内は設定値を表示するため、host の実 CPU は `the host thread on ...` の番号で確認します。pin に失敗した場合は `strata cpu pool: host CPU Set selection for processor ... failed: ...; previous placement kept`（Windows）、または `strata cpu pool: host affinity for CPU ... failed: ...; previous affinity kept`（それ以外）が出ます（`engine/src/kernels/cpu/pool.cpp:699-722`）。環境変数の無効値自体に対するログはありません。

`docs/SETTINGS.md:112` はこの変数の値を `on / off` としていますが、現行ソースが受け取るのは `last` / `sibling`（または既定値を明示する `first`）です（`engine/src/program/generate.cpp:4696-4702`、`engine/sycl/src/program/generate.cpp:2232-2237`）。`docs/DETAILS.md:1283` は Windows の `last|sibling` と一台での測定を記載していますが、現行ソースでは topology 条件に応じて配置を選びます。記載された性能値については測定条件の詳細をこの実装から確認できないため、一般的な効果としては扱いません。

## 根拠

- 環境変数の読み取りと CLI 優先順位: `engine/src/program/generate.cpp:3947-3953,4696-4702`、`engine/sycl/src/program/generate.cpp:1977-1982,2232-2237`
- 既定値と topology 変更: `engine/src/kernels/cpu/pool.cpp:80-85,249-267`
- topology が得られない場合と host pin: `engine/src/kernels/cpu/pool.cpp:206-209,699-722`、`engine/src/core/session.cpp:550-570`、`engine/sycl/src/core/session.cpp:775-793`
- 配置ログ: `engine/src/program/generate.cpp:9022-9036`、`engine/sycl/src/program/generate.cpp:4810-4820`
