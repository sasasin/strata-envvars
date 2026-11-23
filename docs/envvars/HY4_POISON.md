# `HY4_POISON`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の GPU バッファ割り当て後に全バイトを `0xFF` で埋める診断用スイッチ。通常は初期化しない `dalloc<T>` の割り当て領域と、MLA workspace の新規確保・拡張領域を poison し、未初期化 device memory の読み取りを見つける目的がコードコメントに記されている。値による推論設定や生成戦略の選択は行わない。該当する実装は `Runner::dalloc` と `Runner::ensure_mla_ws`（`engine/src/hy4flash/run/hy4_graph.hip.h`）に限られる（同ファイル:188-198, 1272-1276）。

このファイルは CMake の `strata-hy4` ターゲットに含まれ、CUDA または HIP 言語としてコンパイルされる。したがって適用先はこのエンジンの CUDA/HIP ビルドであり、ビルドオプション `STRATA_BUILD_HY4` は既定 OFF、かつ CUDA/HIP のいずれかが必要（`engine/CMakeLists.txt:846-851, 884-891`）。

## 値と判定

両読み取り箇所とも `getenv("HY4_POISON")` の戻り値をポインタとして直接条件判定する。数値・文字列の変換や内容比較はせず、環境変数が存在すれば有効、未設定なら無効。明示的な空文字も非 NULL なので有効となる。`0`、`false`、`0anything`、大文字小文字、前後空白を含む任意の設定値も、設定されている限り有効である。値域・境界・無効文字列による fallback はない（`engine/src/hy4flash/run/hy4_graph.hip.h:194, 1275`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata-hy4` CUDA / HIP | poison しない | 空文字、`0`、`1`、`false` など、環境変数が存在する任意の値 | なし（値の内容は判定しない） |

## 有効になる条件

- `STRATA_BUILD_HY4` を有効にして作られた `strata-hy4` の CUDA または HIP 実行経路であること。CMake では CUDA が有効なら GPU ソースを CUDA 言語にし、それ以外は HIP 言語にする（`engine/CMakeLists.txt:848-851, 884-891`）。
- 実行中に `Runner::dalloc<T>` が呼ばれるか、`Runner::ensure_mla_ws` が現在の workspace 容量を超える領域を確保すること。workspace の必要量が既存容量以下なら早期 return し、この関数内で poison しない（`engine/src/hy4flash/run/hy4_graph.hip.h:188-194, 1272-1276`）。
- サーバーモード、CLI 引数、モデル状態、別の環境変数による追加条件は、この変数を読む箇所にはない。索引記載以外の読み取り箇所は同ファイルの上記 2 箇所だけ。

## 実行時の詳細

`dalloc<T>(n)` は `hipMalloc` の成功後、環境変数が設定されていれば `n * sizeof(T)` バイトを `hipMemset(..., 0xFF, ...)` で埋めてからポインタを返す。従って型に関係なく割り当て領域全体が対象になる（`engine/src/hy4flash/run/hy4_graph.hip.h:1272-1276`）。

`ensure_mla_ws(need)` は既存容量が不足した場合、stream を同期し、旧領域を解放して `need + need/4` バイトを確保する。その新領域も設定時には `0xFF` で埋める。その後 `mla_ws_gen` を進め、`HY4_HAS_GRAPHS` が有効ならグラフをクリアする。workspace 確保は Runner 初期化時と MLA 処理から呼ばれ、キャプチャ中の呼び出しでは MLA 処理側が確保を避ける（同ファイル:188-198, 1743-1747, 2166-2168, 3069-3070）。

読み取り結果を static や Runner の状態に保存しない。各 `dalloc` と workspace の拡張時にその都度 `getenv` を評価するため、実行中に環境が変更された場合、その後の割り当てでは新しい状態が使われるが、すでに確保済みの領域は再 poison されない（同ファイル:188-194, 1272-1276）。子プロセスへの転送処理はこの変数の読み取り箇所にはない。

## ログと測定値

成功時に `HY4_POISON` 専用のログは出さない。割り当てや memset の失敗は `HCK` を通る。失敗時は `HIP error %d (%s) at %s:%d\n` を stderr に出して `exit(3)` する（`engine/src/hy4flash/run/hy4_graph.hip.h:190-194, 1273-1275`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。Strata の資料にこの変数に関する測定値は確認できない。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:188-198` — MLA workspace の再確保条件、同期、サイズ、poison、グラフ無効化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1272-1276` — 全型共通の device allocation と poison。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1743-1747, 2161-2168, 3069-3070` — workspace 確保箇所。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — GPU API エラー時の stderr 出力と終了コード。
- `engine/CMakeLists.txt:846-851, 884-891` — HY4 ターゲットの有効条件と CUDA/HIP の選択。
