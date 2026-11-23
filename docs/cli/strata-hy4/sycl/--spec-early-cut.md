# `strata-hy4-sycl --spec-early-cut`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--spec-early-cut` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で変換される閾値 |

## 役割

DFly2 speculative decoding の draft tree 拡張を、残存 frontier の最大到達確率が指定値を下回ったときに早期終了させる閾値です。draft tree が有効な実行で不要な枝の展開を避けるための設定で、生成するトークン数や出力内容を直接指定するものではありません。

## 使い方

```sh
# 通常実行で DFly2 を使い、reach が 0.05 未満になった frontier の拡張を打ち切る
strata-hy4-sycl --model model.strata --tokens prompt.ids --draft dfly2 --gen 32 --spec-early-cut 0.05

# serve 経路で DFly2 を選び、同じ閾値を設定する
strata-hy4-sycl --serve --native model.strata --draft dfly2 --spec-early-cut 0.05
```

## 値と既定値

値は `atof` で `float` に変換され、`SpecCfg::early_cut` に格納されます。既定値は `0.08` です。parser に範囲検証や変換エラー検査はなく、不正な数値文字列は `atof` の変換結果（通常は `0`）として扱われます。複数回指定した場合は引数走査のたびに代入され、最後の値が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,189`）。

値を省略すると、共通の値取得処理が標準出力へ `ERR --spec-early-cut needs a value` を出し、flush 後に終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。

実際の打ち切り判定は閾値が `0` より大きい場合だけ有効です。したがって `0` と負数は打ち切りを無効にします。正の値に対する上限・下限の制限はありません（`engine/src/hy4flash/sycl/sy_dfly2.h:894-897,907-909`）。

## 実行時の動作

通常実行では、`--draft dfly2` かつ `--gen` が正のとき speculative decoding 経路に入り、`Spec` が設定を使います。値は各 draft 呼び出しで `early_cut` として渡され、draft tree の frontier のうち到達確率が最も高い候補を選ぶループで、すでに root 以外の node がある状態 (`tree.M > 1`) でその最大値が閾値未満なら、早期終了カウンタを増やして frontier 展開を止めます。また選択した node の reach が閾値未満なら、その node の子を展開しません（`engine/src/hy4flash/sycl/sy_main.cpp:279,379-386`; `engine/src/hy4flash/sycl/sy_spec.h:201-208`; `engine/src/hy4flash/sycl/sy_dfly2.h:890-909`）。

ただし `Spec::run` は、適応型 (`adaptive`) かつ `--spec-cut` の値が負の場合に限って設定値を drafter へ渡します。それ以外は `0` を渡すため、`--spec-fixed` または `--spec-cut` によってこのオプションの効果は無効になります。`--spec-cut` の既定値は `-1`、`--spec-fixed` は adaptive を false にします（`engine/src/hy4flash/sycl/sy_spec.h:21-30,203-205`; `engine/src/hy4flash/sycl/sy_main.cpp:180-189`）。

serve 経路では parser が `SpecCfg` を `ServeOpts` に渡します。serve 側で `--draft` が `off` 以外、モデルに DFly2 drafter tensor があり、chunk が 8 以上の場合に speculative path の候補となり、DFly2 初期化が成功した場合に設定が `Spec` に渡ります。`--draft dfly2` でモデルに drafter がない、chunk が 8 未満、または初期化に失敗した場合は serve 側でエラーになります。`auto` は DFly2 初期化に失敗しても serve を続け、speculative path を使わない経路にフォールバックします（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`; `engine/src/hy4flash/sycl/sy_serve.h:248-278,303-308,468-479`）。

## 適用条件と副作用

- 通常実行の既定 `--draft` は `off` です。`--draft dfly2` を指定しない場合、この値は speculative draft に使われません（`engine/src/hy4flash/sycl/sy_main.cpp:250,279-280`）。
- `--spec-early-cut` 自体はモデル読込や GPU 初期化より前に値として記録されますが、効果は上記の speculative DFly2 経路に限られます。
- 早期終了は draft tree の構築量を変えます。生成処理の時間や性能がどう変化するかは、ソースコードだけでは定量化できません。
- 対象ソースは SYCL 実装です。他 backend の同名オプションの有無や挙動はこの調査範囲に含めていません。

## 出力とエラー

オプション固有の閾値範囲エラーや警告はありません。値不足時の出力と終了コードは「値と既定値」のとおりです。draft tree の実行自体が失敗した場合、通常実行は `spec: draft failed` を標準エラーへ出して `1` を返し、serve は protocol の `ERR spec: ...` を送って `1` を返します（`engine/src/hy4flash/sycl/sy_spec.h:205-208`; `engine/src/hy4flash/sycl/sy_main.cpp:386-390`; `engine/src/hy4flash/sycl/sy_serve.h:470-476`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:105-115,180-189` — 引数走査、値取得、`atof` 変換、他の speculative decoding オプション。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,201-208` — `SpecCfg` の既定値、閾値を有効にする条件、drafter 呼び出しと失敗処理。
- `engine/src/hy4flash/sycl/sy_dfly2.h:789-791,890-909` — 閾値による frontier の早期終了と子展開の抑制。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,279-280,379-390` — serve への設定転送と通常実行の speculative path 条件。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278,303-308,468-479` — serve 側の drafter / chunk 条件、初期化、設定適用と decode 経路。
