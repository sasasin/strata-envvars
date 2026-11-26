# `STRATA_METAL_MATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal runtime の `mtl::Context::compile_try` が MSL ライブラリをコンパイルするとき、Metal の数学モードを選びます。既定は safe math で、環境変数を文字列全体で `fast` と指定した場合に限り fast math になります。`Context::compile` の `fast_math` 引数は読み取り後に必ず false で上書きされるため、呼び出し側からの指定はこの実装では反映されません（`engine/metal/src/mtl_rt.h:96-102`、`engine/metal/src/mtl_rt.mm:170-177, 209-220`）。

この読み取りは Objective-C++ の Metal runtime にある MSL ソースコンパイル経路のものです。別の Metal runtime 経路 `engine/metal/src/gpu/runtime.cpp` は `MTL::MathModeSafe` を直接設定しており、この変数を読みません（`engine/metal/src/gpu/runtime.cpp:577-588`）。したがって、この環境変数が Strata の全 Metal コンパイル経路に適用されるとは言えません。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば値全体を `std::string` にして、大文字小文字を区別する完全一致 `== "fast"` で判定します。数値・真偽値としての変換や trim はありません。未設定時は `fast_math=false`、設定済みでも文字列が正確に `fast` でなければ false です（`engine/metal/src/mtl_rt.mm:209-218`）。

| 条件 | unset | fast になる値 | fast にならない設定値 |
|---|---|---|---|
| `mtl::Context::compile_try` を通る MSL コンパイル | safe | `fast` | 空文字、`0`、`1`、`true`、`FAST`、` fast`、`fast `、`0anything` など。いずれも safe |

macOS 15 以降では判定結果を `MTLMathModeFast` / `MTLMathModeSafe` に設定し、それより前では `fastMathEnabled` に bool を設定します。どちらの分岐でも値の判定規則は同じです（`engine/metal/src/mtl_rt.mm:213-218`）。

## 有効になる条件

- `engine/metal/src/mtl_rt.mm` の `mtl::Context::compile_try` が実行されること。通常のエンジンでは `metal window` のライブラリ群を `cx_->compile(...)` で順次コンパイルする箇所がこの経路を呼びます（`engine/metal/src/engine/window.cpp:790-798`）。
- 変数が未設定または `fast` 以外の値なら、safe math のままです。CLI 引数や別環境変数による上書きは、この読み取り箇所にはありません（`engine/metal/src/mtl_rt.mm:209-218`）。
- GPU runtime 側でソースからライブラリを作る `metal::pipeline` 経路は別実装で、safe math を直接設定します。この経路では `STRATA_METAL_MATH=fast` は参照されません（`engine/metal/src/gpu/runtime.cpp:577-588`）。

## 実行時の詳細

値は `compile_try` を呼ぶたび、各 MSL ライブラリのコンパイル直前に読み直されます。関数内 static cache はありません。実行中に環境値が変われば、その後の `compile_try` には新しい値が使われますが、すでに作成済みの Metal library のコンパイル設定は遡って変わりません。呼び出し側の `fast_math` 引数は毎回 false に戻され、環境値だけで最終値が決まります（`engine/metal/src/mtl_rt.mm:183-220`）。

通常の `Context::compile` は `compile_try` が失敗すると GPU 名・macOS バージョン・ファイル名・コンパイラの説明を stderr に `mtl: compile failed (...)` の形式で出し、終了コード 3 でプロセスを終了します。`compile_try` 自体は失敗時に `-1` を返し、`why` にエラー説明を設定します。環境変数の値が無効という理由での警告やエラーはありません（`engine/metal/src/mtl_rt.mm:170-179, 219-223`）。

## 根拠

- 読み取り、safe math の既定、値判定、OS バージョンごとのオプション設定、コンパイル失敗: `engine/metal/src/mtl_rt.mm:170-227`
- `compile` 引数の説明と宣言: `engine/metal/src/mtl_rt.h:96-103`
- 通常の Metal window エンジンによる `compile` 呼び出し: `engine/metal/src/engine/window.cpp:790-798`
- 別 runtime の safe math 設定: `engine/metal/src/gpu/runtime.cpp:577-592`
- Metal runtime / エンジン構成の説明: `docs/MAC.md:296-304`
