# `STRATA_EXPERT_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL エンジンの native expert 計算で、split 形式の gate/up・down 行列に使うカーネルを、ポート独自の grouped/lane kernel から upstream 由来の multi kernel に切り替えます。デフォルトはポート独自 kernel です。カーネルの選択と launch grid を変えますが、環境変数を読み取るだけの診断フラグではなく、計算経路を切り替える実行時フックです。

環境変数を読む実装は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にのみあります。通常のトップレベル CUDA engine の `src/kernels/cuda/iq_kernels.cu` にはこの名前の参照がなく、少なくとも調査対象ソースで確認できる適用先は SYCL kernel です。`native_expert_grouped()` は native expert layout の場合に呼ばれます。通常の native expert 実行が無効、または別の expert 経路の場合はこの設定の影響を受けません。

## 値と判定

共通 helper `env_on()` は `getenv()` の結果について、値が存在し、空でなく、先頭文字が `0` でない場合だけ true を返します。文字列全体の parse、数値変換、空白除去、大文字小文字の正規化はしません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| `0`, `0anything`, `01` | OFF（先頭文字が `0`） |
| `1`, `10`, `true`, `false`, ` 0` | ON（空でなく先頭文字が `0` ではない） |

この値は translation unit のグローバル `g_split_multi` 初期化時に一度読み取られます。プロセス起動後の環境変更では再評価されません。

## 有効になる条件

- SYCL 側で `STRATA_NATIVE_EXPERTS` が有効なビルドで、実行時に native expert の grouped kernel 経路へ入る必要があります。SYCL CMake は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` を kernel 群へ含めます。
- 対象型が `kSplit<T>` として登録された split 形式である必要があります。通常の `STRATA_GU_FMTS` / `STRATA_D_FMTS` dispatch を通る gate/up または down 型だけが対象です。非 split 型は環境変数が ON でも port lane kernel を使います。
- `g_old_kernels` が true の場合は split multi kernel への切替を抑止し、port lane kernel を使います。通常の初期値は `STRATA_OLD_IQ_MMVQ` で読み取ります。別の設定口 `iq_set_old_kernels()` は公開されていますが、リポジトリ内の呼び出しは parity 用コードに限られます。
- 該当する `STRATA_HIP_GFX906` の AMD 専用 dispatch が先に kernel を選ぶ経路では、この SYCL split launcher の分岐を通りません。

## 実行時の詳細

`g_split_multi` が true で、対象型が `kSplit<T>`、かつ旧 kernel が選ばれていない場合、gate/up は `launch_gu_multi()`、down は `launch_down_multi()` を使います。これらは `GU_ROWS` 行単位の独自 grid で `native_gu_multi_kernel` / `native_down_multi_kernel` を起動します。条件を満たさない場合は `launch_gu_lanes()` / `launch_down_lanes()` へ進み、port の lane kernel を使います。gate/up の `STRATA_IQ_STAGE_GRID` 等による staging は multi kernel 側でも別途条件分岐します。

読み取り箇所ではログ、警告、エラーを出しません。この変数自体に対する CLI・設定ファイル・別環境変数との優先順位もありません（旧 kernel の選択は上記の独立した上書き条件です）。SYCL port の資料では、B70 上の測定で port default が upstream 由来 kernel より速かったため default を維持し、この設定を opt-in にしています。資料記載の decode tok/s は Coder の 19-token prompt / 2,184-token prompt / IQ2_XS 19-token prompt の順に、port default が 78.1 / 75.7 / 58.6、`STRATA_EXPERT_SPLIT=1` が 65.6–69.5 / 67.2 / 49.1（資料記載で -11〜-16%）です。これは docs の B70 測定記録であり、他の GPU・モデル・条件に一般化できません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2824` — helper の値判定、グローバル初期化、既定 kernel に関する説明。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:773-777,870-1179,2804-2810` — gate/up と down の dispatch format、および `kSplit<T>` 登録。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4162-4195,4197-4222` — multi/lane kernel の起動条件と launch grid。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5052-5078,5129-5139,5201-5235` — native expert 経路、旧 kernel 条件、型ごとの呼び出し。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4227-4228` と `src/kernels/iq_multi_parity.cpp`, `sycl/src/kernels/iq_multi_parity.cpp` — 旧 kernel setter と parity 用呼び出し箇所。
- `sycl/src/core/verify.cpp:1433-1445` および `sycl/src/core/remote_experts.cpp:426-437` — native layout 時の呼び出し元。
- `sycl/CMakeLists.txt:151-190,205-218` — native experts build option と SYCL kernel 群への登録。
- `docs/INTEL.md:530-544` — port と upstream 由来 kernel の説明、および上記測定記録。
