# `STRATA_POOL_SPIN_US`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool の worker が、新しい仕事を待つ間に `_mm_pause` で spin してから condition variable で sleep に入るまでの時間をマイクロ秒単位で指定します。短くすると worker は早く sleep に入り、pool の仕事を公開した側が sleep 中の worker を起こします。これは pool の待機方法を調整するフックで、コメント上は test knob とされています。

生成経路は `src/program/generate.cpp` で `ExpertPool` を作成し、その constructor が値を読みます。実装には OS/backend による分岐はありません。

## 値と判定

constructor は `std::getenv()` で設定有無を判定し、設定があれば `std::atoi()` の結果を使います。文字列全体の妥当性検査はありません。

| 環境変数の状態 | `spin_before_sleep_` |
|---|---:|
| 未設定 | 20,000 µs（20 ms） |
| 空文字 | 0 µs（`atoi` が 0 を返す） |
| 数字で始まらない文字列 | 0 µs（`atoi` が 0 を返す） |
| 整数として読める文字列 | 先頭の整数値を µs として設定。先頭の空白と符号は `atoi` の変換に従い、整数の後ろの文字は検査されない |
| 負の値 | 0 µs に clamp |

`atoi` のため、小数・単位 suffix は解釈されません。たとえば `1500us` は 1500 として読まれます。整数範囲外の文字列は実装で検証・fallback されていません。

根拠: `src/kernels/cpu/pool.cpp:437-442`, `include/strata/kernels/cpu/pool.hpp:209-216,277`。

## 有効になる条件

生成時に CPU `ExpertPool` が作成される経路で適用されます。環境変数が未設定でも pool は既定の 20 ms で動きます。値を設定しても worker が仕事待ちに入らなければ影響しません。

pool は `generate.cpp` の生成処理から構築されます。CLI や設定ファイルによる上書きはこの読み取り箇所にはありません。`pool.cpp` の値読み取りに platform / GPU backend の条件分岐もありません。

## 実行時の詳細

値は `ExpertPool` constructor ごとに一度だけ読み込まれ、その pool の `spin_before_sleep_` に保存されます。既に作られた pool の値は実行中の環境変更では変わりません。後から新しい pool が作られる場合は、その constructor 時点の環境を読みます。

worker は新しい epoch を待つループで `_mm_pause` を実行し、1024 回ごとに経過時間を確認します。待機時間が指定値以上になると worker 状態を sleeping にして condition variable を待ちます。pool が新しい仕事を publish すると、sleep 中の worker を通知します。したがって 0 µs を設定しても sleep 判定は最大 1024 回の pause 後に行われます。

この変数を読み取ったこと自体によるログや警告はありません。pool constructor の一般的な起動ログは worker 数と task 数を出しますが、この設定値は表示しません。

根拠: `src/kernels/cpu/pool.cpp:478-488,491-525`; 生成経路は `src/program/generate.cpp:4744-4749`。

## 文書との照合

`include/strata/kernels/cpu/pool.hpp:209-216` は既定の 20 ms と test knob であることを説明しています。`docs/DETAILS.md` にこの変数の個別設定説明や測定結果は見つかりませんでした。性能や精度への影響は、調査対象ソースと参照資料からは確認できません。

## 根拠

- `src/kernels/cpu/pool.cpp:437-442` — constructor 内の環境読み取り、`atoi`、負値 clamp。
- `include/strata/kernels/cpu/pool.hpp:209-219,272-278` — 20 ms の既定値、worker sleep の説明、メンバー初期値。
- `src/kernels/cpu/pool.cpp:478-488,491-525` — worker の待機、時間確認、sleep と通知。
- `src/program/generate.cpp:4744-4749` — 生成経路の `ExpertPool` 構築。
