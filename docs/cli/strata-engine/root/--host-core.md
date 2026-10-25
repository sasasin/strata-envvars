# `--host-core`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--host-core` |
| 別名 | なし |
| 値 | `first`、`last`。通常版では `sibling` も指定可。値は大文字小文字を区別する文字列。 |

## 役割

CPU expert pool が予約する host thread 用 CPU を選びます。通常は最初の物理コアを host に予約します。`last` は対応する非 hybrid CPU で最後の物理コアを host に回し、`sibling` は通常版で最初の物理コアの SMT sibling に host を移します。worker の割り当てもこの topology に合わせて変わります。これはスレッド配置を制御する設定で、ソースは「結果ではなくスレッドだけを移動する」と説明しています（`src/program/generate.cpp:1032-1038`; `src/kernels/cpu/pool.cpp:194-212`）。

## 使い方

```sh
strata generate --native MODEL.gguf --host-core last --serve
```

通常版で SMT sibling を選ぶ例:

```sh
strata generate --native MODEL.gguf --host-core sibling --serve
```

`--native` は位置引数ではなく、モデルパスを取るエンジン引数です（`src/program/generate.cpp:808-812,2423-2426`）。

## 値と既定値

- 通常版 parser は `first`、`last`、`sibling` のみ受理します。既定は `first` です（`src/program/generate.cpp:525-526,2521-2527`; `src/kernels/cpu/pool.cpp:78-83`）。
- SYCL 版 parser は `first` と `last` のみを受理し、`sibling` は受理しません（`sycl/src/program/generate.cpp:504-505,1853-1858`）。
- 値を省略すると `--host-core needs a value` を stderr に出して終了コード 2 で終了します。未知の値も stderr にエラーを出し終了コード 2 です。通常版の文言は `expected first, last or sibling`、SYCL 版は `expected first or last` です（通常版: `src/program/generate.cpp:2416-2420,2521-2527`; SYCL 版: `sycl/src/program/generate.cpp:1853-1858`）。
- 同じオプションを複数回指定した場合、parser は各値を順に検証して `o.host_core` を更新するため、全て有効なら最後の値が使われます。途中の不正値はその場で終了します（`src/program/generate.cpp:2416-2422,2521-2527`; `sycl/src/program/generate.cpp:1853-1858`）。

## 実行時の動作

起動時、通常版と SYCL 版のどちらも pool/session が thread を pin する前に設定を決めます。CLI 値が空の場合のみ `STRATA_HOST_CORE` を読み、`last` または（通常版のみ）`sibling` と完全一致する場合に設定を切り替えます。CLI 値が指定されていれば環境変数より優先します。環境変数に未知の値を指定しても CLI のような validation error は出ず、既定の `First` が保たれます（通常版: `src/program/generate.cpp:2893-2899`; SYCL 版: `sycl/src/program/generate.cpp:2083-2088`; 初期値: `src/kernels/cpu/pool.cpp:78-83`）。

`last` は topology が非 hybrid で、host と worker の CPU が検出されているとき、worker list の末尾を host に移し、元の host を worker list の先頭に移します。hybrid CPU、worker がない場合、または host が未検出の場合はこの入れ替えをしません（`src/kernels/cpu/pool.cpp:194-203`）。

通常版の `sibling` は検出可能な SMT sibling がある場合、host をその論理 CPU に移し、同じ sibling を worker list から除きます。SMT sibling を検出できない場合は切り替わりません。この分岐は hybrid CPU を除外する条件を持たないため、通常版では hybrid CPU でも適用対象になり得ます（`src/kernels/cpu/pool.cpp:204-210,518-524,558-565`）。SYCL 版 parser ではこの値を指定できません。

最終的に session の host thread は `planned_host_core()` の CPU に pin され、pool worker は worker core に pin されます。pinning が失敗した場合、host/worker affinity のエラーを stderr に出し、以前の affinity を保ちます。session teardown では caller の affinity を戻します（host: `src/core/session.cpp:555-576,579-580`; pin/restore 実装: `src/kernels/cpu/pool.cpp:644-684`; worker: `src/kernels/cpu/pool.cpp:580-590,930`）。pool の affinity や worker 数など他の設定も pool 構成に関与します。起動時ログは host の論理 CPU、worker の論理 CPU と選択名を stderr に出します（`src/program/generate.cpp:5991-6010`; SYCL 版: `sycl/src/program/generate.cpp:4464-4475`）。

## 適用条件と副作用

- `--pool-affinity` 等で選ばれる worker topology と予約 CPU に影響します。`last` は hybrid CPU で入れ替わらず、通常版 `sibling` は SMT sibling の検出が必要です（`src/kernels/cpu/pool.cpp:194-212,518-569`）。
- Strata は thread affinity を設定します。`SessionLoopScratch` は host thread を pin し、`ExpertPool` は worker thread を割り当て先 CPU に pin します（`src/core/session.cpp:555-576`; `src/kernels/cpu/pool.cpp:580-590,930`）。この pinning が OS や実行環境で成功するかは実機確認していません。
- `STRATA_HOST_CORE` も同じ起動時設定源です。環境変数文書 [`STRATA_HOST_CORE`](../../../STRATA_HOST_CORE.md) は別 revision（`7695859aa13afb248bdb4d36f9b2e95707db079d`）を対象とする参考資料であり、本書の仕様根拠には使用していません。
- `STRATA_HOST_CORE` はプロセス起動時に一度だけ読まれます。起動後の環境変更で配置を更新する処理は確認できません（`src/program/generate.cpp:2893-2899`; `sycl/src/program/generate.cpp:2083-2088`）。

## 出力とエラー

通常版/SYCL 版で受理されない値は `strata generate: unknown --host-core value ...` を stderr に出し、終了コード 2 を返します。値なしも stderr と終了コード 2 になります（`src/program/generate.cpp:2418-2420,2521-2527`; `sycl/src/program/generate.cpp:1853-1858`）。

別経路として、Qwen35 モデルは build 条件により `src/qwen35` の parser に委譲されます。その parser に `--host-core` の処理はなく、通常の非 serve 呼び出しでは未知引数として usage を stderr に出して終了コード 2 になります。serve mode では未知の `--...` 引数を警告付きで無視し、次の値引数も読み飛ばします（`src/program/generate.cpp:2393-2408`; `src/qwen35/q36_engine.cu:3742-3747,3782-3795`）。したがってこの委譲経路で `--host-core` が host thread 配置を変えるとは確認できません。

## 根拠

- 通常版の option 宣言、help、parser、環境変数処理: `src/program/generate.cpp:525-526,1032-1038,2416-2422,2521-2527,2893-2899`
- SYCL 版の値範囲、parser、環境変数処理、配置ログ: `sycl/src/program/generate.cpp:504-505,931-935,1853-1858,2083-2088,4464-4475`
- 既定値、topology の切り替え、sibling 判定: `src/kernels/cpu/pool.cpp:78-83,194-212,518-569`
- host thread の pinning と復帰: `src/core/session.cpp:555-580`; affinity の実装と worker pinning: `src/kernels/cpu/pool.cpp:580-590,644-684,930`
- Qwen35 への委譲とその parser: `src/program/generate.cpp:2393-2408`; `src/qwen35/q36_engine.cu:3742-3795`
