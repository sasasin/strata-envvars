# `STRATA_METAL_STUBS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal engine にまだ実装がない kernel entry point が呼ばれたときの `strata::metal_engine::missing()` の動作を切り替えます。通常は不足している entry point 名を stderr に出して終了コード 86 でプロセスを止めます。値を正確に `log` とすると、その entry point 名を一度だけ stderr に記録して関数から戻ります。これは不足実装へ到達する経路を調べるための診断用フックであり、計算結果を得る用途ではありません。

## 値と判定

値は文字列全体で大小文字を区別して比較されます。数値変換や前後空白の除去はありません。

| 環境変数の状態 | `log_only` | `missing()` の動作 |
|---|---:|---|
| 未設定 | false | entry point 名を stderr に出し、stderr を flush して `_Exit(86)` |
| `log` | true | `strata metal: STUB <entry point 名>` を同じ名前につき初回だけ stderr に出し、戻る |
| 空文字、`LOG`、`1`、`log `、その他の値 | false | entry point 名を stderr に出し、stderr を flush して `_Exit(86)` |

## 有効になる条件

この環境変数を読む実装は `metal/src/engine/missing.cpp` にあります。Metal 用 CMake 設定は `metal/src/engine/*.cpp` を `strata_metal_kernels` に含め、そのライブラリを `strata` 実行ファイルへリンクします（`metal/CMakeLists.txt:103-123`）。したがって、この設定はその Metal engine の実行経路に適用されます。CUDA/HIP/SYCL engine 向けの同名設定の読み取りは、この調査対象ソース内では確認できません。

## 実行時の詳細

判定は `missing()` 内の関数ローカル `static const bool` で初回呼び出し時に一度だけ行われます。その後プロセス内で環境を書き換えても判定は更新されません。子プロセスへの値の継承・上書き処理は、この変数の実装箇所にはありません。

`STRATA_METAL_STUBS=log` の場合、mutex で保護した `std::set` に entry point 名を記録し、同じ名前については一度だけログを出します。`missing()` 自体は戻るため、呼び出し元の stub が戻り値を持つ場合は、その stub に書かれた既定値（例: `return {}`）が返り、出力先バッファ等は実装されません。よって処理が続く可能性はありますが、このモードのログと戻り値を有効な推論結果として扱うことはできません。既定動作はログを flush した後に `_Exit(86)` するため、通常の終了処理や stack unwinding を行いません。

なお `missing.cpp` には共有 host loop 用の空の control vector `cvec()` もありますが、これは `STRATA_METAL_STUBS` の判定とは独立しており、常に `loaded()` が false となる空オブジェクトを返します。

## 根拠

- `metal/src/engine/missing.cpp:14-28` — 環境変数の完全一致判定、static cache、既定の stderr 出力と終了コード、`log` 時の重複抑制。
- `metal/src/engine/missing.cpp:32-40` — 同じファイル内の control vector stub。環境変数による切り替えではないこと。
- `metal/CMakeLists.txt:103-123` — Metal engine のソース glob、kernel library、`strata` 実行ファイルへのリンク。
