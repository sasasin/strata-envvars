# `STRATA_STACK_ISOLATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows HIP の engine 起動時に、プロセス内の 1 TiB 未満の空き仮想アドレス領域を予約し、engine 本体を新しいスレッドで実行する分岐を無効化できます。この領域予約は GPU alias と engine の stack・後続の割当てが重なる可能性を避けるためのもので、GPU alias と重なる既存メモリがある場合は個別の pinned arena 範囲を登録しない処理もあります。`STRATA_STACK_ISOLATE` はその起動時の分岐だけを制御し、`0` を指定すると予約・スレッド分離を行わず、現在のスレッドで `engine_main` を呼びます。実装は `engine/src/program/generate.cpp` の `main` にあります（`engine/src/program/generate.cpp:25566-25574,25609-25625`）。

## 値と判定

`std::getenv` で一度取得し、ポインターが null か、値の先頭文字が `'0'` かだけを判定します。未設定または先頭文字が `'0'` でない値なら予約・新スレッド実行が有効です。文字列全体の parse や数値検査はなく、空白除去、大文字小文字変換もありません（`engine/src/program/generate.cpp:25609-25612`）。

| ビルド・実行条件 | unset | 設定時に有効（予約・分離） | 設定時に無効（現在のスレッドで実行） |
|---|---|---|---|
| `STRATA_USE_HIP` かつ `_WIN32` | 有効 | 先頭文字が `'0'` 以外。例: `1`, `true`, 空文字, ` 0` | 先頭文字が `'0'`。例: `0`, `00`, `0anything` |
| その他のビルド・OS | この `main` の分岐自体がコンパイルされず、変数を読まない | 該当なし | 該当なし |

空文字は `getenv` が null ではなく、`iso[0]` は終端文字 `\0` のため `'0'` と一致せず、有効側です。`false`、`0 `、` 0` も先頭が `'0'` でないため有効側です。`0anything` は後続を検査せず無効側です。したがって `0` / `1` のみを受け付ける厳密な flag ではありません（同上）。

## 有効になる条件

- 判定コードは `STRATA_USE_HIP` と `_WIN32` の両方が定義されたビルドに限られます。Linux HIP、CUDA、SYCL、Metal などではこの環境変数を読むこの分岐はありません（`engine/src/program/generate.cpp:25566,25609`）。
- CLI 引数、サーバーモード、モデルの状態、他の環境変数による上書き分岐はこの `main` にありません。判定は engine の引数処理 `engine_main` を呼ぶ前に行われます（`engine/src/program/generate.cpp:25610-25625`）。
- 予約・分離を有効にした場合も、`CreateThread` が失敗すると idle thread stack の記録をクリアして、現在のスレッドで `engine_main` を実行する fallback になります。失敗の明示的なログはありません（`engine/src/program/generate.cpp:25617-25625`）。
- 低位領域の各予約は `VirtualAlloc` の成功時だけ保持リストに加えられます。失敗した範囲を理由として出力する処理はこの予約ループにはありません（`engine/src/program/generate.cpp:25586-25606`）。

## 実行時の詳細

環境変数は Windows HIP の `main` に入った直後、一度だけ読みます。関数内 cache やリクエストごとの再読込はありません。したがって、起動後にプロセス内の環境を変更する処理があっても、この起動分岐には反映されません（`engine/src/program/generate.cpp:25609-25612`）。

有効側では、まず現在のスレッドの stack 範囲を記録し、`reserve_low_address_space(1ull << 40)` で 1 TiB 未満の空き領域を走査して `MEM_RESERVE` / `PAGE_NOACCESS` として予約します。続いて同じ実行引数・戻り値領域を渡して `engine_main` を新規スレッドで実行し、終了を無期限に待機してその戻り値を返します。予約ベースは sorted な保持リストに保存されます（`engine/src/program/generate.cpp:25586-25625`; `engine/src/core/pinned.cu:596-609`）。

Windows HIP の pinned arena 登録では `claim_alias` が GPU alias の範囲を調べ、起動時に保持した予約や待機中の最初のスレッドの stack を認識して扱います。alias 範囲にその他の使用中メモリが重なる、または alias の予約に失敗した場合、呼び出し元は範囲を unregister し、`strata pin: ...; that range stays unregistered (#3431)` を stderr に出します。この経路は環境変数を再読込せず、`0` を指定した場合でも pinned arena の alias 検査自体は残ります（`engine/src/core/pinned.cu:683-749,988-1008`）。

無効側ではアドレス予約も新スレッド生成もせず、`engine_main(argc, argv)` を直接呼びます（`engine/src/program/generate.cpp:25610-25625`）。

## ログと測定値

この環境変数の値や予約成否を直接表示するログはありません。別スレッド生成失敗時にもログはありません（`engine/src/program/generate.cpp:25609-25625`）。pinned arena の alias 判定で登録を拒否した場合は、前節記載の `strata pin: ...; that range stays unregistered (#3431)` が stderr に出ます（`engine/src/core/pinned.cu:998-1004`）。

`docs/AMD_HIP.md` は、低位 1 TiB 予約と `STRATA_STACK_ISOLATE=0` の効果を記述しており、コードの条件と一致します。同資料には過去の不具合の頻度・症状もありますが、ここでは現行コードによる再測定値として扱いません（`docs/AMD_HIP.md:151-158`）。

## 根拠

- `engine/src/program/generate.cpp:25566-25625` — Windows HIP 限定の起動分岐、値判定、予約、スレッド実行と fallback。
- `engine/src/core/pinned.cu:596-609,683-749,988-1008` — stack・予約領域の保持、alias 範囲の検査、拒否時の stderr ログ。
- `docs/AMD_HIP.md:151-158` — Windows HIP の設計説明との照合。
