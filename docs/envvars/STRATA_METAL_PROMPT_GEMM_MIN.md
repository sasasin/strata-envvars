# `STRATA_METAL_PROMPT_GEMM_MIN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンで expert を SSD からストリーミングしている場合に、matrix-unit prompt GEMM 経路を選ぶ最小 prompt 行数を指定します。既定値は64行です。しきい値以上なら prompt を `STRATA_METAL_PROMPT_CHUNK` 相当の chunk に分けて `prompt_chunk()` で処理し、未満なら decode window 経路に進みます。コードコメントではこの二経路の数値が異なると説明されています。

この変数はストリーミング経路だけで参照されます。resident model の prompt 経路の最小行数は別変数 `STRATA_METAL_PROMPT_MIN`（既定32）で決まります。

## 値と判定

値は `std::atoll()` で整数に変換されます。文字列全体の妥当性検査、fallback、clamp はありません。

| 設定 | しきい値 | ストリーミング時の結果 |
|---|---:|---|
| unset | 64 | prompt 行数 `n >= 64` で GEMM 経路の条件を満たす |
| 数値文字列 | 変換された `long long` 値 | `n >= しきい値` で条件を満たす |
| 空文字・数値に変換できない文字列 | 0 | 通常の正の `n` なら条件を満たす |
| 数字の後に文字がある文字列 | 数字の先頭部分 | 例: `64rows` は64として扱われる |
| 負数 | 負の値 | 通常の正の `n` なら条件を満たす |

`atoll` が変換できない文字列を0にするため、無効値を既定64へ戻す処理はありません。比較は `n >= mn` であり、行数がしきい値と等しい場合も GEMM 経路の条件を満たします。

根拠: `metal/src/engine/window.cpp:2561-2567`。既定値と同じ変換を持つ `Window::prompt_gemm_on()` もありますが、この関数の呼び出し箇所は HEAD 内に見つからず、実際の prompt 選択は `prompt_run_rows()` の読み取りで行われます（同 `:2007-2017,2555-2578`）。

## 有効になる条件

次の条件を満たす場合に限り、このしきい値が経路選択に使われます。

- Metal prompt の実行時に decode window が作成済み。
- `STRATA_METAL_PROMPT=window` が指定されていない。
- window が streaming mode。
- `STRATA_METAL_PROMPT_GEMM` が文字列全体で `0` ではない。
- prompt 行数 `n` がこの変数から得た値以上。

`STRATA_METAL_PROMPT_GEMM` が unset の場合は GEMM 経路を許可します。空文字や `00` も文字列 `0` と一致しないため許可します。一方、`STRATA_METAL_PROMPT=window` は streaming / resident のどちらでも GEMM の選択分岐を飛ばし、decode window 経路を使います。

streaming では、このしきい値を下回る prompt は `Window::run()` と `commit()` を最大 `MAXT` 行ずつ呼ぶ fallback になります。resident mode では本変数は使われず、`STRATA_METAL_PROMPT_MIN` が既定32行で `Window::prompt()` の選択を決めます。

別の条件として、streaming arena 初期化時の `STRATA_METAL_PROMPT_GEMM` が GEMM buffers の初期化と arena の slot 数を決めます（有効なら `prompt_gemm_init()` を行い、arena に576 slots、無効なら64 slots）。したがって、本変数だけでは GEMM 機能を有効化できません。

## 実行時の詳細

`prompt_run_rows()` は各 prompt 呼び出し時に本変数を `getenv()` し、`atoll()` で変換します。この読み取り値は static cache されません。閾値を通過し、他の条件も満たすと、不足時は prompt buffers を初期化し、`prompt_region(true)` の後に入力を chunk ごとに `prompt_chunk()` へ渡します。各 chunk 後に `on_chunk` があれば呼び、最後に `prompt_region(false)` に戻します。初期化または chunk 処理が失敗すれば `false` を返します。

Strata の `docs/MAC.md` は `STRATA_METAL_PROMPT=window` を slow, exact fallback と記し、streaming Mac での prompt chunk サイズと測定値を掲載しています。一方、この変数のしきい値を変えた比較測定や速度・出力差の定量値は同資料にありません。ソースコメントには prompt GEMM と window の数値が異なるとありますが、差の大きさや正確性はここでは断定できません。

## 根拠

- `metal/src/engine/window.cpp:2555-2587` — 値の読み取り、streaming 条件、GEMM / fallback の分岐と実処理。
- `metal/src/engine/window.cpp:1194-1209` — `STRATA_METAL_PROMPT_GEMM` による streaming arena の buffer 初期化。
- `metal/src/engine/window.cpp:1970-1977` — prompt GEMM の概要、window 経路との数値差、およびこのしきい値の既定64というコメント。
- `metal/src/engine/window.cpp:2007-2017` — 同じ変数を読む補助関数。現在の呼び出し箇所はない。
- `metal/src/engine/prompt_chain.inc:8-11` — resident 用 `STRATA_METAL_PROMPT_MIN` との区別、prompt chain の chunk 説明。
- `docs/MAC.md:110,183-195` — streaming Mac の chunk 測定と公開スイッチ一覧。本変数のしきい値測定は記載されていない。
