# `STRATA_FILE_RELEASE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Windows で `FileExpertSource` が管理するファイルマッピングから、GPU への転送が完了した expert の全ページ部分をワーキングセットから外すよう OS に依頼します。`experts.bin` のマッピングと、GGUF ファイル内の expert を直接参照するマッピングが対象です。CUDA と実験的 SYCL backend の実装にあります。Linux では同関数は何もせず 0 を返します。

## 値と判定

Windows の `FileExpertSource::release()` が初めて呼ばれた時に値を読み、関数内の `static const bool` に保存します。文字列全体が厳密に `1` の場合だけ有効です。数値変換や前後空白の除去はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| `1` | 有効 |
| 空文字、`0`、`01`、`1 `、`true` など | 無効 |

初回判定以降に環境変数を変更しても、このプロセスでは反映されません。非 Windows ビルドは値を読みません。

## 有効になる条件

- Windows であること。CUDA 実装は `_WIN32` の分岐内でのみ処理し、SYCL 実装も同じ Windows 分岐を持ちます。
- `FileExpertSource` のファイルマッピングが存在し、layer と expert の番号が範囲内であること。
- 対象ページが blob の中に完全に収まること。ページ境界をまたぐ端の部分と隣接 expert と共有するページは残ります。
- ページを別のバッファから読む場合でも、関数は pinned RAM や exchange buffer ではなく、マッピング上のファイル範囲を直接計算します。resident complement は直接コピー経路であり、ここで trim する対象ではありません。

`ArenaExpertSource` の解放処理は別実装で、この環境変数を参照しません。

## 実行時の詳細

`release(layer, expert)` は Windows で system page size の整数倍に切りそろえた範囲に `VirtualUnlock` を呼びます。通常の失敗は stderr に `FileExpertSource: cannot trim mapped pages for layer ... expert ... (... bytes, Windows error ...)` を出して 0 を返します。未ロック範囲についての `ERROR_NOT_LOCKED` は、このコードでは trim 成功として扱います。戻り値は trim を依頼したバイト数で、実際に RAM が回収された量の測定ではありません。

CUDA 実装は未マッピング状態も無効条件に含めます。SYCL 版にも同じ環境値判定と Windows の trim 処理があります。両 backend とも生成コードから `release()` が呼ばれ、初期 cache fill 後の GPU 保持 expert、および実行中の swap-in / prefill への貸し出し分について、コピー完了後に呼ぶ箇所があります。したがって、設定が有効でもファイルマッピングを使わない実行や、対象ページがない呼び出しでは何も解放されません。

## 文書との照合

`docs/DETAILS.md` は Windows の opt-in として説明し、1 台の Windows 11 laptop 構成で available RAM が増えた測定を記載しています。同じ説明で prefill throughput の低下、committed memory や物理 SSD read は減らなかったこと、OS が file cache を破棄する保証はないことも示しています。これらは記載された構成での測定であり、一般的な性能保証ではありません。

## 根拠

- 値判定、Windows guard、範囲検査、ページ trim、エラー出力: `src/core/expert_source.cpp:2545-2595`、`sycl/src/core/expert_source.cpp:1598-1648`。
- `FileExpertSource` の仮想メソッド宣言と Windows 向け説明: `include/strata/core/expert_source.hpp:687-689`、`sycl/include/strata/core/expert_source.hpp:565-567`。
- 初期 fill 後の解放呼び出し: `src/program/generate.cpp:6122-6137`、`sycl/src/program/generate.cpp:5779-5794`。
- 実行中の交換後および prefill 貸し出し後の呼び出し例: `src/program/generate.cpp:8327-8331,8777-8785`、`sycl/src/program/generate.cpp:7798-7804,8260-8269,10039-10048`。
- 説明と測定条件・制限: `docs/DETAILS.md:206-213`。
