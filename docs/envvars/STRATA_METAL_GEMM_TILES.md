# `STRATA_METAL_GEMM_TILES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の非ストリーミング prompt-chain が実行する dense GEMM について、Apple M5 系で一部行列のタイル寸法を変える最適化を無効にできます。無効にすると従来の 64 系 tile を使います。Metal 以外の backend にはこの読み取り箇所がなく、Metal でも M5 系以外では tile の変更は行われません。

## 値と判定

`gemm_tile()` の最初の呼び出し時に環境変数を読み、値全体が文字列 `"0"` と一致するかを比較します。数値変換や前後空白の除去はありません。

| 環境値 | `off` | M5 系かつ対象形状の結果 |
|---|---:|---|
| 未設定 | false | 下表の最適化を適用 |
| 空文字 | false | 下表の最適化を適用 |
| 厳密に `0` | true | helper は tile を変更せず既定値を維持 |
| その他（例: `00`, `0 `, `false`, `1`） | false | 下表の最適化を適用 |

この判定結果は関数内の `static const bool` に保存されます。プロセス内で初回に判定した後の環境変更は再評価されません。

| Metal device 名 | GEMM の出力幅 `Nn` と内積幅 `K` | `STRATA_METAL_GEMM_TILES` が厳密に `0` でない場合の tile `(tm, tn)` |
|---|---|---|
| `Apple M5` で始まる名前 | `Nn == 2560 && K == 6144` | `(64, 128)` |
| `Apple M5` で始まる名前 | `Nn >= 6144`（上の条件を除く） | `(128, 64)` |
| その他の形状またはその他の device | すべて | 呼び出し元の既定値を維持。通常 `Nn > 64` なら `(64, 64)`、`Nn <= 64` なら `(64, 32)` |

## 有効になる条件

- `STRATA_GPU_METAL` で組み込まれた Metal backend が使われ、Metal の prompt-run が呼ばれる必要があります。Metal エンジンのビルドには Metal C++ headers が必要です。
- `prompt_run_rows()` が `STRATA_METAL_PROMPT=window` で window 経路を強制していないこと、および通常経路では `STRATA_METAL_PROMPT_MIN`（既定 32）以上の prompt 行数であることが必要です。
- 上記通常経路でも `g_window->streaming()` が false の場合に `Window::prompt()`（prompt-chain）へ進みます。ストリーミング時には別の prompt GEMM 経路または window 経路となり、この文書の `gemm_tile()` は呼ばれません。
- 呼び出し元の GEMM 既定値を変更できるのは device 名が `Apple M5` で始まり、表記した形状に一致する場合だけです。M4 などその他の device 名では設定値が `0` 以外でもタイル選択は既定値のままです。
- CLI 引数によるこの値の上書きは見つかりません。プロンプト経路自体には `STRATA_METAL_PROMPT`、`STRATA_METAL_PROMPT_MIN`、ストリーミング経路には `STRATA_METAL_PROMPT_GEMM` と `STRATA_METAL_PROMPT_GEMM_MIN` が関与します。

## 実行時の詳細

非ストリーミングの `Window::prompt()` は prompt を chunk に分け、各 chunk の prompt-chain (`pc_chunk`) で dense GEMM を行います。GEMM helper はまず `(64, Nn <= 64 ? 32 : 64)` を既定値にし、`gemm_tile()` が条件に応じて `tm` / `tn` を上書きします。その寸法から `gemm_f16_<tm>_<tn>_4` というパイプライン名を作り、出力グリッドも同じ tile 寸法で計算して dispatch します。

この環境変数を読む箇所は `metal/src/engine/window.cpp` の `gemm_tile()` 内の一箇所です。設定値による専用ログ、警告、終了・失敗経路はありません。処理失敗時は通常の prompt-chain / prompt-run のエラー経路を通ります。ソースコメントは tile の違いについて bit-identical と記し、M5 Max の測定例を挙げていますが、本調査では性能を再測定していません。

## 根拠

- 候補名の全参照と値判定、M5 device 判定、形状ごとの tile: `metal/src/engine/window.cpp:72-80`。直接参照はこの実読み取りと直前のコメントだけです。
- prompt-run が通常の prompt-chain、ストリーミング用 GEMM、window 経路を選ぶ条件: `metal/src/engine/window.cpp:3045-3075`。
- 通常 prompt-chain の chunk 分割と失敗伝播: `metal/src/engine/prompt_chain.inc:435-461`。
- prompt-chain GEMM が既定 tile を用意し、対象 helper を呼んでパイプライン名・grid を選択する箇所: `metal/src/engine/prompt_chain.inc:165-171`。実際の dense GEMM 呼び出し例: `metal/src/engine/prompt_chain.inc:228-252,261-265,301-312`。
- ストリーミング時に使用される別 prompt GEMM の既定 tile とカーネル選択（対象 helper を経由しない）: `metal/src/engine/window.cpp:2624-2629`。
- Metal backend のビルド定義と Metal C++ headers がない場合の非ビルド条件: `metal/CMakeLists.txt:51-61`。Verifier から Metal window を呼ぶ条件: `src/core/verify.cpp:801-805,3056-3060`。
- 関連資料: `docs/MAC.md:250` は `STRATA_METAL_PROMPT=window` の fallback を記載しています。`docs/DETAILS.md` に `STRATA_METAL_GEMM_TILES` の説明は見つかりませんでした。
