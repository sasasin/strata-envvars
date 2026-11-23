# `STRATA_ROW_PF_PRO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU の native-expert 行処理で、通常の行 dot loop に入る前に先頭行をまとめて要求する prologue を有効にするか決める。既定は有効（値 1）。この prologue が要求するのは gate/up または down の先頭 `pf_rows` 行で、要求距離は `STRATA_ROW_PF` の値から行サイズ単位に切り上げて算出する。prologue を無効にしても、通常の行 dot loop が処理する行では後続行の prefetch が残る。一方、`STRATA_OWN_CPU_QUANT` build で x4 dot kernel が使われると、先頭の 4 行単位の処理は行 loop 内の lookahead を通らず、最後に残った行だけが通常 loop に入る場合がある。`STRATA_ROW_PF` が正でない経路では prologue の判定自体が呼ばれない。根拠: `engine/src/kernels/cpu/native_expert.cpp:247-260,741-788,858-892`。

## 値と判定

空でない値を `std::atoi` で整数に変換し、結果が 0 以外なら prologue を有効にする。文字列全体の妥当性検査、範囲制限、大文字小文字の判定はない。`atoi` が読む整数の後ろに文字があっても、先頭の数値部分が変換される。整数として始まらない文字列は 0 になり無効。空文字は既定値 1 に戻る。

| 条件 | unset | prologue 有効 | prologue 無効 |
|---|---|---|---|
| `STRATA_ROW_PF` 由来の `pf_rows > 0` で、初めて prologue 判定に到達 | `1`（unset または空文字） | `1`, `-1`, `2tail`, ` 1`（変換結果が非 0） | `0`, `0tail`, `false`, `true`, `x1`, 空白だけの設定文字列（変換結果 0） |
| `pf_rows == 0` | 判定されない | 該当なし | 該当なし |

表の `true` は文字列比較で真偽値として認識されるのではなく、`atoi("true") == 0` となる例。`atoi` の結果が `int` の範囲に収まらない文字列の結果は、このコードで検査・制限されない。`pf_rows` は `STRATA_ROW_PF` が空でない場合の `atoi` 結果が正のときだけ正になる。未設定・空文字・変換結果 0 以下なら prologue は評価されない。根拠: `engine/src/kernels/cpu/native_expert.cpp:247-260,742,866`。

## 有効になる条件

- CPU native-expert の gate/up または down 行処理が、形式・CPU 機能に応じた専用カーネルの早期 return を通らず、共有の dot 行ループに到達する必要がある。gate/up では trellis、IQ/KQ、NVFP4 などの専用経路が先に return する場合があり、down にも同様に専用経路がある。根拠: `engine/src/kernels/cpu/native_expert.cpp:653-740,794-865`。
- `STRATA_ROW_PF` から得る行先行距離が正である必要がある。未設定時および空文字時は同ファイルの実装では 0 なので、`STRATA_ROW_PF_PRO` は読まれず prologue は実行されない。`STRATA_ROW_PF` が正なら距離を行サイズ単位に切り上げた行数が使われる。根拠: `engine/src/kernels/cpu/native_expert.cpp:247-253,742,866`。
- CPU pool からこの行処理が呼ばれる経路では通常・window-invariant の両 arithmetic mode が同じ実装テンプレートに入る。一方、pool の Q2 専用分岐は `native_gu_rows` / `native_down_rows` を呼ばない。根拠: `engine/src/kernels/cpu/pool.cpp:1274-1309,1423-1453`、`engine/src/kernels/cpu/native_expert.cpp:897-915`。
- prologue の要求は `row_prefetch_range` に委ねられる。x86 では intrinsics、`__GNUC__` のビルドでは builtin を使い、それ以外のコンパイラでは helper は何もしない。根拠: `engine/include/strata/kernels/cpu/row_prefetch.hpp:15-43`。
- この変数を読む箇所に OS、GPU backend、サーバーモード、CLI 引数、モデル状態による追加判定はない。対象の効果は CPU native-expert 行処理に限られ、GPU 側の専用 expert kernel の設定としては使われない。根拠: `engine/src/kernels/cpu/native_expert.cpp:254-260,741-748,866-870`。

## 実行時の詳細

`row_pf_prologue()` の関数ローカル `static const int` が初めて評価されたときに読み取り、その後はプロセス内で値を cache する。呼び出し側が `pf_rows > 0` の場合に限り `row_pf_prologue()` を評価するため、先行距離が無効なままなら変数の読み取りも行われない。初回評価後にプロセス環境を変更しても反映されない。根拠: `engine/src/kernels/cpu/native_expert.cpp:254-260,742-745,866-869`。

有効時は gate/up の場合に各先頭行の gate と up の weight 範囲、down の場合に各先頭行の down weight 範囲を先に要求する。行範囲は `row_prefetch_range` が 64 byte ごとに要求する。通常の行 dot loop は、距離分の行が残っている限り後続行も要求するので、値 0 は prologue 部分だけを止める。`STRATA_OWN_CPU_QUANT` の x4 kernel が行を処理する場合、その 4 行単位の loop には後続行を要求する処理がなく、残り行が通常 loop に入った場合に限りその loop の prefetch が実行される。環境変数によるログ、警告、終了・失敗経路はこの実装にない。根拠: `engine/src/kernels/cpu/native_expert.cpp:744-788,868-890`、`engine/include/strata/kernels/cpu/row_prefetch.hpp:46-49`。

## ログと測定値

`STRATA_ROW_PF_PRO` の読み取りや有効・無効を示すログはない。`docs/DETAILS.md` にこの変数の測定値や説明は見つからないため、性能値は記載しない。実装コメントは行 prefetch が計算結果の同じ bit を保つと説明しているが、ここでは性能や実行結果を独自に測定していない。根拠: `engine/src/kernels/cpu/native_expert.cpp:741-742`。

## 根拠

- 値の読み取り・既定値・cache: `engine/src/kernels/cpu/native_expert.cpp:254-260`
- 先行距離の読み取りと gate/up への適用: `engine/src/kernels/cpu/native_expert.cpp:247-253,741-773`
- down への適用: `engine/src/kernels/cpu/native_expert.cpp:858-890`
- pool からの呼び出しと Q2 専用分岐: `engine/src/kernels/cpu/pool.cpp:1274-1309,1423-1453`
- prefetch 命令の platform / compiler 分岐と 64 byte 単位の走査: `engine/include/strata/kernels/cpu/row_prefetch.hpp:15-49`
- 関連資料との照合: `docs/DETAILS.md` に `STRATA_ROW_PF_PRO` の説明・測定値はない。
