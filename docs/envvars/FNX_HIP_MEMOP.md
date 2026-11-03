# `FNX_HIP_MEMOP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP 版 `strata-split` のプロンプト経路で使う、stream 順序付き 32-bit フラグの書き込み・待機実装を選びます。既定はフラグ操作を HIP kernel で行い、環境変数を文字列 `native` に完全一致させた場合は HIP runtime の `hipStreamWriteValue32` / `hipStreamWaitValue32` を呼びます。Strata 本体の通常エンジン全般の設定ではありません。

## 値と判定

読み取り箇所は `fnx_native_memops()` 内の一か所です。`std::getenv` の戻り値を `std::strcmp(e, "native")` で比較します。

| 値 | 選択される実装 |
|---|---|
| 未設定 | kernel（既定） |
| 空文字 | kernel |
| 大文字小文字を含め、値全体が `native` と一致 | HIP runtime の native stream memory 操作 |
| その他すべて（例: `Native`, `1`, `native `） | kernel |

数値変換、真偽値解釈、前後空白の除去はありません。CLI 引数や別の環境変数による上書きは、この実装にはありません。

## 有効になる条件

- HIP backend で `STRATA_BUILD_SPLIT=ON` にして `strata-split` をビルドした場合に限り、この HIP shim が組み込まれます。split エンジンは既定ではビルドされず、HIP split の CMake 条件は Linux、HIP のみ（CUDA との同時有効化なし）です。対象コードオブジェクトは gfx1100/1101/1102/1103、gfx11-generic、gfx1200、gfx1201 を許容します。
- CUDA 版 `strata-split` は別の CUDA driver API を使うため、この HIP 用判定は通りません。通常の Strata エンジンにもこの読み取りはありません。
- 値が `native` でも、stream フラグ操作が呼ばれない実行では効果がありません。呼び出しはプロンプトの ring と attention flag の書き込み・待機経路にあります。

## 実行時の詳細

`fnx_native_memops()` の結果は関数内の `static const bool` に保存されます。最初の呼び出しで環境を評価し、そのプロセスで以降に環境を変えても再評価しません。書き込み wrapper は native 選択時に `hipStreamWriteValue32`、既定側では `fnx_memop_write` kernel を stream に enqueue し、後者は前後に system fence を実行します。待機 wrapper も同様に native API または `fnx_memop_wait` kernel を使います。kernel 側の待機はフラグ値が要求値以上になるまで spin し、`clock64()` の差が `8000000000` を超えるとループを抜けます。

これらの wrapper は prompt ring の信号・待機と attention 交換フラグから呼ばれます。HIP API がエラーを返した場合、`cud()` が `prefill: <操作名>: <HIP error string>` 形式の例外にします。kernel 待機の時間上限に達した場合、kernel 自体は戻ります。プロンプト処理は stream 完了を最大120秒待つ経路と ring データ検査を持ち、完了しない場合は `prefill: a pass did not finish in 120 s (a ring step's flag never came?)`、検査エラーが立った場合は `prefill: ring error <数値>` を例外にします。これらはフラグ待機の失敗を観測し得る経路ですが、環境値の不正そのものに対する警告や専用ログはありません。

ソースコメントは native 操作が multi-stream で起動ごとに出力を変えた観測を記し、既定 kernel 実装を repeatable としています。これは当該コメントの記述であり、この調査で再測定した結果ではありません。`docs/SPLIT_ENGINE.md` に本変数の説明はありません。

## 根拠

- 読み取りと完全一致判定、初回値の static cache、および両 wrapper の分岐: `src/split/src/hip/cuda.h:17-52`。
- HIP split の Linux/backend 条件、HIP 用 include path とターゲット定義、split の既定 OFF: `src/split/CMakeLists.txt:1-7,20-27,45-56,92-109`; `CMakeLists.txt:2945-2949`。
- stream 操作の呼び出し: `src/split/src/pf_common.cuh:179-185,262-273`; `src/split/src/prefill.cu:541-572,589-595`。
- HIP API エラーの例外化: `src/split/src/pf_common.cuh:27-38`。
- kernel 待機 timeout: `src/split/src/hip/cuda.h:30-36`。プロンプトの bounded wait と ring error: `src/split/src/prefill.cu:1319-1335`。
