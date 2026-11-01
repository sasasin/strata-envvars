# `DS4_COPY_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Metal の DS4 実行経路で `ds4_ctx_copy` が処理するコピーについて、呼び出し中のホスト経過時間とコピー数・バイト数を集計し、プロセス終了時に標準エラーへ出します。GPU 上のコピー完了時間を測る設定ではありません。

## 値と判定

`ds4_ctx_copy` の各非ゼロ長呼び出しで `std::getenv("DS4_COPY_LOG") != nullptr` を判定します。値の内容は parse されず、数値変換や文字列比較もありません。

| 値 | 集計 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む設定済みの値 | 有効 |
| その他の任意の値（`0`、`false` などを含む） | 有効 |

既定値は無効です。CLI 引数や別の環境変数による優先順位・上書きはありません。設定はコピー呼び出しごとに読み直され、static cache はありません。

## 有効になる条件

この読み取りは macOS 専用の Metal DS4 ビルドに含まれる `ds4_finish.cpp` のコードです。CUDA / HIP / SYCL の経路ではこの実装を通りません。

実行時には DS4 runtime が有効で、ストリームの graph capture 中ではなく、`DS4_STREAM_COPIES` が未設定で `ctx_queue_ops()` が有効、かつコピー元と先の両方が runtime の管理対象である場合に `memcpy_async` から `ds4_ctx_copy` が呼ばれます。`DS4_STREAM_COPIES` が設定されている（値が空でも同じ）場合、または上記条件を満たさない場合はこの呼び出し経路を使いません。関数に渡されたサイズが 0 なら即時成功し、環境変数を読みません。

## 実行時の詳細

`ds4_ctx_copy` は環境変数が設定されていれば時刻を記録し、`ensure()`、host view の取得、Metal buffer の wrap、pipeline の取得、dispatch の投入を試みます。呼び出し終了時の RAII 集計器が、成功・失敗のどちらでも呼び出し数、要求バイト数、関数内の経過マイクロ秒を加算します。たとえば初期化失敗、host view 不在、buffer handle 不在、pipeline 取得例外による `false` return も集計対象です。`memcpy_async` は `ds4_ctx_copy` が成功した場合に成功を返し、失敗した場合は後続の queue barrier / 通常の stream copy 経路へ進みます。

集計値は DS4 finish ファイル内の静的 `CopyLog` に蓄積され、デストラクタからプロセス終了時に `stderr` へ次の形式で出力されます。集計された呼び出しがなければ何も出しません。

```text
copy log: %llu copies, %.1f MB, %.1f ms host time (%.1f us a copy)
```

ログの `host time` は各 `ds4_ctx_copy` 呼び出しの開始から return までのホスト側経過時間を合算したものです。実装はこの計測のために GPU 完了を待ちません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2646-2662` — 集計器、終了時ログ、環境変数の有無判定と計時開始。
- `metal/src/engine/ds4_finish.cpp:2663-2688` — コピー処理と早期失敗経路。RAII 集計器により return 時にも集計。
- `metal/src/gpu/runtime.cpp:242-252,618-634` — DS4 runtime guard、`DS4_STREAM_COPIES` 条件、呼び出し元と fallback。
- `metal/CMakeLists.txt:1-2,16-18,132-165` — macOS 専用 Metal プロジェクトと DS4 runtime のビルド定義。
