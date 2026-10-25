# `STRATA_Q36_NO_EXT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-q36` エンジンの Qwen3.6 MoE 層で、複数行 decode 時に使う router と shared expert gate の拡張行付き積 (`router_ext`) を無効にします。通常の router 行列積に加えて shared expert gate の入力積を別に実行する経路になります。1 行だけの処理では、この環境変数を設定していても拡張行付き積を使います。

対象エンジンは `strata-q36` と、Qwen3.6 (`qwen35moe`) のときに同じエンジンへ切り替える `strata` です。根拠: `CMakeLists.txt:711-725`。

## 値と判定

値の内容は parse せず、`getenv()` が null かどうかだけを調べます。

| 設定状態 | `T == 1` | 複数行の拡張行経路が他の条件を満たす場合 |
|---|---|---|
| unset | 1 行処理として拡張行を使用 | 拡張行を使用 |
| 設定あり（空文字、`0`、`1`、その他を含む） | 1 行処理として拡張行を使用 | 拡張行を使わない |

この変数に無効値や境界値はありません。設定後の値の変更は各 layer の処理時に再度 `getenv()` で確認されます。対して関連する `STRATA_Q36_OLD_KERNELS` と `STRATA_Q36_VERIFY` は `Engine` のフィールド初期化時に一度だけ設定有無を読みます。

## 有効になる条件

複数行で拡張行付き積を使うには、すべての条件が必要です。

- `STRATA_Q36_OLD_KERNELS` が未設定で、fast kernel 経路である。
- `STRATA_Q36_NO_EXT` が未設定である。
- `STRATA_Q36_VERIFY` が未設定である。
- 行数 `T` が `kGemmT` 以下（`kGemmT` は 8）。
- モデルの expert 数 `g.n_expert` が 256 で、top-k `Kp` が 8。

条件を満たさない場合は `router` の積を行い、shared expert gate の積を後段で別に行います。`T == 1` は別条件で常に拡張行経路です。したがって、この変数だけで1行処理を切り替えることはできません。

## 実行時の詳細

各層で `ext` を判定します。`ext` が true のときは、router の重みに shared expert gate の重み行を追加した `router_ext` と hidden state の積を一度に計算します。router の結果から routed expert を選び、追加行の結果を shared expert の gate として `moe_end` に渡します。`ext` が false のときは router のみ計算し、shared expert gate の重み (`sh_gate_inp`) と hidden state の積を別途計算して `moe_end` に渡します。

環境変数を読む箇所にログ出力はありません。設定値が変えるのはこれらの積の実行経路です。ソースと `docs/DETAILS.md` に、この変数による性能差や出力同一性の測定記載は確認できません。

## 根拠

- `src/qwen35/q36_engine.cu:845-847,1055-1064`: router と shared gate の重みを保持し、追加行付き重み行列を構成。
- `src/qwen35/q36_engine.cu:1562-1577`: `kGemmT=8` と fast/verify kernel フラグ。
- `src/qwen35/q36_engine.cu:1998-2005,2009-2011,2053-2071`: 環境変数を含む `ext` 判定、router の積、route 入力の行数、shared gate の積と `moe_end` への引き渡し。
- `CMakeLists.txt:711-725`: エンジンライブラリと `strata-q36` のビルド、および `strata` からの利用。
