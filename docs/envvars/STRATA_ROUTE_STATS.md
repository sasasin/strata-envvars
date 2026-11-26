# `STRATA_ROUTE_STATS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP verifier の speculative verify window 内で、各層の router が選んだ expert ID を追加集計する診断用フック。window 内の先行 row に同じ ID がない expert を row ごとに数え、結果を `route_stats_report()` が window 幅別に平均化して返す。集計用の CUDA/HIP kernel は `ids_` を読むだけで、route ID や weight を書き換えないため、この変数自体は生成 token や router の選択を変えない（`engine/src/core/verify.cpp:2671-2680`、`engine/src/kernels/cuda/verify_kernels.cu:625-638`）。

有効時も、集計値の標準出力は `STRATA_SPEC_T_CYCLE` から有効な window 幅が一つ以上得られたベンチ実行の終了時だけ表示される。したがって通常の生成で有効にしても、出力が表示されない場合がある（`engine/src/program/generate.cpp:24811-24821,25279-25289`）。

## 値と判定

`Verifier::init()` で `std::getenv` の戻り値と先頭 1 byte だけを検査する。文字列全体の parse や数値変換は行わない（`engine/src/core/verify.cpp:1263-1271`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP verifier の初期化 | 集計バッファを確保せず、集計しない | 先頭文字が `1`（`1`, `10`, `1anything`） | 空文字、`0`, `2`, `true`, ` 1` |
| Metal verifier | Metal 用初期化から先に return し、この変数を読まない | 該当なし | 値にかかわらずこの集計は行わない |

大小文字・空白・後続文字は解釈されない。たとえば `true` は先頭が `t` なので無効で、`1true` は先頭が `1` なので有効。CUDA/HIP では有効時に `17 * n_layers * 16` 個の `unsigned long long` 用 device buffer を確保する。確保に失敗すると `rs_on_` を有効にせず、CUDA error state を読み捨てる。警告やエラー文は出さず、集計・レポートは無効のままとなる（`engine/src/core/verify.cpp:1263-1271`）。

## 有効になる条件

- CUDA/HIP の `Verifier::init()` が実行されること。Metal は初期化の Metal 分岐で return するため対象外（`engine/src/core/verify.cpp:956-993,1263-1271`）。
- device buffer の確保に成功すること。失敗時は理由ログなしで集計を無効化する（`engine/src/core/verify.cpp:1264-1271`）。
- `record_window()` 内で `G == 1`、`n <= 16`、`T <= 16` であること。このとき各層の router 後に集計 kernel を enqueue する。`G` は `split_ && T >= 2` または `T > kVerifyMaxT`（ただし batch capture 中を除く）で 2 になるため、その経路では集計 kernel が呼ばれない（`engine/src/core/verify.cpp:1484-1486,2679-2680`）。
- レポートを標準出力で見るには、別途 `STRATA_SPEC_T_CYCLE` に `1..--spec` の範囲に入る値が少なくとも一つ必要。値はカンマ区切り部分ごとに `atoi` で読み、範囲外は捨てられる。空文字や有効な幅がない値では cycle が空になり、`route_stats_report()` 自体が呼ばれない（`engine/src/program/generate.cpp:24811-24821,25279-25289`）。
- 計測対象の ID は router の後、任意の `STRATA_ROUTE_PRIOR` と `STRATA_ROUTE_RESIDENT` の処理後に読み取られる。そのためこれらが選択 ID を変える設定なら、その後の ID が計上される（`engine/src/core/verify.cpp:2662-2680`）。

## 実行時の詳細

環境変数は verifier 初期化時に読み、結果をインスタンスの `rs_on_` に保存する。各 window や request ごとには再読しないため、初期化後にプロセス環境を変更してもその verifier には反映されない（`engine/src/core/verify.cpp:1263-1271`）。

集計 kernel は各層で router が書いた `ids_` を走査し、同じ row 内の重複と、それ以前の row に現れた ID を除いて row 別のカウンターを加算する。従って「distinct experts per layer」は window 全体での distinct 数、「new per row」はそれ以前の row にない ID の row 別数である（`engine/src/kernels/cuda/verify_kernels.cu:625-638`）。集計は route 処理の後、plan/doorbell に続く処理の前に stream 上へ投入される（`engine/src/core/verify.cpp:2662-2684`）。

window を stage するたび `rs_win_[T]` が増える一方、集計 kernel の条件は `G == 1` である。このため同じ `T` に `G == 2` の window が混在すると、その window の値は加算されず、report の分母 `rs_win_[T] * n_layers` には含まれる。該当条件では表示値が集計対象 window の値より小さくなり得る（`engine/src/core/verify.cpp:2679-2680,3587-3589,3187-3199`）。

`route_stats_report()` は有効時に device buffer を host にコピーし、T=1..16 の行を整形した後、device カウンターと window 数をゼロに戻す。現在の generate 経路では `STRATA_SPEC_T_CYCLE` が空でない場合に終了時 1 回呼ばれる（`engine/src/core/verify.cpp:3180-3205`、`engine/src/program/generate.cpp:25279-25289`）。

## ログと測定値

集計 buffer の確保失敗時にこの変数固有のログはない。route kernel の launch error は `route_marginal_stats` と CUDA/HIP エラー文字列を stderr に出し、プロセスを `exit(1)` で終了する（`engine/src/core/verify.cpp:1265-1271`、`engine/src/kernels/cuda/verify_kernels.cu:1994-1996`、同ファイル `:37-40`）。

`STRATA_SPEC_T_CYCLE` が有効なら、標準出力に `routed experts per window width:` と、たとえば `T2 (n=...): distinct experts per layer ...; new per row: ...` の行を出す。集計値は verifier の report 呼び出しまでのカウンターから算出され、その後リセットされる。Strata の docs にこの変数の別の測定値や性能値の記載は見つからなかった（`engine/src/core/verify.cpp:3180-3205`、`engine/src/program/generate.cpp:25279-25289`）。

## 根拠

- `engine/src/core/verify.cpp:956-993,1262-1271` — verifier の backend 分岐、環境変数の読み取りと device buffer 初期化。
- `engine/src/core/verify.cpp:1484-1486,2662-2684,3587-3589` — window 分割条件、router 後の集計呼び出し、window 数の記録。
- `engine/src/core/verify.cpp:3180-3205` — host へのコピー、平均値の算出、カウンターの reset。
- `engine/src/kernels/cuda/verify_kernels.cu:37-40,625-638,1994-1996` — route marginal kernel と launch error の扱い。
- `engine/src/program/generate.cpp:24811-24821,25279-25289` — ベンチ用 window cycle とレポート表示条件。
- `engine/include/strata/core/verify.hpp:462-463,656-658` — report API と集計状態の宣言。
