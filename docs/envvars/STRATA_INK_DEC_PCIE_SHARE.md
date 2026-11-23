# `STRATA_INK_DEC_PCIE_SHARE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling2 の CUDA ハイブリッド MoE 処理で、GPU VRAM にない host expert のうち、verify batch の miss を GPU へ PCIe DMA 転送して CUDA Tensor Core で処理する比率を指定する。残りを CPU worker pool に割り当てる。`0` は GPU 割当なし、`1` は全 miss を GPU 側へ割り当てる設定だが、後述の適用条件を満たす場合に限る。実装は `InkHybridEngine::start_workers` が値を読み、`launch_ink_moe_hybrid` が比率で miss を分割する (`engine/src/inkling2/cuda/ink_hybrid.cuh:956-990,1177-1184,1561-1578,1633-1665`)。

## 値と判定

`start_workers` の初回実行時に `std::getenv` で設定有無を確認し、設定されていれば `std::atof` で数値変換して `std::min(1.0, ...)` と `std::max(0.0, ...)` で `[0,1]` に制限する。未設定はメンバー初期値 `-1.0` のまま自動設定を使う。空文字や数値に変換できない文字列は `atof` の変換結果 `0` となる。数値の後ろに文字があっても数値部分を読み、全体一致やエラー検査はしない。負数は `0`、`1` 超は `1` に制限される。文字列 `true` / `false` は数値に変換できず `0` になる。(`engine/src/inkling2/cuda/ink_hybrid.cuh:989,1177-1183`)

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・境界になる値 |
|---|---|---|---|
| Inkling2 CUDA で worker が起動 | `-1` の自動分岐。通常の分割比率は host arena が pinned なら `0.65`、pageable なら `0.55`。少数 miss の PCIe staging 条件を満たすと全件 PCIe (`1.0`) | 変換後の値を `[0,1]` で clamp。例: `0.25`、`1`、`0.5suffix` → `0.25`、`1`、`0.5` | 空文字、`true`、`abc`、`0anything` → `0`; `-0.1` → `0`; `1.1` → `1`。`0.999` 以上は分割処理の閾値により全件 GPU 割当となる |

## 有効になる条件

- Inkling2 CUDA backend を含む実行経路であること。変数の読み取り場所は `engine/src/inkling2/cuda/ink_hybrid.cuh` で、HIP / SYCL / Metal / CPU backend に同名の読み取りはない (`engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1183`; CUDA plugin の定義は `engine/src/inkling2/cuda/CMakeLists.txt:1-7,65-78`)。
- モデル初期化で host expert が少なくとも 1 件あり、`ink_runner.cuh` が `hybrid.start_workers(...)` を呼ぶこと。host expert がなければ worker 起動とこの読み取りも行われない (`engine/src/inkling2/cuda/ink_runner.cuh:459-467,559-565,1277-1285,1462-1469`)。
- 比率による CPU/GPU 分割が行われるのは、dispatch の `M=2..16`、`!ssd_only`、GPU 外の host expert が 2 件以上、必要な hybrid worker/buffer が有効で、かつ比率が `0.999` 未満の場合。`M=1` は別の doorbell 経路、SSD-only は別の処理経路で、この比率による分割を通らない。miss が 1 件だけ、または必要な buffer がない場合も比率分割条件を満たさず、設定した値どおりの CPU/GPU 配分にはならない (`engine/src/inkling2/cuda/ink_hybrid.cuh:1596-1604,1616-1639,1666-1694`)。
- `--` 引数や別の環境変数による当該値の上書きは、この読み取り・分岐経路にはない。`STRATA_INK_DEC_PCIE_SHARE` の参照は上記の CUDA ソース 2 箇所（初期値のコメントと `getenv`）で、別の backend 読み取りも確認できない。

## 実行時の詳細

`start_workers` は `active` の場合すぐ戻り、その後に CPU 数等を設定して環境変数を読む。このため worker 起動に使われる初回の読み取り後、プロセス内で環境を変更しても同じ `InkHybridEngine` の値には反映されない (`engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1183`)。起動関数は host expert の存在を条件にモデル初期化中に呼ばれる (`engine/src/inkling2/cuda/ink_runner.cuh:459-467,559-565`)。

`M=2..16` の通常経路では、GPU 外にある host expert の miss を出現頻度 `ecnt` の降順で並べ、`w_goal = share * w_tot` に届くまでを GPU 側の host list に残し、残りを CPU 側に分ける。その後 GPU 分は pinned staging buffer に非同期転送して GPU 上で実行し、CPU 分は worker pool で評価して結果を GPU に戻す (`engine/src/inkling2/cuda/ink_hybrid.cuh:1621-1665,1785-1800,1802-1829`)。設定値 `0` の場合でも miss が 1 件だけなど分割条件を満たさない経路では、この分割は実行されない。

未設定時の少数 miss 高速経路では、host miss が 6 件以下で PCIe staging が利用可能な場合 `stream_all_pcie` が立ち、全件 GPU に回る。変数を設定するとこの自動判定は無効になり、通常は pinned arena で `0.65`、pageable arena で `0.55` の比率が適用される。明示値が `0.999` 以上だと分割条件 `share < 0.999` が成立せず、通常の GPU streamed miss がすべて GPU 側に残る (`engine/src/inkling2/cuda/ink_hybrid.cuh:1633-1639`)。

## ログと測定値

この変数の値、無効値、選択された比率を表示する専用ログや、変数に起因するエラー・終了経路は該当コードにない。CUDA API 失敗時の一般的な処理は `INK_CK` によるもので、変数値の検証メッセージではない (`engine/src/inkling2/cuda/ink_hybrid.cuh:1183-1209`)。`docs/DETAILS.md` には別の PCIe share 制御に関する説明はあるが、この変数名や Inkling2 の動作に結びつく測定値は見つからなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:956-990,1177-1184` — 状態の初期値、環境変数の読み取り、変換・clamp。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1596-1604,1616-1639,1640-1665,1666-1694` — M の分岐、host miss の選出、自動値、適用条件、比率分割。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1785-1800,1802-1829` — GPU streamed miss と CPU 評価・結果転送。
- `engine/src/inkling2/cuda/ink_runner.cuh:459-467,559-565,1277-1285,1462-1469` — host expert がある場合の worker 起動。
- `engine/src/inkling2/cuda/CMakeLists.txt:1-7,65-78` — Inkling2 CUDA plugin のビルド条件。
