# `STRATA_OLD_IQ_MMVQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP と SYCL の IQ 系 MMVQ および grouped expert の通常 dispatch で、分割形式に対する新しい multi-entry kernel の代わりに、重みを列・entry ごとに再 decode する従来 kernel を選ぶ診断・A/B 用スイッチです。対象となる形式では計算経路と性能が変わります。CUDA/HIP の grouped expert にはこのフラグを参照せず先に実行される特化経路があり、すべての呼び出しを従来 kernel に固定するものではありません。ヘッダーコメントは新旧 kernel の結果を bitwise equal としていますが、この調査では実行比較していません。CUDA/HIP では `STRATA_EXPDEC` による EXPDEC も抑止します。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3693-3695,3791-3804,4452-4457,7089-7183,7205-7215,7265-7280,7340-7385`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3931-3938,4174-4227,6053-6067`、`engine/include/strata/kernels/iq_kernels.hpp:186-188`。

## 値と判定

CUDA/HIP と SYCL のどちらも `env_on` が `std::getenv` の結果を検査し、値が未設定でなく、空文字でなく、先頭文字が `0` でなければ true とします。文字列全体や数値としての妥当性は parse しません。大文字小文字や空白も検査せず、先頭文字だけで判定します。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3689-3694`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3932`。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP | off | `1`, `true`, `false`, `x`, ` 1`（空でなく先頭が `0` 以外） | 空文字、`0`, `0anything`, `01`（先頭が `0`） |
| SYCL | off | `1`, `true`, `false`, `x`, ` 1`（空でなく先頭が `0` 以外） | 空文字、`0`, `0anything`, `01`（先頭が `0`） |

数値変換、値域、無効値エラー、clamp はありません。たとえば `false` は文字列として false 扱いされず、有効になります。

## 有効になる条件

- CUDA/HIP の `iq_mmvq` では `kSplit<TY>` の形式で従来 `mmvq_kernel` を選びます。非 split 形式は元から同じ `mmvq_kernel` を使うため、この変数による分岐差はありません。`STRATA_KQ_SPLIT` などで `split_off<TY>()` が true の場合も従来 kernel になりますが、この変数が true ならそちらの設定にかかわらず従来側です。根拠: `engine/src/kernels/cuda/iq_kernels.cu:989-992,3791-3804`。
- CUDA/HIP の `native_expert_grouped` の通常 dispatch では split gate/up と down 形式について、multi kernel の代わりに `native_gu_kernel` / `native_down_kernel` を選びます。非 split 形式はこのフラグの有無で選択が変わりません。行数最適化や特化 kernel の一部も `g_old_kernels` を条件に除外します。例外として、NVFP4 grouped 経路（条件を満たせば 7094-7102）、`STRATA_EXPERT_V2` / `STRATA_EXPERT_V2K` の早期経路（7121-7182）、EXP layout の `fused_gu`（`em0 == 8` など、7205-7239）、および EXP layout の LDS gate/up・down（7265-7280、7355-7385）は `g_old_kernels` を条件にせず先行・代替実行できます。従ってこれらの条件を満たす呼び出しは、この変数が有効でも当該専用経路へ進みます。根拠: `engine/src/kernels/cuda/iq_kernels.cu:4541-4571,4622-4637,7089-7183,7205-7239,7265-7280,7355-7385`。
- CUDA/HIP の EXPDEC は `STRATA_EXPDEC=1` で要求しても、`g_old_kernels` が true なら gate/up・down とも不採用になり、呼び出し側が通常 kernel に進みます。EXPDEC 側の「not covered」ログもこの早期 return では出ません。根拠: `engine/src/kernels/cuda/iq_kernels.cu:4452-4458,4486-4490`。設計資料も旧 MMVQ フラグが EXPDEC と multi kernel を無効にすると記述しています: `docs/EXPERTDEC.md:33-34`。
- SYCL の `iq_mmvq` では split 形式が従来 `mmvq_kernel` に進みます。true の場合、Battlemage 用 IQ3 public XMX 経路など、`!g_old_kernels` を条件とする特化経路も選びません。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4204-4227,6543-6558`。
- SYCL の grouped expert では true なら `launch_gu_lanes` / `launch_down_lanes` に進み、`STRATA_EXPERT_SPLIT=1` が要求する multi-entry 経路を抑止します。`STRATA_EXPERT_SPLIT` が未設定または無効の場合、grouped expert は元から lane 経路なので、その選択自体は変わりません。ただし `g_old_kernels` を条件にした専用経路も抑止されます。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3933-3938,5847-5866,6053-6067,6095-6121`。
- この変数は GPU backend の上記 kernel 選択に関するもので、OS、サーバーモード、CLI 引数、モデル設定による別の値判定は見つかりません。CLI による優先順位もありません。SYCL grouped expert の `STRATA_EXPERT_SPLIT` と CUDA/HIP の `STRATA_KQ_SPLIT` は別の選択条件です。

## 実行時の詳細

両 backend の `g_old_kernels` は翻訳単位スコープのグローバル bool として初期化され、共有 helper を通じて環境を読みます。したがって通常は engine ライブラリ／実行ファイルの初期化時に一度評価され、後から環境を変更しても再読込されません。ヘッダーはこの設定を graph capture より前に行う前提を示し、capture 済み graph は capture 時の kernel を保持すると説明しています。根拠: `engine/src/kernels/cuda/iq_kernels.cu:3689-3694`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3932`、`engine/include/strata/kernels/iq_kernels.hpp:186-188`。

C++ API `iq_set_old_kernels(bool)` は初期化後にグローバル値を変更できます。ただしリポジトリ内の呼び出しは parity / benchmark 用コードにあり、通常の engine 経路から呼ぶ箇所は見つかりませんでした。API が呼ばれた場合は、以降の dispatch にその値が使われます。根拠: `engine/include/strata/kernels/iq_kernels.hpp:194-195`、`engine/src/kernels/cuda/iq_kernels.cu:5647-5648`、例: `engine/src/kernels/iq_multi_parity.cpp:146-148`。

子プロセスへこの値を明示的に転送・上書きする Strata の処理は確認できませんでした。

## ログと測定値

この変数の値を読み取ったことや従来 kernel を選んだことを示す専用ログはありません。空文字や `0` 始まりの値も静かに無効扱いされ、その他の文字列は有効扱いされます。値に起因する警告・終了・失敗経路は見つかりませんでした。通常の kernel dispatch 後に行われる `check` や、未対応型に対するエラーはありますが、この環境変数の値判定によるものではありません。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3689-3694` — CUDA/HIP の helper と環境値の初期読み取り。
- `engine/src/kernels/cuda/iq_kernels.cu:3791-3804,4541-4571,4622-4637` — MMVQ と grouped expert の kernel 選択。
- `engine/src/kernels/cuda/iq_kernels.cu:4452-4458,4486-4490` — EXPDEC を抑止する条件。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3938,4204-4227,6053-6067,6095-6121` — SYCL の helper と MMVQ / grouped expert の選択。
- `engine/include/strata/kernels/iq_kernels.hpp:186-195` — kernel の意図、graph capture と API。
