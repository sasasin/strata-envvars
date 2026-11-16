# `STRATA_SYCL_PACKED_SIGNS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL backend の grouped expert 計算で、特定の IQ2 gate/up 形状に限り、packed-signs 用の固定形状カーネルを選ぶ opt-in です。`STRATA_SYCL_PACKED_SIGNS` を読むのは `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `launch_gu_port` にある2分岐で、IQ2_XXS (format 16) は `launch_gu_packed_fixed<10016>`、IQ2_S (format 22) は `<10022>` を起動します。これらのテンプレート形式はそれぞれ通常の format 16/22 に packed-signs 用の dot 実装を割り当てています（同ファイル:938-941, 4267-4275, 5640-5651）。

この分岐は gate/up の計算だけを変えます。down 計算や他の量子化形式を選ぶフラグではありません。SYCL 以外の backend の動作を決める読み取りは見つかりませんでした（同ファイル:5640-5651）。

全参照のうち `data/settings-register.json:40428` は設定レジストリの記録で、値を環境から取得する処理ではありません。ソースコード上の読み取りは上記2箇所です。CLI 引数や設定ファイルによる上書きも見つかりませんでした。

## 値と判定

共通 `env_on(name)` は `std::getenv(name)` の戻り値を調べ、未設定でなく、空文字でなく、先頭文字が `'0'` でない場合に true を返します。文字列全体の parse、数値変換、大文字小文字変換、空白除去はしません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `env_on` の判定 | 無効 | `1`, `true`, `false`, ` 0`, ` 1`, `2anything` | 空文字, `0`, `0anything`, `00` |

`false` も先頭が `f` なので判定上は有効です。値が有効でも、下記の backend・カーネル経路・形状条件が満たされなければ分岐しません。優先順位や無効値からの fallback はなく、条件に合わない場合は次の通常カーネル経路へ進みます（同ファイル:5640-5655）。

## 有効になる条件

- SYCL の `native_expert_grouped` が `launch_gu` まで到達し、IQ2_XXS または IQ2_S の gate/up を処理すること。CUDA/HIP 向けの同名設定処理はありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7308-7317, 7413-7417`）。
- grouped の呼び出しが `cap_entries <= 80` で `bounded=true` を渡すこと。この `bounded` 引数は別の環境変数ではなく、`cap_entries` から決まります（同ファイル:7413-7415）。
- レーン数テンプレートが 8 (`LN==8`) であること。レーン数は `STRATA_GU_LANES` によって選ばれ、値が4/16/32ならこの分岐には一致しません（同ファイル:4243-4249, 5702-5711）。
- IQ2_XXS の場合は `!STRATA_OLD_IQ_MMVQ`, `!STRATA_EXPERT_SPLIT`, `!STRATA_SYCL_EXPERT_MULTI16`。IQ2_S の場合は `!STRATA_OLD_IQ_MMVQ`, `!STRATA_EXPERT_SPLIT` が必要です。これら3変数の判定値は翻訳単位の初期化時に `g_old_kernels`, `g_split_multi`, `g_iq2xxs_reuse` に保存されます（同ファイル:3689-3700, 4250-4253, 5640-5650）。
- 形状と配置が固定値に一致すること。IQ2_XXS は `n_embd=2560`, `n_ff=640`, `gu_row=660`, `up_off=640*660`。IQ2_S は同じ `n_embd/n_ff` で `gu_row=820`, `up_off=640*820` です。`NativeExpertLayout` は `gu_row` と `up_off` を量子化形式と形状から計算します（同ファイル:6729-6740, 5640-5650）。
- `native_expert_grouped` 内の先行する専用経路に一致しないこと。一致時はそこで起動して戻るため、この環境変数を確認する `launch_gu_port` に届きません（同ファイル:7388-7412）。

`STRATA_SYCL_DEQUANT_GU_BOUNDED` は別の後段 dequant 経路を制御する変数です。このフラグの `bounded` 引数と同一条件ではありませんし、packed-signs 分岐自体の有効化条件としては参照されません（同ファイル:5640-5650, 6643-6648）。

## 実行時の詳細

`env_on("STRATA_SYCL_PACKED_SIGNS")` は `launch_gu_port` の呼び出し時に各候補分岐で評価され、対象変数についての `static` cache はありません。したがって関数呼び出し間では環境値の再取得がコード上行われます（同ファイル:3689-3692, 5640-5650）。

条件を満たすと通常の `native_gu_kernel` 起動の代わりに `launch_gu_packed_fixed` が起動し、40×256 の work range で固定形状の `native_gu_kernel<TG,8,false,true>` を実行して gate/up の出力バッファへ書きます。`TG=10016/10022` はそれぞれ IQ2_XXS/IQ2_S の packed-signs 用 dot 実装に結び付きます（同ファイル:938-941, 4267-4275, 5640-5651）。条件不一致ならこの分岐は何も起動せず、後続の IQ2_XXS reuse 判定または標準 grouped lane kernel へ進みます（同ファイル:5652-5680）。

## ログと測定値

この環境変数の判定や有効化だけを知らせるログはありません。分岐はカーネルを起動して戻るだけです。`native_expert_grouped` の後続処理では `check("native_expert_grouped/gu")` が SYCL エラー確認に使われますが、このフラグ専用の警告・終了経路はありません（同ファイル:5640-5651, 7413-7422）。確認した `docs/DETAILS.md` と関連する `docs/A770_SPEED_SPEC.md` に、この環境変数またはこの切替の測定値の記載は見つかりませんでした。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692` — helper の環境変数判定。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4243-4253` — lane 選択と IQ2_XXS reuse フラグ。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4267-4275, 938-941` — 固定形状 launcher と packed-signs 用 format dispatch。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5640-5680` — 対象変数の全読み取り箇所、ガード、fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6723-6740, 7308-7317, 7388-7425` — expert layout、SYCL grouped 呼び出し、先行経路と結果確認。
- `data/settings-register.json:40428-40444` — 設定レジストリ上の候補記録（環境値の読み取りではない）。
