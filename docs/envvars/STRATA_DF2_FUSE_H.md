# `STRATA_DF2_FUSE_H`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal backend の DFlash2 drafter が、中間 float 値の half 形式コピーを生成 kernel と同時に書く経路を使うか選びます。有効時は RMS norm、畳み込み、attention merge、SwiGLU などの fused variant が `xh` に half 値も書き、後続処理で別の float-to-half dispatch を省けます。無効時は対応する非 fused kernel と、必要な箇所で `df2_f16` dispatch を使います。

この変数の実読み取りは `metal/src/engine/dflash2.inc` に1箇所あります。ほかの参照は同ファイルの説明コメントです。候補一覧の名前どおり環境変数ではありますが、Metal backend で DFlash2 drafter を bind しない実行には影響しません。

## 値と判定

実装は値を parse せず、設定値の先頭文字だけを `0` と比較します。

| 環境の状態 | `d.fuse_h` | 判定 |
|---|---:|---|
| 未設定 | 有効 (`true`) | 既定で fused 経路 |
| 空文字 | 有効 (`true`) | 値は存在するが先頭文字は `\0` |
| 先頭文字が `0` | 無効 (`false`) | 例: `0`, `0anything` |
| それ以外 | 有効 (`true`) | 例: `1`, `false`, `off`, ` 0` |

数値変換、空白除去、文字列全体の比較はありません。値の形式が無効でもエラーや警告にはならず、先頭文字の規則だけで決まります。

## 有効になる条件

- `metal/src/engine/dflash2.inc` の Metal 実装でのみ読み取られます。`Dflash2Drafter::bind()` が Metal decode window の `df2_bind()` を呼び、DFlash2 pack と tap が用意できた場合に値が参照されます。
- DFlash2 drafter 自体が使われない場合、または bind に到達しない場合、この値の判定もありません。CUDA/HIP の DFlash2 実装ではこの名前を読み取る箇所はありません。
- CLI 引数や別環境変数による上書きはありません。DFlash2 の選択・起動条件は別途ありますが、この値は bind 後の Metal kernel 経路を選ぶだけです。

## 実行時の詳細

`Window::df2_bind()` は pack のロード後に `STRATA_DF2_FUSE_H` を読み、`Df2::fuse_h` に保存します。これは static cache ではなく drafter の bind 状態です。すでに bind 済みなら関数は読み取りより前に成功して戻るため、bind 後にプロセス環境を変更しても現在の drafter には反映されません。dispatch list は最初の draft 時にこの保存値に基づいて作られます。

有効時、Q4_0 GEMM の入力が直前の producer により half 化済みなら、`df2_mm4()` は `reuse` に応じて `df2_f16` dispatch を省略し、その half バッファを使います。`fc.weight` は window taps が入力であるため、この再利用扱いから除外されます。無効時は対応箇所で `df2_f16` を dispatch して半精度入力を作り、RMS norm、attention merge、SwiGLU なども非 fused variant を選びます。Q8_0 GEMV 経路も存在するため、変数が DFlash2 の全演算を Q4_0 に変えるわけではありません。

この変数専用のログ、警告、エラー経路はありません。bind 完了時には設定値にかかわらず `strata metal: DFlash2 drafter ready (...)` が stderr に出ます。値の判定自体で bind の失敗や終了は発生しません。

## 根拠

- `metal/src/engine/dflash2.inc:76-88,282-288,397-411`: `fuse_h` の既定値、bind 条件、環境値の読み取りと保存、完了ログ。
- `metal/src/engine/dflash2.inc:449-483`: Q4_0 GEMM 前の `df2_f16` dispatch と half 入力の再利用、`fc.weight` の例外。
- `metal/src/engine/dflash2.inc:485-495,497-514,544-557,584-615,619-630`: fused / 非 fused kernel と half 書き出しの分岐。
- `metal/src/engine/msl/dflash2.metal:768-815`: half 出力を併せて書く fused kernel 群。
- `metal/src/engine/dflash2.inc:740-775`: dispatch list が初回 draft 時に構築される箇所。
- `metal/src/engine/dflash2.inc:1034-1064`: Metal の `Dflash2Drafter::bind()` から window の bind へ進む呼び出し。
