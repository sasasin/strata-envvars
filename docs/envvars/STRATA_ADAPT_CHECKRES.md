# `STRATA_ADAPT_CHECKRES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の `strata serve` と `strata generate` で、host 側の expert residency table と device 側の table を window ごとに読み戻して比較する診断を有効にします。serve では直列 window のとき、generate では device table が存在するときに `res_check` を呼びます。値は診断用の read-back と不一致・stale 状態の集計を有効にするだけで、expert の実行先や生成計算を切り替えません（`engine/src/program/generate.cpp:15257-15262`, `24608-24614`; `engine/src/core/expert_source.cpp:5736-5745`）。

## 値と判定

両方の読み取り箇所で `std::getenv(...) != nullptr` のみを判定し、値の文字列や数値は変換しません。未設定だけが無効です。空文字も含め、何らかの値が設定されていれば有効になります（`engine/src/program/generate.cpp:15257-15260`, `24608-24612`）。

| 経路・追加条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata serve`: `serial_windows` が真（`!pipe && !piped_groups`） | 無効 | `1`, `0`, `true`, `false`, `0anything`, 空文字、空白など、値が存在するものすべて | なし（値の内容は検査しない） |
| `strata serve`: pipeline window または layer split での `--batch-groups` 並行実行 | 無効 | なし。この条件では設定値にかかわらず無効 | 設定済みでも無効 |
| `strata generate`: `d_res != nullptr` | 無効 | `1`, `0`, `true`, `false`, `0anything`, 空文字、空白など、値が存在するものすべて | なし（値の内容は検査しない） |
| `strata generate`: `d_res == nullptr` | 無効 | なし。この条件では設定値にかかわらず無効 | 設定済みでも無効 |

`0` や `false` も無効化指定にはなりません。大文字小文字、前後の空白、数値としての妥当性、文字列全体は調べません。CLI 引数や別の環境変数による上書き・優先順位もありません（同上）。

## 有効になる条件

- `strata serve` は `serial_windows = !pipe && !piped_groups` の場合に限って有効です。`pipe` は pipeline window が実際に構成された場合、`piped_groups` は `--batch` の batch groups が複数で stages もある場合です。どちらかが真なら、この診断用 hook は登録されません（`engine/src/program/generate.cpp:13267`, `15249-15262`, `15330-15332`）。
- `strata generate` は residency table の device pointer `d_res` が非 null のときに限って有効です。null なら環境変数が設定されていても診断用 hook と `dres_check` は設定されません（`engine/src/program/generate.cpp:24608-24614`, `24630-24631`）。
- 読み取り箇所に OS や明示的な build macro による追加判定はありません。該当箇所は CUDA API を使う CUDA/HIP engine の実装です。CPU-only の実行経路に対する読み取りはこのソース内で確認できません（`engine/src/program/generate.cpp:2360`, `15257`, `24608`）。
- serve / generate の引数解析で値を読むのではなく、各実行経路の table/hook 設定時に一度 bool にします。serve はサーバー実行中の各 request で読み直すコードではなく、generate も各 window では読み直しません。プロセス実行中に環境を変更しても、この bool には反映されません（`engine/src/program/generate.cpp:15257-15262`, `24608-24614`）。

## 実行時の詳細

有効なら host table と同じ要素数の `res_back` を確保し、その領域を `drive.d.dres_check` に設定します。serve は verifier の pre-launch hook から各 serial window の前に table 更新を同期した後、対象 device table を host 側へ読み戻して全要素を比較します。layer split の stages がある場合は各 stage の table と主 device の table を比較します。generate も pre-launch hook で各 window の前に device table を読み戻して比較します（`engine/src/program/generate.cpp:15257-15263`, `15272-15316`, `24608-24614`, `24630-24654`）。

`res_check` は `cudaMemcpy(..., cudaMemcpyDeviceToHost)` で `host_res.size()` 個の値を読み、host と device の各 entry を比較します。不一致ごとに合計を増やし、プロセス内で最初の 20 件まで `window`、`layer`、`expert`、host 値、device 値を stderr に出します。比較結果は集計とログにだけ使われ、戻り値の mismatch 数で verifier の成功・失敗や expert dispatch を変更しません（`engine/src/program/generate.cpp:2358-2376`; `engine/src/core/expert_source.cpp:5739-5745`）。

別に `ExpertDispatch` は、その層に CPU expert がある window で `dres_check` を参照します。window 内の routed id がすべて device table 上 resident に見える場合 `stale_x` を 1 増やし、最終集計で「CPU experts があるのに activation が publish されなかった layer-window 数」として報告します。この確認後も通常の `any_cpu` 処理へ続き、実行先は切り替えません（`engine/src/core/expert_source.cpp:5736-5747`; `engine/include/strata/core/expert_source.hpp:670-673`）。

## ログと測定値

- entry の不一致は stderr に `strata: res check: window ... layer ... expert ...: host ..., device ...` と出ます。各 process で最初の 20 件までです（`engine/src/program/generate.cpp:2364-2374`）。
- read-back に失敗すると stderr に `strata: res check: the read-back failed: ...` と出し、その呼び出しの mismatch 数は 0 として返ります。比較関数自体は失敗で終了させず、診断用 hook も成功を返して続行します（`engine/src/program/generate.cpp:2360-2363`, `24648-24654`）。
- serve は mismatch があった最初の 4 window と、256 window ごとに stderr へ `strata serve: res check: ...` の累計を出します。generate は実行終了時に stdout へ `residency check ...` の累計を出します（`engine/src/program/generate.cpp:15308-15316`, `25320-25323`）。
- この変数に関する条件付きの測定値は記載しません。ソースの read-back コメントに別の residency update の時間測定がありますが、この環境変数の診断自体を測定した値ではありません（`engine/src/program/generate.cpp:15264-15266`）。

## 根拠

- 環境変数の全読み取り箇所と有効化条件: `engine/src/program/generate.cpp:15249-15262`, `24608-24614`
- residency table の読み戻し・比較・ログ: `engine/src/program/generate.cpp:2356-2376`, `15300-15316`, `24648-24654`
- CPU expert がある window の stale 判定: `engine/src/core/expert_source.cpp:5736-5747`, `engine/include/strata/core/expert_source.hpp:670-673`
- serve の pipeline window 条件: `engine/src/program/generate.cpp:13267`, `15249-15250`
