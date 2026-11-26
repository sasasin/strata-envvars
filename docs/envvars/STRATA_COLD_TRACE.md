# `STRATA_COLD_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA / HIP の prefill で `native_proj` または `bf16_proj` に到達したとき、dense GEMM の時間を計測して stderr に記録する診断スイッチです。`native_proj` は native GGUF ブロックを使う射影、`bf16_proj` は常駐 BF16 tensor の射影を対象にします。環境変数が無効なら計測用の同期・ログ出力は行わず、射影自体の処理は通常どおりです（`engine/src/prefill/prefill.cpp:3947-3998`）。このファイルは CUDA / HIP 共通の GPU prefill ライブラリに含まれ、HIP ビルドでも同じ実装を使います（`engine/cmake/strata_gpu_engine.cmake:7-12,478-488`）。

## 値と判定

`ColdTrace` のグローバルインスタンス生成時に `std::getenv` で一度読み、未設定でないことに加えて先頭文字が `'1'` である場合だけ有効になります。文字列全体の数値変換や真偽値判定はしません（`engine/src/prefill/prefill.cpp:3949-3966`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA / HIP の GPU prefill | 無効 | `1`、`10`、`1anything` | 空文字、`0`、`01`、`true`、`True`、` 1` |

先頭が `1` かどうかだけを比較するため、数値の妥当性・範囲・後続文字・大文字小文字・空白の trim は検査されず、無効値に対する警告や fallback もありません。CLI 引数や別の環境変数による上書き処理はありません（`engine/src/prefill/prefill.cpp:3951-3953`）。

## 有効になる条件

- 実行ファイルに CUDA または HIP の GPU prefill が含まれていること（`engine/cmake/strata_gpu_engine.cmake:478-488`）。
- この判定に CLI / サーバーモードや GPU 世代ごとの分岐はありません。どちらの起動経路でも、対象射影関数に到達すれば同じ条件で計測します（`engine/src/prefill/prefill.cpp:3949-3979`）。
- モデル処理が prefill の `native_proj` または `bf16_proj` に到達すること。前者は `w->native_data` が必要で、後者は `WeightKind::Bf16InF32` かつ `w->data` が必要です。条件を満たさない場合は各射影関数が既存のエラーを返し、計測を開始しません（`engine/src/prefill/prefill.cpp:3967-3979`）。両関数は通常の prefill の GDN / QSA / その他の射影処理から呼ばれます（例: `engine/src/prefill/prefill.cpp:5171-5192`、`5222-5240`）。
- `STRATA_COLD_TRACE` が `ColdTrace` の初期化時に設定済みで、先頭文字が `1` であること。値はグローバルインスタンスで一度だけ保持され、プロセス実行中に環境を変更しても読み直しません（`engine/src/prefill/prefill.cpp:3949-3966`）。
- 有効時でも、計測対象はこの二つの prefill 射影関数を通る GEMM に限られます。decode など他の計算や、ここを通らない最適化経路はこのスイッチでは計測されません（`engine/src/prefill/prefill.cpp:3967-3998`）。

## 実行時の詳細

各対象射影の前に `cudaDeviceSynchronize()` を呼び、その直後から `steady_clock` で計時します。GEMM の呼び出し後に再度デバイス全体を同期し、経過時間を出力します。したがってログの時間は GEMM 呼び出しから同期完了までの wall time で、計測のたびにデバイス全体の同期を追加します（`engine/src/prefill/prefill.cpp:3952-3964`）。

計測はプロセス内で最大 80 回です。カウンターは `g_cold` に共有されるため、モデルやリクエストごとではなくプロセス内の対象射影呼び出しを数えます。80 回に達した後は同期もログも行いません（`engine/src/prefill/prefill.cpp:3952-3966`）。`bf16_proj` が `X_lo` を追加で計算する場合、その2回目の `gm.bf16` は計測範囲の外です。また Q8 scratch から BF16 scratch を作る処理も計測開始前です（`engine/src/prefill/prefill.cpp:3978-3997`）。

環境変数はグローバルオブジェクトの構築時に読みます。CLI オプションによる優先順位やリクエスト単位の再評価はありません。この実装から子プロセスへ値を転送する処理は確認できません。同期 API の戻り値も検査していないため、この計測コード独自の同期失敗ログや終了処理はありません（`engine/src/prefill/prefill.cpp:3949-3966`）。

## ログと測定値

対象射影ごとに stderr へ次の形式で出力します。`what` は `native` または `bf16`、`name` は重み名、`T` / `N` / `K` は GEMM に渡す行列寸法、末尾はミリ秒です（`engine/src/prefill/prefill.cpp:3958-3964`）。

```text
strata cold-trace: #<番号> <native|bf16> <重み名> T=<行数> N=<出力幅> K=<入力幅> <ミリ秒> ms
```

## 根拠

- `engine/src/prefill/prefill.cpp:3947-3998` — 値の読み取り、計測条件・範囲、同期、上限、stderr 出力。
- `engine/src/prefill/prefill.cpp:5171-5240` — prefill の GDN / QSA から対象射影が呼ばれる例。
- `engine/cmake/strata_gpu_engine.cmake:7-12,478-488` — CUDA / HIP GPU prefill ライブラリへの組み込み。
