# `MM_PROBE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`MM_PROBE` は Metal の routed-expert GEMM (`moe_mm.metal`) を調べるため、`moe_mm_parity` テスト／ベンチプログラムが Metal function constant 5 に設定する整数値である。一般の Strata 推論設定として環境変数を読むものではない。いくつかの値は重みの復号や行列積を省く、または誤った値を作るベンチ用経路を選ぶ。

## 値と判定

テストプログラムは `getenv("MM_PROBE")` が null なら `0`、設定されていれば `atoi` の結果を使う。したがって未設定は 0、空文字や数値として読めない文字列は `atoi` により 0 になる。数値の後ろに文字がある文字列は数値部分を変換する（例: `3xyz` は 3）。大文字小文字を区別する文字列判定ではなく整数の等値比較である。値の許容範囲チェックや clamp はなく、ここにない整数は各分岐に一致しない限り probe 分岐を選ばない。

| 整数値 | 該当する Metal 経路と処理 |
| --- | --- |
| `0`（既定） | probe 用の変更を選ばず、通常の重み読み取り・演算を行う。 |
| `1` | `mm_gu2` は重みを復号せずパターン値で埋める。`mm_gu3` は gate/up の重み復号を定数値で置き換える。どちらも通常の出力計算との比較には使えない。 |
| `2` | `mm_gu2` の行列積呼び出しを省略する。accumulator は初期化値のまま後段へ進む。 |
| `3` | IQ3_XXS の `W8` 復号で threadgroup table lookup を省くベンチ経路を選ぶ。ソースコメント上、値は正しくない。 |
| `4` | IQ3_XXS の符号値を table lookup せず `popcount` から計算する経路を選ぶ。 |
| `5` | IQ3_S の `W8` 復号で load と scale を残し、grid lookup／sign 計算を省くベンチ経路を選ぶ。ソースコメント上、値は正しくない。`mm_gu2` では別途「重み復号を省略する」値としても使われる。 |
| `7` | IQ3_S の `W8` 復号で再配置を想定した aligned 16-byte load のベンチ経路を選ぶ。ソースコメント上、読み出し位置は任意の領域となり値は正しくない。 |
| その他（`6` を含む） | 上記の probe 分岐に一致せず、該当する通常経路を通る。 |

`atoi` の数値範囲外の扱いは C ライブラリ実装に依存し、このコードでは別途検証・処理しない。

## 有効になる条件

- `metal/tests/moe_mm_parity.cpp` の `moe_mm_parity` 実行時に読み取られる。v2 以前の `mm_gu`/`mm_gu2`、`--v3`、`--v4` の gate/up pipeline に function constant 5 として渡される。`--v5` の pipeline には渡されない。
- `1` と `2` の分岐は `mm_gu2` 内にある。`3` と `4` は IQ3_XXS の `W8`、`5` と `7` は IQ3_S の `W8` でのみ対応する分岐がある。異なる形式・カーネルでは設定値があっても該当分岐が実行されない。
- 通常の Metal engine 経路は `metal/src/engine/window.cpp` と `metal/src/engine/prompt_chain.inc` で function constant 5 に 0 を明示するか、値を指定しない。いずれも環境変数 `MM_PROBE` を参照しない。値を設定しても通常の Strata engine の挙動は変わらない。

## 実行時の詳細

環境変数は `moe_mm_parity` の pipeline 作成時に読み取られ、pipeline に関数定数として固定される。各 pipeline 作成式で `getenv` と `atoi` を実行するため、環境を変更して新たに作成した pipeline にはその時点の値が使われる。既に作成済み pipeline に後から環境変数を変更しても、その関数定数は更新されない。子プロセスへの転送・上書き処理はこの参照箇所にはない。

値 `1`、`2`、`3`、`5`、`7` は計算を省いたり不正なデータを作ったりするため、`moe_mm_parity` の出力を通常の推論結果や正確性確認の結果として扱う用途ではない。`MM_PROBE` 自体が値を表示するログや警告を出す処理は確認できない。

`docs/DETAILS.md` には Metal prompt expert 経路についての説明はあるが、`MM_PROBE` やこのテスト専用の probe 値についての記述は見つからなかった。

## 根拠

- `metal/tests/moe_mm_parity.cpp:96-107`: `getenv` と `atoi` による既定値、v2/v3/v4/v5 での pipeline 定数設定。
- `metal/kernels/moe_mm.metal:286-288, 317-329`: function constant 5 の宣言、未指定時の shader 側既定値、`mm_gu2` の値 `1`/`2` の処理。
- `metal/kernels/moe_mm.metal:604-628`: IQ3_XXS の `W8` における値 `3`/`4`。
- `metal/kernels/moe_mm.metal:676-707`: IQ3_S の `W8` における値 `5`/`7`。
- `metal/kernels/moe_mm.metal:824-828`: `mm_gu3` の値 `1` による復号の置き換え。
- `metal/src/engine/window.cpp:2357-2368` と `metal/src/engine/prompt_chain.inc:301-308`: 通常 engine 経路で probe 定数を 0 にする箇所、または指定しない箇所。
