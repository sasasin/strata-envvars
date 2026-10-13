# `STRATA_DEC_BATCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。CUDA/HIP 実装と Strata の SYCL エンジンを確認。外部ライブラリの環境変数の動作は対象外。

## 役割

検証用 decode window に複数行があるとき、対応する GPU 計算やデータ転送を複数 token まとめて処理する経路を許可します。無効にすると、これらの経路の一部が token ごとの処理に戻ります。検証 window 自体や lookahead の有効・無効を切り替える変数ではありません。

対象は CUDA/HIP の `Verifier::record_window()`、SYCL エンジンの同名処理、および CUDA/SYCL の shared expert 実装です。効果には別の backend 機能、window 行数、モデル形状、他の設定を必要とするものがあります。

## 値と判定

値は `std::atoi()` で変換し、結果が 0 かどうかで判定します。文字列全体の厳密な数値検証はしません。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 無効（`atoi("")` は 0） |
| `0`、`00`、`0xyz`、数値で始まらない文字列 | 無効 |
| `1`、`-1`、`2`、先頭の空白や符号の後に非ゼロ数値がある文字列 | 有効 |

読み取りは各ソース内の関数ローカル `static const bool` の初回初期化時です。CUDA/HIP verifier、SYCL verifier、CUDA shared expert、SYCL shared expert はそれぞれ独立して判定値を保持します。通常これらは同じプロセス内で同一の環境を読みますが、判定後に環境を書き換えても、既に初期化された判定は更新されません。

## 有効になる条件

- 複数行の処理を持つ検証 window で効果が現れます。個々の分岐には `n > 1` の条件があり、1 行ならバッチ専用経路を使いません。
- CUDA/HIP では `record_window()` の `dec_batch` 判定が residual write、Q/K/V や indexer の処理、MoE router・combine、CPU 側 expert 結果の GPU 転送などの条件に使われます。別の switch（例: `STRATA_NO_MULTI_GR`、`STRATA_NO_BATCH_KV`）や batch-recording 経路により、個別の最適化が使われない場合があります。
- `STRATA_PLE_BATCH` が有効な場合の PLE key/value projection の一括処理にも `dec_batch` が必要です。また resident mode の shared expert gate 融合は `dec_batch` に加え、`STRATA_LFUSE`、native combine/BF16 条件、2〜8 行を必要とします（`src/core/verify.cpp:853-855, 961-975`）。
- MoE router の一括経路は、CUDA では native router が有効で `NE == 512`、`K == 10` の場合に使われます。HIP `gfx906` には `moe_route_window()` 経路があります。それ以外は token ごとの router にフォールバックします。SYCL では native router の一括経路が `NE == 512` または `256`、`K == 10` に対応します。
- Shared expert の gate projection を一回の multi-row GEMV にするには、native BF16 経路と `n_tok > 1` が必要です。条件が合わないと token ごとの処理に戻ります。
- 文書・ベンチ結果ディレクトリには変数名の記載がありますが、`docs/` にこの変数の設定仕様を説明する記述は見当たりませんでした。速度や出力の同一性はこの調査では測定していません。

## 実行時の詳細

CUDA/HIP verifier は `record_window()` の冒頭で値をキャッシュします。既定では decode window の複数行をまとめ、たとえば条件が揃った場合に residual write、QSA の K/V append と indexer append、router/top-10、MoE combine を複数行のカーネル呼び出しにします。行単位の計算に対応する箇所には token ごとの実装も残っています（`src/core/verify.cpp:845, 853-855, 965-1012, 1223, 1265-1322, 1433-1462, 1663-1679`）。

MoE の CPU expert 結果がある場合は、バッチ有効時に GPU 自身が処理する行を除いた mapped-memory の行コピーを使い、GPU hit 行のゼロ初期化も GPU 側に任せられる条件があります。`STRATA_VERIFY_DEVICE_PLAN` が有効な場合はこのゼロ化条件から除外されます（`src/core/verify.cpp:1635-1639`; SYCL expert source: `sycl/src/core/expert_source.cpp:2706-2710, 2751-2759`）。

SYCL verifier も同様の既定値と `atoi` 判定を持ちますが、router の native multi-row 条件は CUDA/HIP と完全には同じではありません（`sycl/src/core/verify.cpp:825, 1309-1334`）。

設定値に応じた専用ログは見つかりませんでした。失敗時のエラーは各処理の既存経路から返されます。たとえば CUDA verifier の router/combine は例外を `verify router: ...` / `verify combine: ...` として `err` に設定します（`src/core/verify.cpp:1438-1448, 1652-1667`）。

## 根拠

- `src/core/verify.cpp:845, 853-855, 965-1012, 1223, 1265-1322, 1433-1462, 1627-1645, 1663-1679` — CUDA/HIP verifier の判定と使用箇所。
- `src/kernels/cuda/shared_expert.cu:246-264` — CUDA shared expert の判定と multi-row / per-token 分岐。
- `sycl/src/core/verify.cpp:825, 838-839, 920-957, 1097, 1123-1168, 1309-1334, 1487-1515, 1522` — SYCL verifier の判定と使用箇所。
- `sycl/src/kernels/cuda/shared_expert.dp.cpp:377-428` — SYCL shared expert の判定と分岐。
- `sycl/src/core/expert_source.cpp:2706-2710, 2751-2759` — SYCL expert source が GPU hit 行のゼロ化を省略する条件。
- `docs/DETAILS.md`, `docs/AMD_HIP.md` — 関連する検証・backend 説明を照合。`STRATA_DEC_BATCH` の仕様記述は確認できず。
