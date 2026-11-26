# `STRATA_METAL_MAX_THREADS_CAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal runtime が compute pipeline の `maxTotalThreadsPerThreadgroup` から保存する上限を、正の小さい値に下げる検査用フック。Metal 自体の pipeline 上限や dispatch サイズは変更せず、Strata の `require_fit` が dispatch を事前検査する際の比較値だけを下げる。要求スレッド数がこの値を超えると、Metal が無言で dispatch を実行しないケースを検出して Strata が終了する。ヘッダーも `test hook` と明記している（`engine/metal/src/mtl_rt.mm:267-274`, `engine/metal/src/mtl_rt.h:69-76`）。

## 値と判定

`Context::pipeline` が `std::getenv` で設定有無を調べ、設定されていれば `std::atoi` で整数変換する。変換結果 `lim` が `0` より大きく、Metal が報告した `p.max_threads` より小さい場合だけ、その保存値を `lim` に置き換える（`engine/metal/src/mtl_rt.mm:267-274`）。

| 条件 | unset | 有効になる値（例） | 値が反映されない例 |
|---|---|---|---|
| Metal pipeline 作成時 | Metal が報告した `maxTotalThreadsPerThreadgroup` | 正の整数で、報告上限より小さい値（例: 実上限が 512 のとき `256`） | 空文字、`0`、`0anything`、`-1`、整数に変換できない文字列、実上限以上の値 |

全体文字列の妥当性検査やエラー報告はなく、`atoi` が先頭部分を変換する。したがって `256junk` や ` 256` は 256 として扱われ、`true` や `junk256` は 0 となって反映されない。符号付き整数の変換結果が正で、実上限未満かどうかだけを判定する。設定値が未設定でも空文字でもエラーや警告は出ず、上限は Metal の報告値のまま（同上）。

## 有効になる条件

- Apple/macOS 向け Metal runtime を使い、Strata が `Context::pipeline` を呼び出して pipeline を作る経路で評価される。Metal CMake project は macOS 専用で、CUDA/HIP/SYCL builds には含めないと記載している（`engine/metal/CMakeLists.txt:1-19`, `engine/metal/src/mtl_rt.mm:229-284`）。
- 変換値が正かつ実上限より小さい場合に限り検査上限が下がる。値が 0 以下、または実上限以上なら実際の比較上限は変わらない（`engine/metal/src/mtl_rt.mm:269-274`）。
- その pipeline を使う dispatch の threadgroup サイズが保存上限を超えると失敗する。サイズが上限以下、または 0 なら `require_fit` は通過する（`engine/metal/src/mtl_rt.mm:287-296`）。
- CLI 引数、モデル状態、サーバーモード、別環境変数による上書き・優先順位分岐は、この値の読み取り経路にはない（`engine/metal/src/mtl_rt.mm:229-284`）。

## 実行時の詳細

値は pipeline 作成時に読み取られ、その pipeline の `max_threads` に保存される。変数値を関数内 static に保存する処理はなく、新たに作る pipeline ではその時点の環境値が読まれる。一方、既存 pipeline は `max_threads` を保持するため、後から環境を変えても再作成されるまではその pipeline の判定値は変わらない。Metal engine の `Window::P` は pipeline を key ごとに cache し、cache miss のときだけ `cx_->pipeline(...)` を呼ぶ（`engine/metal/src/mtl_rt.mm:229-284`, `engine/metal/src/engine/window.cpp:327-333`）。

通常の dispatch は encoding 時に `require_fit` を実行し、graph 構築時と prompt-chain の一部も追加で検査する。indirect-command dispatch もコマンド登録前に同じ判定を行う（`engine/metal/src/mtl_rt.mm:287-296,414-416,583-600`, `engine/metal/src/engine/window.cpp:335-354`, `engine/metal/src/engine/prompt_chain.inc:271-281`）。

要求数が保存上限を超えた場合、stderr に kernel 名、上限、GPU 名、dispatch 箇所、要求数を含むメッセージを出し、flush 後に終了コード `6` で終了する。この環境変数だけを理由としたログはなく、実行スレッド数や生成結果を調整する処理でもない（`engine/metal/src/mtl_rt.mm:287-296`）。

## 根拠

- 読み取りと値の反映: `engine/metal/src/mtl_rt.mm:229-284`
- 上限超過時の判定と終了: `engine/metal/src/mtl_rt.mm:287-296`
- 通常・indirect dispatch の検査: `engine/metal/src/mtl_rt.mm:414-435,583-614`
- engine pipeline cache と graph 検査: `engine/metal/src/engine/window.cpp:327-354`
- prompt-chain 検査: `engine/metal/src/engine/prompt_chain.inc:271-281`
- Metal build の対象範囲: `engine/metal/CMakeLists.txt:1-19`
