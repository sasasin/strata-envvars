# `STRATA_EXPERT_SPLIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata の SYCL 実装が grouped expert の gate/up と down の積を計算するとき、i-quant 系など一部の形式で使う multi-entry kernel を選びます。既定では Strata port の lane kernel を使い、この変数を有効にすると upstream 由来の multi kernel とその grid を使います。対象は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の実装です。この名前を読む Strata 所有コードはこのファイルの一箇所だけで、CUDA `.cu` 実装では確認できません。

## 値と判定

`env_on()` は `getenv()` の結果について設定有無と先頭文字だけを調べます。文字列全体や数値としての妥当性は parse しません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| 空でなく先頭文字が `0` 以外 | 有効（例: `1`, `true`, `false`, `2`, ` 1`） |

大文字小文字、空白、後続文字は検査しません。従って `false` も有効です。値は namespace scope の `g_split_multi` 初期化時に一度読み込まれます。通常の Strata engine プロセスでは起動時の環境で決まり、起動後の環境変更では再評価されません。

根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3202,3209`。

## 有効になる条件

- SYCL build がこの kernel 実装を使い、実行が `native_expert_grouped()` の SYCL launch 経路に入る必要があります。SYCL build は `iq_kernels` を kernel source 一覧に含めます（`sycl/CMakeLists.txt:237-248`）。
- gate/up (`TG`) または down (`TD`) の量子化型が compile-time の `kSplit<T>` で `true` である必要があります。現行の `kSplit` 特殊化は型番号 `16, 17, 18, 20, 21, 22, 23, 29, 42, 144, 145, 146` です。これ以外は値が有効でも lane kernel を使います。
- `g_old_kernels` が有効なら lane kernel が優先され、`STRATA_EXPERT_SPLIT` はその呼び出しでは選択に影響しません。`g_old_kernels` は起動時の `STRATA_OLD_IQ_MMVQ` に加え、公開関数 `iq_set_old_kernels(bool)` でも変更できます。
- SYCL ソース内の `STRATA_HIP_GFX906` 条件付き AMD 専用 launch 分岐が該当型を処理する場合、その分岐は `launch_gu` / `launch_down` の切り替えを通りません。このため、その経路では `STRATA_EXPERT_SPLIT` による選択は適用されません。

根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:963-964,1017,1049,1086,1125,1170,1218,1243,1271,1308-1310,3199-3210,4593-4605,4627-4633,4638-4640,5668-5689,5764-5791`。

## 実行時の詳細

`native_expert_grouped()` は gate/up と down の型ごとに dispatcher を呼びます。`kSplit<T>` が偽なら常に lane kernel です。真の場合は `g_old_kernels` が有効、または `g_split_multi` が無効なら lane kernel、有効なら multi kernel へ進みます。gate/up の multi kernel は `GU_ROWS` 行の grid を作って `native_gu_multi_kernel` を launch し、down は同様に `native_down_multi_kernel` を launch します。

gate/up の multi kernel では、型別に staging 対応があり、別変数 `STRATA_IQ_STAGE_GRID` が有効なら staged 版を使います。これは `STRATA_EXPERT_SPLIT` の有効化条件ではなく、multi kernel 内での追加選択です。down multi kernel にはこの staging 分岐はありません。

この変数自体にログ出力はありません。コードコメントでは B70 で測定された port kernel を既定にし、`STRATA_EXPERT_SPLIT=1` で upstream kernel を選ぶと説明しています。`docs/INTEL.md` の B70 測定記録も opt-in としていますが、その記録は当該文書に書かれた条件の範囲の結果であり、この調査で性能を再測定したものではありません。

根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3205-3209,4570-4605,4608-4633,5660-5695,5760-5794`; `docs/INTEL.md:555-559,567-569`。

## 根拠

- 候補名の直接参照と値の判定: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3210`。
- gate/up と down の kernel 選択: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4593-4605,4622-4633`。
- SYCL build の kernel 登録: `sycl/CMakeLists.txt:237-248`。
- port 既定と upstream multi kernel の説明: `docs/INTEL.md:555-559`。
