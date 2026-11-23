# `STRATA_EXPERT_NIBBLE_SKIP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_EXPERT_NIBBLE=1` で有効にする実験的な 4-bit expert slot 機能から、指定した層を除外する。除外層は gate/up 重みを変換せず GGUF ブロックのまま VRAM slot に置き、他の条件を満たす対象層だけを変換する。対象となる層番号は 0 始まりで、各層の形式・形状が対応条件に合うことも必要。`STRATA_EXPERT_NIBBLE` が有効でないと、この変数だけでは何も有効にならない。層計画と値の読み取りは `engine/include/strata/core/expert_nibble.hpp:213-219,238-269,315-340`、起動時の有効化は `engine/src/program/generate.cpp:5440-5464`。

## 値と判定

値は `std::getenv` で読み、未設定または空文字なら空の skip リストになる。空でない場合は `strtoll(..., 10)` で符号付き 10 進整数を読み、カンマ区切りの層番号として全体を順に解析する。先頭の空白と符号は `strtoll` が受け付けるが、整数の後ろにはカンマか文字列末尾だけを許す。各カンマの後ろの空白は次の `strtoll` が読み飛ばす。大文字小文字の区別は関係しない。数値の重複は拒否されず、同じ層を複数回指定しても結果は同じ。`strtoll` の `errno` は検査されないため、整数範囲を超えた値は通常の parse エラーではなく、変換後の層範囲チェックに進む。根拠: `engine/include/strata/core/expert_nibble.hpp:221-235,263-266,353-355`。

| 条件 | unset / 空文字 | 設定時に受理される例 | 無効になる例 |
|---|---|---|---|
| `STRATA_EXPERT_NIBBLE=1` で層計画を実行 | skip なし | `40,44`、`+40, 44`、`40,` | `,40`、`40,,44`、`40x`、`40  ,44` |
| `STRATA_EXPERT_NIBBLE` が有効でない | skip なし。この変数単独では層範囲も検証しない | 設定値は読み取られるが効果なし | 同左。SKIP の parse error だけでは nibble 起動判定に入らない |

parse error は `STRATA_EXPERT_NIBBLE_SKIP=<値>: expected layer numbers, e.g. 40,44` として設定エラーに保持される。さらに、nibble 機能が有効な状態で番号が負数または `lay.n_layers` 以上なら `STRATA_EXPERT_NIBBLE_SKIP: layer <番号> is not in the model` がエラーになる。これらのエラーは層単位でその層だけを無視するのではなく、当該起動で nibble 機能全体を無効にする。根拠: `engine/include/strata/core/expert_nibble.hpp:263-266,343-355`、`engine/src/program/generate.cpp:5446-5461`。

## 有効になる条件

- `STRATA_EXPERT_NIBBLE=1` が必要。SKIP はこのスイッチで選ばれる機能の対象層を除外するだけで、機能自体を有効化しない。設定の読み取り規則は `engine/include/strata/core/expert_nibble.hpp:242-245,263-269`。
- 4-bit kernel を含む CUDA build（`STRATA_EXPERIMENTAL_SM60` と native experts）であり、可視 CUDA device がすべて compute capability 6.0 であることが必要。HIP / Metal / 対応 kernel のない build、または条件に合わない GPU では起動時に機能を無効化する。`engine/src/program/generate.cpp:3385-3387,3403-3424`。
- `--peer-device`、remote expert cache、`--kv-grow`、`--vram-elastic` は使えない。環境設定 `STRATA_MMQ_DIRECT`（空でなく `atoi` が非 0）、`STRATA_PREFILL_MMQ`（空でなく `atoi` が 0）、`STRATA_PF_FUSED`（先頭文字が `1`）、`STRATA_FS_SLOTS`（`atoi` が正）、`STRATA_EXPERT_V2`（先頭文字が `1`）、`STRATA_KV_GROW`（先頭文字が `0` 以外）、`STRATA_EXP_MODE`（`atoi` が 0 または 8 以外）も競合理由となる。いずれかに該当すると、この起動では nibble を無効化する。`engine/src/program/generate.cpp:277-298,3425-3435`。
- `--expert-profile` が必要で、`--expert-cache 0` は不可。変換対象層の形式・形状が対応範囲外の場合もその層は変換されず、skip 層以外に変換対象が一つも残らない場合は起動時に機能を無効化する。層は 2560 × 640 の対応 shape、build 済み format であり、既定の対象 format は IQ2_S / IQ3_XXS / IQ3_S。`engine/include/strata/core/expert_nibble.hpp:216,327-340`、`engine/src/program/generate.cpp:3432-3435,5451-5455`。
- 起動後に検査される条件として、各層の全 expert が担当 GPU の VRAM に常駐できること、prompt path が cache slot を借りないこと、対応する MMQ prompt 経路であること、通常時と同じ prompt chunk を使うことが必要。skip 層も含め全層の expert residency が検査される。これらを満たさない場合は起動を拒否する。`engine/src/program/generate.cpp:9957-9989,12814-12843`、prompt MMQ 判定は `engine/src/prefill/prefill.cpp:3915-3937`。

## 実行時の詳細

`config()` 内の関数ローカル `static const Config` が初回呼び出し時に環境を読み、その値をプロセス内で保持する。起動経路は割り当て前に設定を確認し、問題がなければ native expert layout の各層を計画する。リストに含まれる層は `skipped` になり `LayerVram::on` が false のままなので GGUF slot サイズを使い、対象外の対応層は gate/up を 4-bit slot に変換する。したがって、プロセス起動後の環境変更やリクエストごとの変更では適用対象は変わらない。`engine/include/strata/core/expert_nibble.hpp:238-269,315-340`、`engine/src/program/generate.cpp:5446-5455`。

SKIP の parse error または範囲外層番号が見つかると `nibble_refusal()` が理由を返す。起動コードは stderr に警告し、層テーブルを空に戻して GGUF slot の通常経路で起動を続ける。ほかの後段条件（例: 全 expert が VRAM に収まらない、prompt が slot を借りる）では「refuses the start」のログを出して `return 1` となる。skip した層はサイズが小さくならないため、SKIP 指定だけで VRAM residency 要件を免れるわけではない。`engine/src/program/generate.cpp:5457-5464,9957-9984,12814-12843`。

## ログと測定値

SKIP の形式不正や範囲外番号は、次の共通警告の理由部分に表示され、通常 slot で起動を続ける。

```text
strata generate: WARNING: STRATA_EXPERT_NIBBLE is off for this start: <理由>; the expert slots stay GGUF blocks
```

警告の出力と fallback は `engine/src/program/generate.cpp:5457-5461`、理由文字列は `engine/include/strata/core/expert_nibble.hpp:263-266,353-355`。正常に有効化されたときの起動ログは変換された層数・format 別内訳・全 expert 分の追加 VRAM 見積りを出すが、SKIP 層数を独立して表示しない（`engine/src/program/generate.cpp:5475-5480`）。この変数単独の性能測定値はソース資料に記載されていない。

## 根拠

- `engine/include/strata/core/expert_nibble.hpp:221-235,238-269` — カンマ区切り parser、設定の一度限りの読み取り、空値と parse error。
- `engine/include/strata/core/expert_nibble.hpp:315-357` — 層の除外、変換対象条件、範囲検査。
- `engine/src/program/generate.cpp:3385-3435,5440-5480` — build / GPU / option 条件、起動時の fallback とログ。
- `engine/src/program/generate.cpp:9957-9989,12814-12843`、`engine/src/prefill/prefill.cpp:3915-3937` — residency と prompt 経路の起動条件。

`docs/OLDER_GPUS.md:200-231` は `STRATA_EXPERT_NIBBLE_SKIP=<layers>` を対象層選択として紹介しており、上記のソース上の使い方と一致する。測定値は同資料にも nibble 機能全体の条件付き測定のみで、この SKIP 変数固有の値ではないため、本書では記載しない。
