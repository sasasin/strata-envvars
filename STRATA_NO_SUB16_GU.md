# `STRATA_NO_SUB16_GU`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有の CUDA/HIP 共用 kernel 実装と、別 backend の SYCL 実装。外部ライブラリの環境変数動作は対象外。

## 役割

CUDA/HIP 側では、grouped native expert の分割量子化形式について、特定の gate/up と down kernel が使う小幅サブワープ（sub16 / sub-down）経路を無効にし、通常の 32 lane warp 行経路を選びます。SYCL 側では同じフラグを読みますが、GU kernel のサブワープ切替には使われず、`n_ff == 640` の down 処理で使う行数・launch grid を既定の 8 行に戻します。

## 値と判定

両実装は共通の `env_on()` で判定します。環境変数が未設定、空文字、または先頭文字が `0` の場合は無効。それ以外は有効です。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`, `0anything` | 無効 |
| `1`, `true`, `false`, `2`, 空白から始まる文字列 | 有効 |

大文字小文字や後続文字は検査されません。`false` も先頭が `f` のため有効です。根拠: `src/kernels/cuda/iq_kernels.cu:1951-1957`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2824`。

## 有効になる条件

- **CUDA/HIP 共用実装:** kernel translation unit の初期化時に `g_no_sub16_gu` へ値を読み込みます。grouped expert の分割形式で、旧 kernel (`STRATA_OLD_IQ_MMVQ`) に切り替わっていない場合に、GU は `native_gu_multi_kernel<..., SUB16=false>`、down は `native_down_multi_kernel<..., SUB_DOWN=false>` を選びます。非分割形式は元から通常 kernel に進むため、このフラグでの変更はありません。`STRATA_OLD_IQ_MMVQ` が有効なら旧 kernel が先に選ばれ、この切替は使われません。根拠: `src/kernels/cuda/iq_kernels.cu:2666-2693`。
- GU の小幅サブワープ経路は `L.n_embd / 32 == 80`（`n_embd == 2560`）のときに実行されます。無効化時はこの条件専用分岐をコンパイル時に除き、通常の warp 行処理に進みます。`native_expert_grouped` の grid も、旧 kernel でなく、分割 GU 形式で `n_embd == 2560` の場合に 16 行単位から `GU_ROWS` に戻ります。根拠: `src/kernels/cuda/iq_kernels.cu:1241-1295,3492-3495`。
- down の sub-down 分岐は `n_ff == 640`（`hb == 20`）かつ down 型が 20 または 42 の場合に存在します。無効化時には該当分岐を使わず、generic down kernel と 8 行単位の grid を使います。他の `n_ff` / down 型では sub-down 分岐自体が成立しません。根拠: `src/kernels/cuda/iq_kernels.cu:1361-1374,1417-1423,1462-1469,3582-3584`。
- `STRATA_EXPERT_V2K` の専用経路は `native_expert_grouped` 内で通常の GU/down dispatch より先に処理して return するため、このフラグの grid / kernel 切替を通りません。CUDA/HIP の別の expert layout 専用 early-return 経路も通常 dispatch を迂回できます。根拠: `src/kernels/cuda/iq_kernels.cu:3478-3495,3582-3594`。
- **SYCL:** `g_no_sub16_gu` は GU dispatch では参照されません。SYCL の GU multi kernel は、条件に応じて `SUB16=false` を使う設計であり、この環境変数はそこを切り替えません。環境変数の直接の効果は、`n_ff == 640` かつ旧 kernel を使わない場合に算出する down grid の行数です。down 型 20 では 32 行、型 42 では 16 行、それ以外およびフラグ有効時は 8 行となります。grouped dispatch が実行される時にのみこの grid 値が使われます。根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4160-4194,5201-5204`。

## 実行時の詳細

CUDA/HIP と SYCL の各 translation unit は、グローバル変数 `g_no_sub16_gu` の初期化時に環境を一度読みます。値は以降の dispatch で参照され、リクエストごとの再読み込みや、この変数を更新する setter は確認できません。したがって、プロセス起動後に環境を変更しても初期化済みの値は更新されません。CUDA/HIP の env 判定は空文字を無効にしますが、`STRATA_IQ_STAGE_GRID` など他の個別 parse 方式とは異なり、`STRATA_NO_SUB16_GU` 自身には既定 ON の扱いはありません。

この切替は kernel と launch grid の選択であり、該当コードにこの変数専用のログ、警告、エラー出力はありません。ソース上に性能測定や正確性測定の結果は見当たりません。SYCL の sub-warp variant 全般についてのコメントはありますが、この環境変数による性能効果を示す根拠にはなりません。

## 根拠

- 値の判定と初期読み込み: `src/kernels/cuda/iq_kernels.cu:1951-1957`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2813-2824`。
- CUDA/HIP GU/down の dispatch: `src/kernels/cuda/iq_kernels.cu:1241-1295,1361-1374,1417-1423,1462-1469,2666-2693,3492-3495,3582-3594`。
- SYCL GU multi dispatch と down 行数: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4160-4194,5201-5204`。
- `docs/DETAILS.md` と `docs/` 内には、この変数を直接説明する記載を確認できませんでした。
