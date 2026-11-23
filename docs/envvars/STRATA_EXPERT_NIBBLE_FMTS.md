# `STRATA_EXPERT_NIBBLE_FMTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_EXPERT_NIBBLE=1` で有効にする 4-bit expert slot 機能において、変換対象とする gate/up の GGUF 形式コードを指定する。既定値は `22,18,21`（IQ2_S、IQ3_XXS、IQ3_S）。形式の選択だけでは変換は有効にならず、主スイッチ、ビルド、GPU、モデル形状、起動オプションなどの条件も必要になる。対象形式でも条件に合わないレイヤーは変換されず、down rows は常に GGUF のまま。設定を読む実装は `strata::core::nibble::config()`、選択は `plan_layer()`、起動時の適用は `generate.cpp` にある（`engine/include/strata/core/expert_nibble.hpp:213-218,238-269,315-340`; `engine/src/program/generate.cpp:5440-5480`）。

この変数だけを設定しても nibble 機能は有効にならない。`STRATA_EXPERT_NIBBLE` が未設定または `0` の場合、FMTS の値が不正でも nibble 起動判定に入らず、通常の GGUF slot のまま起動する（`engine/include/strata/core/expert_nibble.hpp:242-246`; `engine/src/program/generate.cpp:5446-5461`）。

## 値と判定

初回の `config()` 呼び出しで `getenv` し、値が未設定または空文字なら既定の3形式を維持する。空でない値は `detail::parse_list()` が10進 `strtoll` とカンマ区切りで解析する。各 parsed 値は `int` に cast され、その値が `fmt_built()` の 22、18、21 のいずれかか確認される。`strtoll` の `errno` や `int` への範囲を別途検査していない（`engine/include/strata/core/expert_nibble.hpp:94-101,216,221-235,249-261`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| FMTS のリスト解析 | `fmts` は既定の `22,18,21` | `22`、`18,21`、`22,18,21`。符号付き十進数も解析され、重複は許される。`22,` も末尾カンマ後に解析が終了するため受理される | `0`、`17` など対応外コードは型エラー。`,22`、`22,,18`、`22x` はリスト解析エラー |
| 明示的な空文字 | 既定の `22,18,21` を維持 | 該当なし | 空文字自体はエラーではない |

`strtoll` は数値の前の空白を読み飛ばすため、たとえば ` 22` は解析される一方、数値の後の空白は区切り文字ではないため `22 ` は不正となる。`22abc` や `22,18x` のように数値の後ろにカンマ以外が残る場合も失敗する。全体の文字列比較や `true` / `false` 判定はしない。数値 token のオーバーフロー時の `errno` は確認せず、さらに `int` cast 後の値を検証するため、通常の3つのコード以外の巨大値の結果は移植可能な入力仕様として保証されていない（`engine/include/strata/core/expert_nibble.hpp:223-234,255-260`）。

不正なリストまたは対応外型は `Config.error` に記録される。エラーが既に設定済みなら FMTS 側で上書きされない。`STRATA_EXPERT_NIBBLE=1` と併用した場合、エラーは起動前チェックで理由として使われ、nibble はその起動では無効になる（`engine/include/strata/core/expert_nibble.hpp:242-261`; `engine/src/program/generate.cpp:3403-3408,5446-5461`）。

## 有効になる条件

- `STRATA_EXPERT_NIBBLE=1` が必要。主スイッチは文字列全体が `1` の場合だけ on。未設定、空文字、`0` は off で、他の非空値は不正値として記録される（`engine/include/strata/core/expert_nibble.hpp:242-246`）。
- `STRATA_EXPERT_NIBBLE_BUILT` と `STRATA_NATIVE_EXPERTS` が必要。4-bit kernel は CUDA build で `STRATA_EXPERIMENTAL_SM60` が定義され、HIP/Metal ではない場合に限り組み込まれる。build 条件を満たさなければ起動前チェックが理由を返し、警告付きで通常 slot に戻る（`engine/include/strata/core/expert_nibble.hpp:33-38`; `engine/src/program/generate.cpp:3403-3409`）。
- 全ての可視 CUDA device が compute capability 6.0 でなければならない（`engine/src/program/generate.cpp:3410-3424`）。
- `--peer-device`、`--expert-cache-device1..3`、`--kv-grow`、`--vram-elastic` は利用できず、`--expert-profile` が空、または `--expert-cache 0` でも起動前チェックで無効になる（`engine/src/program/generate.cpp:3425-3435`）。
- 競合する設定がないこと。`STRATA_MMQ_DIRECT` は非ゼロ、`STRATA_PREFILL_MMQ=0`、`STRATA_PF_FUSED` が `1` で始まる値、`STRATA_FS_SLOTS` は正数、`STRATA_EXPERT_V2` が `1` で始まる値、`STRATA_KV_GROW` が `0` で始まらない非空値、`STRATA_EXP_MODE` が `atoi` で 0 または 8 以外になる値は理由として返される。各判定の詳細は `env_conflicts()` の実装どおり（`engine/include/strata/core/expert_nibble.hpp:277-299`）。
- 選ばれる各レイヤーは native pack 上にあり、`n_embd=2560`、`n_ff=640`、gate/up の row byte 数・offset・tail が所定値で、down rows が16-byte境界に合うこと。対象コードは `fmts` に含まれ、`STRATA_EXPERT_NIBBLE_SKIP` に列挙されていない必要がある（`engine/include/strata/core/expert_nibble.hpp:315-340`）。
- 選択後に対象 layer が一つもなければ、「no layer ... among STRATA_EXPERT_NIBBLE_FMTS and outside STRATA_EXPERT_NIBBLE_SKIP」の理由でその起動の機能が無効になる。prompt 側は全ての変換 layer で MMQ が必要で、direct MMQ、FP16 fallback、WMMA-only、対応 fused kernel、GGUF 配列形状との不一致も拒否条件（`engine/src/program/generate.cpp:5451-5461`; `engine/src/prefill/prefill.cpp:3915-3937`）。

既定形式を変える CLI 引数や設定ファイルの優先順位は見つからない。実際の対象 layer はモデルの native pack と expert profile に従い、FMTS は候補形式を絞る（`engine/include/strata/core/expert_nibble.hpp:327-339`; `engine/src/program/generate.cpp:3432-3435`）。

## 実行時の詳細

`config()` は関数内 `static const Config` として初回だけ構築され、FMTS を含む3つの設定をその時点の環境から読む。`generate.cpp` はモデル割当て・slot 見積りより前に config を使って拒否理由を確認し、問題がなければ layer table を設定する。その後の slot サイズ計算、expert cache fill、decode / prompt 経路はこの表を参照する。プロセス中に環境値を変更しても config には反映されない（`engine/include/strata/core/expert_nibble.hpp:238-269,345-389`; `engine/src/program/generate.cpp:5440-5464`）。

FMTS に含まれる形式と形状条件に合うレイヤーでは slot の gate/up が変換コード・scale・fp16 `d` に置き換わり、down rows は GGUF bytes のままコピーされる。slot の大きさは変換データ量に基づいて見積もられる。起動時 fill は変換した項目を round-trip 検証し、再構築した GGUF blocks も元 blob と比較する。無効な値・競合・非対応 build 等の起動前拒否は処理を終了させず、「この起動では off」と警告して通常の GGUF slot で続行する。一方、fill の CUDA エラーや変換値が round-trip しない場合は fill が失敗する（`engine/include/strata/core/expert_nibble.hpp:50-60,315-340`; `engine/src/program/generate.cpp:3225-3314,5448-5480`）。

有効時は adaptive tier の swap を無効化する。全 expert の VRAM residency や prompt chunk など後で判明する条件は別途確認され、失敗時の扱いもその起動処理に従う（`engine/src/program/generate.cpp:5462-5480`; `docs/OLDER_GPUS.md:220-231`）。

## ログと測定値

起動前に拒否された場合の形式は `strata generate: WARNING: STRATA_EXPERT_NIBBLE is off for this start: <理由>; the expert slots stay GGUF blocks`。理由には FMTS の parse エラー `STRATA_EXPERT_NIBBLE_FMTS=<値>: expected ggml types, e.g. 22,18,21`、または `STRATA_EXPERT_NIBBLE_FMTS: type <数値> is not converted (22 IQ2_S, 18 IQ3_XXS, 21 IQ3_S)` が使われる（`engine/include/strata/core/expert_nibble.hpp:250-260`; `engine/src/program/generate.cpp:5457-5461`）。有効なら layer 数と形式別内訳、追加 VRAM 量を `strata generate: STRATA_EXPERT_NIBBLE: ...` として stderr に出す（`engine/src/program/generate.cpp:5465-5480`）。

変換 fill でバッファ確保・CUDA 操作・round-trip 検証に失敗すると stderr に `strata generate: STRATA_EXPERT_NIBBLE: ...`、`strata generate: the profile fill failed at pair ...`、または layer-split 時の `strata generate: STRATA_EXPERT_NIBBLE: CUDA<n>: ...` を出して `return 1` する（`engine/src/program/generate.cpp:9700-9735,9882-9907`）。

`docs/OLDER_GPUS.md` は例として `22,18,21` を挙げ、対象が GP100 向けの opt-in 機能であると説明している。現行ソースの既定値と一致する。この資料にある性能測定値は機能全体の測定であり、FMTS の値ごとの比較ではない（`docs/OLDER_GPUS.md:200-242`）。

`docs/SETTINGS.md` の表はこの変数の対応先を「NVIDIA and AMD」と記すが、現行のコンパイル条件は CUDA の `STRATA_EXPERIMENTAL_SM60` を必要とし、HIP build では nibble kernel を組み込まない。実装上の利用条件はソースに従う（`docs/SETTINGS.md:68-70`; `engine/include/strata/core/expert_nibble.hpp:33-38`）。

## 根拠

- `engine/include/strata/core/expert_nibble.hpp:213-269` — Config、リスト解析、環境値の読み取りと既定値・エラー。
- `engine/include/strata/core/expert_nibble.hpp:277-340` — 競合判定、形式とレイヤー適格条件。
- `engine/src/program/generate.cpp:3400-3437,5440-5480` — 起動前チェック、警告、適用と有効時ログ。
- `engine/src/prefill/prefill.cpp:3915-3937` — prompt MMQ の追加条件。
- `docs/OLDER_GPUS.md:200-242` — 機能説明と測定資料。
