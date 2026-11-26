# `STRATA_DF2_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

これは DFlash2 drafter の処理段階を省略する計測用フックです。`skip_part()` が指定名を含む値を見つけると、DFlash2 の context 更新や draft block の一部計算を実行しません。コメントにも measurement only とあり、通常の推論品質を保つ設定ではありません。DFlash2 の候補生成だけに作用し、対象モデルの重みや検証側の計算を切り替えるものではありません（`engine/src/core/dflash2.cpp:142-146,514-537,539-618`）。

## 値と判定

`skip_part()` の初回呼び出し時に `std::getenv` の結果を関数内 `static const std::string` に一度コピーし、以後はその文字列に対する大文字小文字を区別する部分文字列検索 `list.find(what)` を使います。カンマ区切りの解析、真偽値変換、空白除去、数値変換はありません。したがって、空文字と未設定はどちらも何も省略せず、値に対象名がどこかに含まれていれば有効です（`engine/src/core/dflash2.cpp:143-146`）。

| 値に含まれる文字列 | 省略する段階 |
|---|---|
| `ctx` | DFlash2 の context 更新全体（`record_context` の処理） |
| `attn` | 各 block の attention 計算 |
| `head` | DFlash2 draft head の logits 計算 |
| `mlp` | gate/up および down projection の GEMM |
| `qkvo` | q/k/v projection と o projection の GEMM |
| `tiny` | attention/MLP convolution の kernel projection GEMM |
| `small` | convolution、norm、RoPE、SwiGLU を含む補助処理 |

実際の判定対象は各行の文字列全体でなく部分文字列です。たとえば `attn`、`0attn`、`attn,head` は `attn` 段階を省略し、`ATTN`、`true`、`false`、`0`、空文字はどの段階名も含まないため省略しません。`small` と `tiny` も実装上の判定名ですが、コメントに示された例の一覧にはありません（`engine/src/core/dflash2.cpp:142-146,557-584`）。

## 有効になる条件

- 実行ファイルに `Dflash2Drafter` が組み込まれ、DFlash2 の `record_context()` または `record_block()` が実行される必要があります。通常の MTP 経路では参照されません（`engine/src/core/dflash2.cpp:514-537,539-618,1170-1208`; `engine/src/program/generate.cpp:8152-8154`）。
- 共通実装 `engine/src/core/dflash2.cpp` は CUDA/HIP の engine と SYCL engine に組み込まれ、split engine でも DFlash2 target が作られると同じ実装が使われます（`engine/sycl/CMakeLists.txt:297-301`; `engine/src/split/CMakeLists.txt:104-114`）。Metal の独立した DFlash2 実装にはこの `skip_part()` の読み取り箇所がありません。
- `STRATA_DF2_PROFILE=1` の計測経路でも `record_context()` / `record_block()` が直接呼ばれるため、この省略判定は有効です。`STRATA_DF2_PROFILE` 自体は別の設定です（`engine/src/core/dflash2.cpp:296,1170-1208`）。
- CLI 引数や別の環境変数による `STRATA_DF2_SKIP` の上書きは、この読み取り箇所にはありません。DFlash2 が起動しない経路ではこの変数は使われません。

## 実行時の詳細

値は `skip_part()` が初めて呼ばれた時点でキャッシュされます。通常は初回 DFlash2 draft の graph capture 中、または `STRATA_DF2_PROFILE=1` の最初の直接実行中です。その後にプロセス環境を変更しても、このキャッシュ値は更新されません。全 DFlash2 drafter インスタンスがこの翻訳単位の同じ static 値を参照します（`engine/src/core/dflash2.cpp:143-146,621-655,1174-1208`）。

段階を省略しても後続処理は一律には止まりません。たとえば `ctx` は `record_context()` を直ちに成功で返し、context 由来の K/V 更新をしません。一方 `head` は head logits 計算だけを飛ばした後も `df2_topk()` と selector を実行します。`attn`、`mlp`、`qkvo`、`tiny`、`small` も各段階の処理だけを条件付きで飛ばし、その後の処理と graph capture は続きます。したがって、これらの指定はモデル計算の一部を欠いた draft 候補・確率を生み得る診断用操作であり、通常の DFlash2 出力と同等とは扱えません（`engine/src/core/dflash2.cpp:514-537,539-618`）。

この関数自体は値の検証、警告、失敗返却を行いません。変数に一致したかどうかの専用ログもありません。計測イベントは省略分岐の前後で引き続き stamp されます。別途 profile が有効なら終了時に `strata dflash2 profile (%lld rounds, ms per round, total %.3f):` から始まる段階別時間が stderr に出ますが、値や省略理由は表示しません（`engine/src/core/dflash2.cpp:148-178,557-618`; `engine/src/core/dflash2.cpp:42-43`）。

## ログと測定値

`STRATA_DF2_SKIP` 専用のログ・警告・終了経路はありません。コメントは、指定した計算段階を省いて graph の GPU 時間を読めるようにする意図を示しますが、この変数に関する測定値は `docs/DETAILS.md` で確認できません（`engine/src/core/dflash2.cpp:142-146`; `docs/DETAILS.md:1237,1591-1595`）。

## 根拠

- `engine/src/core/dflash2.cpp:142-146` — 値の読み取り、初回キャッシュ、部分文字列判定。
- `engine/src/core/dflash2.cpp:514-537,539-618` — `ctx` および block 内各段階の省略対象と後続処理。
- `engine/src/core/dflash2.cpp:621-655,1170-1208` — graph capture と profile 直接実行からの呼び出し。
- `engine/sycl/CMakeLists.txt:297-301`; `engine/src/split/CMakeLists.txt:104-114` — 共通実装を含む build target。
- `docs/DETAILS.md:1237,1591-1595` — DFlash2 関連資料の確認箇所。本変数の説明・測定値はなし。
