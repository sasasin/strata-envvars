# `FNX_PF_ATT_PIECES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Flash-Next split engine の prompt attention で、各 chunk の attention partial を他カードへ渡す行分割数を指定する。未設定時は 4 分割。分割した piece の計算が終わるたびにその piece の partial を送るため、後続 piece の計算と送信を重ねられる。attention の計算式や結果の選択を変える設定ではなく、交換の分割数を変える。実装は `Engine::Pf::att_pieces` と `pf_attn_start()` にある（`engine/src/split/src/prefill.cu:369-373, 772-783`）。

## 値と判定

`Engine::prefill_alloc()` が各カードの `Pf` を初期化するときに `std::getenv` で読み、設定がなければメンバーの初期値 `4` を維持する。設定値は `std::strtol(..., 10)` で十進数として変換され、少なくとも1桁を変換でき、変換後の末尾が `\0` で、値が1〜8のときだけ受理される。`strtol` のため先頭の空白と符号は変換される（例: `  +2` は受理）。後続の空白、余分な文字、小数点、空文字は受理されない。範囲外、変換不能、または末尾文字がある場合は例外になる（`engine/src/split/src/prefill.cu:317, 371, 1028-1034`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| split engine の attention exchange | 既定の4 | `1`〜`8`、`+2`、` 2` | 空文字、`0`、`9`、`-1`、`1x`、`1 `、`1.0` |

CLI 引数、設定ファイル、または別の環境変数による優先上書きは、この値の読み取り・代入経路にはない。明示値は 1〜8 に clamp されず、範囲外なら初期化に失敗する（`engine/src/split/src/prefill.cu:1028-1034`）。

## 有効になる条件

- `engine/src/split/src/prefill.cu` が CUDA または HIP としてビルドされた sFNX split engine であること。同ファイルは両 backend のソースに含まれ、HIP build では同じ `prefill.cu` を HIP 言語として扱う（`engine/src/split/CMakeLists.txt:76-92`）。
- split prompt path の attention 層を処理し、`FNX_PF_ATTN_DEC` が無効であること。この場合 `pf_attn_start()` が partial を計算・分割送信し、後段で `pf_attn_finish()` が交換完了を待って merge する。`FNX_PF_ATTN_DEC` が有効なら attention 層は別の `attn()` 経路を使い、この変数で設定した分割送信を呼ばない（`engine/src/split/src/prefill.cu:1022, 1671-1689, 1701`）。
- 値の妥当性検査自体は `Pf` 初期化で行われ、上記の attention 経路が実際に呼ばれなくても、split engine 初期化時に無効値なら失敗する（`engine/src/split/src/engine.cu:317-318`, `engine/src/split/src/prefill.cu:854-865, 1028-1034`）。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` がカードごとの `Pf` を作り、そこで値を読み取って `att_pieces` に保存する。そのため読み取りは各カードの初期化時であり、prompt chunk ごとの再読み込みや実行中の環境変更の追跡はない（`engine/src/split/src/engine.cu:317-318`, `engine/src/split/src/prefill.cu:854-865, 1028-1034`）。

attention exchange では各 piece の行範囲を `r0 = C*i/n`, `r1 = C*(i+1)/n` として chunk 行数 `C` を `n = att_pieces` 個に分割する。piece ごとに `attn_prompt()` を起動し、完了 event を送信 stream が待ってから `pf_attn_send()` が部分結果を送信する。merge 側は全 piece の flag と送信完了を待った後に `attn_prompt_merge()` を呼ぶ（`engine/src/split/src/prefill.cu:762-783, 802-820`）。コードは `C` が piece 数で割り切れない場合も上記の整数除算で連続した範囲を作る。piece 数による性能差や出力同一性の測定は、この checkout の資料では確認できない。

## ログと測定値

有効値を設定したこと自体を知らせる専用ログはない。無効値では `FNX_PF_ATT_PIECES: 1 to 8, not '<値>'` の例外を投げる。Engine 構築中の例外は `sfnx` の `fail()` に渡り、標準出力へ `ERR <例外>`、標準エラーへ `sfnx: failed: <例外>` を出して終了コード1で終了する（`engine/src/split/src/prefill.cu:1031-1032`, `engine/src/split/tools/sfnx.cpp:1094-1102, 1123-1135`）。

## 根拠

- `engine/src/split/src/prefill.cu:317-373` — 上限8、既定値4、piece 設定の保持。
- `engine/src/split/src/prefill.cu:762-820` — piece ごとの attention 計算・送信と merge の待ち合わせ。
- `engine/src/split/src/prefill.cu:854-865, 1022-1034, 1671-1701` — 初期化時の読み取り、値検証、attention 分岐。
- `engine/src/split/src/engine.cu:317-318` — Engine 構築時の prompt buffer 初期化。
- `engine/src/split/CMakeLists.txt:76-92` — CUDA/HIP の split build へのソース登録。
- `engine/src/split/tools/sfnx.cpp:1094-1102, 1123-1135` — 初期化例外の出力と終了。
