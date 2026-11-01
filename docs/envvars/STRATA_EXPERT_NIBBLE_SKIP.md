# `STRATA_EXPERT_NIBBLE_SKIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_EXPERT_NIBBLE=1` で使う実験的な expert 4-bit slot 変換から、指定した層を除外します。除外層は従来どおり GGUF ブロックのまま VRAM slot に置かれ、slot サイズも GGUF blob のサイズです。この変数単独では変換を有効にしません。

層番号は 0 始まりです。設定値はモデルの層番号と照合されます。対象機能は native expert pack を使う CUDA の `STRATA_EXPERIMENTAL_SM60` build 向けで、実行時には見えている全 CUDA device が compute capability 6.0 であることなどの条件があります。

## 値と判定

環境変数が未設定または空文字なら除外リストは空です。空白以外の値は `strtoll(..., 10)` による符号付き 10 進整数のカンマ区切りとして読み込みます。文字列全体を各整数の後ろまで厳密に検査し、整数の後にはカンマか終端しか認めません。`strtoll` の仕様により各要素の先頭空白と `+` / `-` は受け付けますが、数字の後ろの空白は区切り・終端ではないため無効です。末尾カンマは次の要素を読まずに終わるため受理されます。重複番号は動作上同じ層を複数回除外するだけです。

| 状態 | 結果 |
|---|---|
| unset / 空文字 | 空リスト。層を除外しない |
| `0`, `2,5`, `+2`, `2, 5` | 数字列を層番号として除外候補にする |
| `2,`, `2,2` | 受理。末尾カンマは空要素として扱われず、重複は実質的に無視される |
| `2,,5`, `2x`, `2 ` | リスト不正 |
| 負数または層数以上の番号 | 値の変換後、モデルの範囲外として不正（ただし `STRATA_EXPERT_NIBBLE=1` のとき） |

`strtoll` の `errno` は検査されません。変換結果がモデル層の範囲外なら有効化時に範囲外として拒否されます。無効リストを読み込んだ場合も設定エラーになりますが、実際の起動への影響は下記のとおり `STRATA_EXPERT_NIBBLE` が有効な場合に限られます。

## 有効になる条件

- `STRATA_EXPERT_NIBBLE=1` が必要です。主スイッチが未設定または `0` なら skip 設定は使われず、リストの形式や範囲も起動時に検証されません。
- 主スイッチが有効でも、空でない skip リストは、その層を変換対象から外すだけです。残った層に変換可能な IQ2_S / IQ3_XXS / IQ3_S の層が一つもない場合は、変換を有効にできません。
- 4-bit kernel がない build、native expert でない pack、見える CUDA device がない場合、または全 device が compute capability 6.0 でない場合は機能全体が拒否されます。実装上、4-bit kernel は `STRATA_EXPERIMENTAL_SM60` 有効の CUDA build に限られます。
- GPU residency、expert cache、prompt の slot loan / chunk など追加条件を満たさない場合も、skip の指定だけでは機能を成立させられません。条件に合わない起動は変換を無効にするか、起動を拒否します。

## 実行時の詳細

`nib::config()` が初めて呼ばれたとき、C++ function-local `static const Config` として環境設定一式を一度だけ読み取ります。generate 起動経路では expert layout の読み込み後、GPU slot のサイズ見積もりや allocation より前にこの設定を判定します。起動後に環境を変更しても同一プロセス内では再読込されません。CLI に skip 層を指定する引数はなく、CLI がこの値を上書きする経路もありません。

変換計画では各層番号 `l` が skip リストに含まれるかを比較し、含まれる層は `LayerVram.on` を有効にしません。変換対象外の層は元の blob サイズ・GGUF ブロックのままです。指定番号が負数、または `lay.n_layers` 以上なら、主スイッチ有効時に `STRATA_EXPERT_NIBBLE_SKIP: layer N is not in the model` の理由になります。形式不正なら `STRATA_EXPERT_NIBBLE_SKIP=<値>: expected layer numbers, e.g. 40,44` が理由になります。

いずれも通常の generate 経路では stderr に `strata generate: WARNING: STRATA_EXPERT_NIBBLE is off for this start: ...; the expert slots stay GGUF blocks` と出し、変換テーブルをクリアして通常の GGUF slot で続行します。別の `STRATA_EXPERT_NIBBLE` / `STRATA_EXPERT_NIBBLE_FMTS` の設定エラーが先にある場合は最初の設定エラーが優先されます。変換が有効になっても、必要な全 expert が VRAM に常駐しない場合や prompt 条件に合わない場合は起動を拒否する経路があり、stderr に理由を出します。serve 経路の prompt 条件エラーは `strata serve: STRATA_EXPERT_NIBBLE refuses the start: ...` と出して終了コード 1 になります。

`docs/OLDER_GPUS.md` も `<layers>` を GGUF slot に残す用途としてこの変数を記載しています。現行実装ではその具体的な値の parse と範囲判定は下記のとおりです。

## 根拠

- `include/strata/core/expert_nibble.hpp:213-218,223-235,238-269`: skip 設定の保持、10 進カンマ区切り parse、unset / 空文字判定、function-local static による一度だけの読み取り、形式エラー。
- `include/strata/core/expert_nibble.hpp:315-340`: 層番号との照合、および skip 層を変換しない条件。
- `include/strata/core/expert_nibble.hpp:343-356`: 層数範囲の検証と範囲外エラー。
- `src/program/generate.cpp:2667-2718`: build / native pack / CUDA device 条件、他環境変数との衝突、および CLI 条件。
- `src/program/generate.cpp:4159-4199`: slot allocation 前の有効化判定、通常 slot への fallback 警告、adaptive tier の無効化と有効時ログ。
- `src/program/generate.cpp:7516-7548,9722-9751`: 全 expert residency の確認、および serve の prompt 条件と拒否経路。
- `docs/OLDER_GPUS.md:225-236`: skip の目的と、変換の追加条件に関する既存概要。
