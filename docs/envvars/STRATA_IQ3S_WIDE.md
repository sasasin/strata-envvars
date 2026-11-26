# `STRATA_IQ3S_WIDE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の IQ3_S 行列ベクトル積で、通常の multi kernel の代わりに wide kernel を選ぶ opt-in 変数。対象コードは `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp` にあり、ファイル名に `cuda` を含むが、このファイルは `engine/sycl/CMakeLists.txt` から SYCL ビルドへ登録されている（同 CMakeLists.txt:44）。実行時の選択は `iq_mmvq` の `t == 21` 分岐で行われる。

wide kernel は IQ3_S の重みと Q8_1 入力の積を計算する。コードコメントによれば、各 sub-block の積は `vec_dot_iq3_s_q8_1` と同じで、sub-block の加算順だけが `mmvq_multi_kernel` と異なるため、出力の最下位ビット付近に差が生じうる（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6445-6448,6482-6499`）。

## 値と判定

`iq3s_wide_on()` が `std::getenv` で取得した文字列を `std::atoi` に渡し、変換結果が 0 以外なら on とする。未設定は `nullptr` 判定で off。空文字も `atoi("") == 0` なので off。全体の厳密な数値 parse ではなく、`atoi` が先頭から読める符号付き十進整数の prefix を変換する。したがって `1`、`2`、`-1`、`1tail` は on、`0`、`0tail`、`true`、`false`、空文字、数値の前に空白しかない文字列は off。先頭の空白と符号は `atoi` の規則で許容され、大文字小文字を比較する処理はない。整数として読めない文字列は 0 になる。範囲検査や clamp はなく、`int` で表せない数値を渡した場合の結果は C の `atoi` の規定外である（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6505`）。

| 条件 | unset | wide kernel を要求する値 | off となる値 |
|---|---|---|---|
| SYCL 内の IQ3_S (`t == 21`) 呼び出し | off | `atoi` の結果が 0 以外（例: `1`, `-1`, `1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0tail`, `true`, `abc`） |

## 有効になる条件

- SYCL backend の `iq_mmvq` に IQ3_S (`t == 21`) が渡される必要がある。別 backend の同名環境変数読み取りは見つからなかった（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6530-6535`）。
- `n_in` が `QK_K` の倍数（この IQ3_S 実装では 256 要素単位）で、`ncols` が 1〜8 のとき wide kernel が起動される。どちらかを満たさない場合は wide launcher が `false` を返し、既存経路へ進む（同:6515-6527）。
- wide 経路の判定は Battlemage の B60 cache 経路や public XMX 経路より前にある。wide が起動すれば後続の経路へは進まない。wide が無効、または形状条件に合わない場合は、該当すれば B60 cache / Battlemage XMX が検討され、その後は通常の `launch_mmvq` に進む（同:6535-6558）。
- この分岐にはデバイス世代、CLI 引数、サーバーモード、モデル名、別の環境変数による追加条件は書かれていない。SYCL device が必要な subgroup size 32 をサポートできず kernel 起動に失敗する場合の扱いは、この選択コードには個別 fallback として実装されていない（wide kernel 起動属性は同:6511-6513）。

## 実行時の詳細

環境変数はプロセス起動時ではなく、`iq3s_wide_on()` が最初に呼ばれたときに関数内 `static const bool` として一度だけ評価・保存される。`iq_mmvq` が `t == 21` のとき `launch_iq3s_wide` を呼び、その先で値を参照する。したがって初回評価後にプロセス環境を変更しても、このプロセスの判定には反映されない。CLI 引数や別変数との上書き・優先順位処理、子プロセスへの設定転送はこの変数の参照箇所にはない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6505,6515-6517,6530-6535`）。

有効値かつ形状条件を満たす場合、列数に応じた `launch_iq3s_wide_t<1>` 〜 `<8>` を起動し、成功扱いで `iq_mmvq` から戻る。wide launcher が使われない場合は既存の処理が継続する。IQ3_S 以外ではこの変数の判定関数自体が呼ばれない（同:6515-6527,6530-6558）。

## ログと測定値

この変数の読み取り値や kernel 選択を示す専用ログはない。wide 起動後の `check("iq_mmvq")` も、このファイルの `check` 実装ではログ出力を行わない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:72-84,6535`）。

`docs/INTEL.md:463` は wide kernel を opt-in と記載し、「one B70 (decode -0.3%)」および 2 枚構成での報告を載せている。ただし同箇所にはモデル、量子化、OS、測定回数などの条件が記載されていないため、測定値を一般的な効果として扱えない。ソースコードには性能測定値はない。

## 根拠

- 直接の環境読み取りと値判定、static cache: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6505`
- wide kernel の計算と加算順についての実装コメント: 同:6445-6448,6482-6499
- 入力幅・列数の判定と launcher: 同:6515-6527
- IQ3_S 呼び出し順と後続 fallback: 同:6530-6558
- SYCL build への登録: `engine/sycl/CMakeLists.txt:44`
