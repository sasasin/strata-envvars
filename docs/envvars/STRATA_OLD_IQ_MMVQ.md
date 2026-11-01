# `STRATA_OLD_IQ_MMVQ`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

IQ 量子化形式の複数列 MMVQ と、grouped native expert の gate/up・down で、複数列・複数 entry に対して重みをまとめて処理する新しい multi カーネルを避け、旧来の per-column / lane カーネルを選びます。`src/kernels/cuda/iq_kernels.cu` は CUDA と HIP の GPU ソースで、SYCL ビルドには `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の対応実装があります。CPU のみのビルドではこれら GPU カーネルは使われません。

CUDA/HIP では旧カーネルを A/B 用に選ぶフラグです。ヘッダーは旧・新カーネルの出力が bitwise 同一と説明しています。SYCL では旧 kernel 経路を選ぶ値です。性能差はこの commit のコードからは確定できません。

## 値と判定

両 GPU 実装で `env_on()` は `std::getenv()` の結果について、未設定、空文字、または先頭文字が `0` のとき false、それ以外の非空文字列なら true を返します。文字列全体の parse や数値変換はしません。

| 値 | 判定 | 動作 |
|---|---|---|
| 未設定 | OFF | 通常の backend 側の選択規則を使う |
| 空文字 | OFF | 同上 |
| `0`, `0anything` | OFF | 同上 |
| `1`, `true`, `false`, `2`, `-1`, ` anything` | ON | 対象となる旧 kernel を優先 |

先頭が空白なら `0` ではないため ON です。大文字小文字は変換・比較されず、先頭文字だけで判定します。数値範囲や無効値 fallback はありません。

## 有効になる条件

- CUDA/HIP の `src/kernels/cuda/iq_kernels.cu` がビルドに含まれる GPU バックエンドで有効です。同ファイルは grouped native expert と IQ MMVQ の分岐でフラグを参照します。実際に分岐するのは compile-time の `kSplit<T>` 対象形式です。`!kSplit<T>` の形式はこの値にかかわらず元から通常 kernel を使います。
- CUDA/HIP の対象形式では、`g_old_kernels` が true なら MMVQ が `mmvq_kernel` を選び、grouped expert の gate/up と down がそれぞれ `native_gu_kernel` / `native_down_kernel` を選びます。形式固有の `split_off<T>()` が true の場合も CUDA/HIP は旧 kernel 側です。
- SYCL は別ビルドの backend です。MMVQ は `g_old_kernels` が true なら `mmvq_kernel`、grouped expert は `launch_gu_lanes` / `launch_down_lanes` を選びます。SYCL の multi 経路は `STRATA_EXPERT_SPLIT` による `g_split_multi` が必要で、旧カーネル指定はその multi 経路を抑えます。
- CUDA/HIP では `STRATA_EXPDEC` が有効でも、`g_old_kernels` が true なら EXPDEC の gate/up・down 関数は false を返し、呼び出し元が既定の grouped カーネルへ進みます。SYCL ファイルにはこの EXPDEC 経路はありません。
- `STRATA_OLD_IQ_MMVQ` は CLI 引数、モデル状態、サーバーモードによる上書きとして読まれません。内部の `iq_set_old_kernels(bool)` API で値を後から変更する呼び出しは parity / benchmark 用コードにありますが、対象の実行ファイルのユーザー向け CLI 優先順位ではありません。

## 実行時の詳細

値は各翻訳単位のグローバル `g_old_kernels` 初期化時に一度読み取られます。従って実行中にプロセス環境を変更しても自動で再読込されません。内部 API `iq_set_old_kernels()` が呼ばれれば変数値に関係なく状態を上書きできます。ヘッダーは graph capture より前に設定すること、capture 済み graph は capture 時の kernel を保持すると説明しています。

この変数自体によるログ、警告、終了処理はありません。kernel 選択後の通常の launch error は CUDA 実装の `check()` で stderr にエラーを出して `exit(1)` しますが、これはこの環境変数固有の失敗経路ではありません。

`docs/EXPERTDEC.md` も、この変数が EXPDEC と multi kernels を無効にすると記しています。性能測定値は本書では主張しません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3395-3401` — `env_on()` の値判定とグローバル読み取り。
- `src/kernels/cuda/iq_kernels.cu:3496-3510,4195-4225,4276-4290` — CUDA/HIP の MMVQ、gate/up、down の kernel 選択。
- `src/kernels/cuda/iq_kernels.cu:4151-4192,6410-6415,6484-6490` — `g_old_kernels` による EXPDEC 不採用と caller の通常 kernel fallback。
- `src/kernels/cuda/iq_kernels.cu:5301-5302` — 内部 setter / getter。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3200-3211,3438-3483,4588-4633,4639-4641` — SYCL の値判定、MMVQ・grouped kernel 選択、内部 setter。
- `include/strata/kernels/iq_kernels.hpp:134-143` — per-column 旧 kernel、bitwise 同一、graph capture の注記と API。
- `CMakeLists.txt:80-95,412-425,502`; `sycl/CMakeLists.txt:237-251` — CUDA/HIP と SYCL の backend / source 組み込み条件。
- `docs/EXPERTDEC.md:31-42` — EXPDEC とこの変数の関係に関する Strata 文書。
