# `HY4_DP4A`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA backend の Hy4-Flash S2/S3/S4/S5/S6/S8 線形層で、FP16 GEMV と `__dp4a` GEMV の選択に関わる。読み取り箇所は2つあり、`sk_dp4a_cuda.hip.h` は通常 GEMV / 複数 GEMV の自動選択を環境変数または GPU 世代で決め、`skhy4.hip.h` は CUDA+MMA の `linear_h` で 1-term / 2-term `__dp4a` を明示的に選ぶ。設定値は同じでも、この2経路で解釈と既定動作が異なる（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:230-242,261-295`、`engine/src/hy4flash/run/skhy4.hip.h:33-54`）。

## 値と判定

どちらの読み取りも `atoi` を使い、数値全体の妥当性検証はしない。未設定と `atoi` 結果 0 は各箇所で異なる扱いになる。

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の通常 / 複数 GEMV (`use_dp4a_gemv`) | device 0 の `major < 8` なら有効。プロパティ取得失敗または `major >= 8` なら無効 | `atoi` 結果が非0。例 `1`, `-1`, `2junk` | `atoi` 結果が0。例 空文字、`0`, `0anything`, `true`, 数字で始まらない文字列 |
| CUDA+MMA の `linear_h` (`lin_dp4a`) | 0（明示選択なし） | `atoi` 結果が非0。1未満の非0値は1-term、2以上は2-term | `atoi` 結果が0。例 空文字、`0`, `0anything`, `true`, 数字で始まらない文字列 |

`atoi` は先頭の空白と符号の後の数値部分を変換し、後続文字を検証しないため、例えば `"  +2tail"` は 2、`"1tail"` は 1 として扱われる。大文字小文字の比較はない。`atoi` の変換結果が0かどうかだけを見る箇所では、`"true"` も無効値となる（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:235-240`、`engine/src/hy4flash/run/skhy4.hip.h:40-42`）。

## 有効になる条件

- 変数を読む実装はいずれも `HY4_CUDA` のビルドに限られる。`lin_dp4a` の明示選択はさらに `HY4_MMA` が有効なビルドに限られる。HIP backend ではこれらの読み取り経路はコンパイルされない（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:7-9`、`engine/src/hy4flash/run/skhy4.hip.h:18-20,33-44`）。
- 通常 GEMV の `__dp4a` 経路は `K` が 256 の倍数で、format が S2/S3/S4/S5/S6/S8 のときだけ採用される。複数 GEMV も同様に `K` と format を確認する。条件を満たさない場合は呼び出し元が通常の FP16 GEMV に進む（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:261-270,285-295`、`engine/src/hy4flash/run/skfast.hip.h:278-292,409-423`）。
- CUDA+MMA の `linear_h` では、`lin_gemv_max_m()` 以下（かつ `M <= 16`）が GEMV 分岐であり、明示 `__dp4a` はその中でも `M <= 8` の場合だけ呼び出される。既定の上限は4。`--knobs16` はこの上限を16にするため対象バッチ範囲を広げるが、環境変数の値を上書きしない（`engine/src/hy4flash/run/skhy4.hip.h:28-31,47-54`、`engine/src/hy4flash/run/hy4_main.hip.cpp:371-374,434,792`）。
- CUDA+MMA で `HY4_DP4A` が非0のとき、`HY4_TUNE` 用の複数 GEMV 最適化判定 `lm_ok_m` は false となる。該当する fused GEMV 経路は使われず、通常の線形層経路に戻る（`engine/src/hy4flash/run/hy4_graph.hip.h:1363-1368,2089,2655,2686`）。
- 明示経路が format / K / M 条件を満たさない場合は、通常 GEMV に戻る。その通常 GEMV 側でも非0値は `__dp4a` を有効にするが、2-term 実装を使う。値0なら通常 GEMV の自動判定も無効になる（`engine/src/hy4flash/run/sk_int8_cuda.hip.h:594-607`、`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:232-242,261-270`）。

## 実行時の詳細

`use_dp4a_gemv()` は初回呼び出し時に `HY4_DP4A` を評価し、関数内 `static` の `cached` に保存する。未設定時だけ device 0 のプロパティを取得し、`major < 8` を既定有効条件とする。CUDA+MMA の `lin_dp4a()` も初回呼び出し時に `atoi` の結果（未設定なら0）を関数内 `static` に保存する。したがって、それぞれの cache 初期化後にプロセス環境を変更しても、その cache の判定は変わらない（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:232-242`、`engine/src/hy4flash/run/skhy4.hip.h:33-42`）。

`linear_h` で `lin_dp4a` が非0かつ `M <= 8` なら、値が1未満の非0では `hi=false`（1-term）、2以上では `hi=true`（2-term）を渡して `linear_h_gemv_dp4a` を呼ぶ。`K < 256`、`K` が256の倍数でない場合、または M が8を超える場合、その入口は通常 GEMV に戻る。format が S2/S3/S4/S5/S6/S8 以外の場合も FP16 GEMV にフォールバックする（`engine/src/hy4flash/run/skhy4.hip.h:47-54`、`engine/src/hy4flash/run/sk_int8_cuda.hip.h:594-607`）。

通常 GEMV と複数 GEMV は `use_dp4a_gemv()` が true で、K と format の条件を満たすと `sk_dp4a_cuda.hip.h` の `__dp4a` kernel を起動する。満たさない場合は FP16 kernel に続く。通常 GEMV の `__dp4a` 側は、各 M 行の入力を Q8_1 に量子化して重みとの積和を計算する（`engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:121-215,245-270`）。

## ログと測定値

この変数の値や無効値について出す専用ログ・警告・終了処理は、該当する読み取りと分岐にはない。対象ソースおよび `docs/DETAILS.md` に、この変数に対応づけられた測定値は見つからなかった。

## 根拠

- 候補名の全参照を確認。環境読み取りは `engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:235-240` と `engine/src/hy4flash/run/skhy4.hip.h:40-42`。`engine/src/hy4flash/run/sk_int8_cuda.hip.h:597-607` の `HY4_DP4A` は C++ のマクロ名であり、環境変数の読み取りではない。
- 自動選択と kernel への接続: `engine/src/hy4flash/run/sk_dp4a_cuda.hip.h:232-295`、`engine/src/hy4flash/run/skfast.hip.h:278-292,409-423`。
- `linear_h` の値分岐と適用条件: `engine/src/hy4flash/run/skhy4.hip.h:28-54`、`engine/src/hy4flash/run/sk_int8_cuda.hip.h:594-607`。
- `HY4_TUNE` の複数 GEMV 適用判定: `engine/src/hy4flash/run/hy4_graph.hip.h:1363-1368,2089,2655,2686`。
