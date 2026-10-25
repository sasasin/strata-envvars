# `STRATA_METAL_MATH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal の MSL ライブラリをコンパイルするときに、Strata が Metal コンパイルオプションへ safe math または fast math を指定します。既定は safe math です。`STRATA_METAL_MATH=fast` のときだけ fast math を指定します。`Context::compile()` の `fast_math` 引数は実装内で false に戻されるため、呼び出し側からの引数指定は無視されます。

この環境変数は Metal バックエンドのコンパイル時に参照されます。Metal 以外の backend に対する読み取り箇所はありません。

## 値と判定

値を数値や真偽値として parse せず、環境変数の文字列全体を `"fast"` と比較します。

| 環境変数の状態 | 選択される設定 |
|---|---|
| 未設定 | safe math |
| 空文字 | safe math |
| `fast` と完全一致 | fast math |
| その他（例: `FAST`, `fast1`, `1`, `true`, 前後に空白のある `fast`） | safe math |

大文字小文字を区別し、余分な文字や空白は許容しません。

## 有効になる条件

Metal の `Context::compile()` が呼び出される経路で有効です。エンジン初期化時に複数の Metal ライブラリをコンパイルし、prompt 用ライブラリも必要な経路でコンパイルします。環境変数は `compile()` の呼び出しごとに読み取られるため、値は各コンパイル時点で判定されます。キャッシュされた設定値はありません。

## 実行時の詳細

`metal/src/mtl_rt.mm:68-99` で `Context::compile()` は MSL ソースをまとめ、`MTLCompileOptions` を生成します。実装は引数 `fast_math` をまず false にし、`std::getenv("STRATA_METAL_MATH")` が返す文字列が `"fast"` と完全一致した場合に true にします。

- macOS 15 以降では `mathMode` に `MTLMathModeFast` または `MTLMathModeSafe` を設定します。
- それより前では `fastMathEnabled` に同じ判定結果を設定します。

ソースコメントは safe math の意図を「演算の再結合を行わず、各 window の token が one-token call と bitwise で一致する」ことと説明し、kernel 側では contraction を明示的な FMA として記述するとしています（`metal/src/mtl_rt.mm:79-83`）。ただし、この調査では fast math と safe math の生成結果の差や token 一致性を実行して検証していません。コンパイル失敗時は Metal コンパイラのエラーを含む `mtl: compile failed (...)` を stderr に出して終了コード 3 で終了します（同 `:90-96`）。環境変数の値自体を報告するログはありません。

実エンジンでは `metal/src/engine/window.cpp:438-444` で decode 用のライブラリ群をコンパイルし、prompt 経路では同 `:2036-2039` で prompt 用ライブラリ群をコンパイルします。どちらも同じ `Context::compile()` を通ります。

## 根拠

- `metal/src/mtl_rt.h:83-88` — `compile()` の引数と、safe math が既定で環境変数 `=fast` が例外という宣言。
- `metal/src/mtl_rt.mm:68-99` — 引数の上書き、環境変数の完全一致判定、OS バージョン別のオプション設定、コンパイル失敗時の出力。
- `metal/src/engine/window.cpp:438-444,2036-2039` — エンジンの decode と prompt における呼び出し。
- `docs/DETAILS.md` — `STRATA_METAL_MATH` の説明や測定値は確認できませんでした。
