# `STRATA_EXPDEC`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の `native_expert_grouped` が verify window 内の routed expert を処理するとき、対応する gate/up の grouped kernel を EXPDEC kernel に切り替えます。EXPDEC kernel は group の q8_1 activation rows を shared memory に staging し、expert weight の複数行で再利用します。出力計算は既定 kernel と同じ演算順を保つ設計です。down projection もこの変数だけで有効になるのではなく、`STRATA_EXPDEC_DOWN` で別途 opt-in します。

これは通常の利用者向け engine に組み込まれた CUDA kernel 選択です。実装は `src/kernels/cuda/iq_kernels.cu` にあり、CPU/HIP/SYCL の同機能実装はこの調査対象ソースにはありません。

## 値と判定

数値 parse や文字列全体の比較はしません。共通 helper `env_on()` が `getenv()` の結果を調べ、値が未設定でなく、空文字でなく、先頭文字が `0` でなければ有効とします。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0anything` | 無効（先頭文字が `0`） |
| `1`、`true`、`false`、`2`、空白で始まる文字列など | 有効（空でなく先頭文字が `0` 以外） |

大文字小文字、後続文字、数値としての妥当性は検査されません。したがって `false` も有効です。判定結果は `g_expdec` に初回使用時に保存されます。通常はプロセス起動後に環境を書き換えても再読込されません。CUDA kernel API の `native_expert_set_expdec(int)` を呼ぶコードはこの値を直接上書きできます。

根拠: `src/kernels/cuda/iq_kernels.cu:3273-3276,3938-3940,5020-5021`。

## 有効になる条件

変数が有効でも、対応する grouped expert kernel に到達し、対象 layout が条件を満たす場合だけ EXPDEC kernel が使われます。

- gate/up は `gu_type` が 16、17、18、21、22 のいずれかで、`n_embd == 32 * ED_XB`、`n_ff > 0` かつ 64 の倍数であることが必要です。
- `STRATA_OLD_IQ_MMVQ` が有効な場合は EXPDEC を使いません。
- down は既定では常に通常 kernel です。`STRATA_EXPDEC_DOWN` が真で、さらに `d_type == 42`、または `d_type == 20` かつ `STRATA_EXPDEC_D20` が真であり、`n_ff == 32 * ED_HB`、`n_embd > 0` かつ 128 の倍数の場合に EXPDEC down kernel が対象になります。
- 上記以外の format/layout では通常 kernel に fallback します。

このソースは CUDA 実装です。実行環境で CUDA backend が使われない場合、この変数による kernel 切替は起きません。ゲート/形式以外の実行条件や verify window の選択は呼び出し側に依存します。

根拠: `src/kernels/cuda/iq_kernels.cu:3955-3962,4030-4043,4063-4070,5200-5205,5262-5269`。

## 実行時の詳細

`native_expert_grouped` の gate/up および down の各処理で EXPDEC 関数を試し、成功時は専用 kernel を起動します。対象外または無効の場合は呼び出し元が既定 kernel を起動します。EXPDEC kernel は group の activation rows を shared memory に配置して、複数の weight rows で再利用する構成です。gate/up の標準設定は lane あたり1 row、down の標準設定は4 rowsですが、調整用の別環境変数があります。

有効モードで各 (role, format, taken/not-taken) に初めて遭遇すると stderr に `strata expdec: CUDA...` の行を出します。対応 layout なら選択 kernel、R、rows per block、grid が記録され、対象外なら `not covered: the default kernel runs` と記録されます。モードが無効の場合、この EXPDEC 診断行は出ません。

API から設定を変えず環境変数を使う通常経路では、モードは初回使用時に評価・cache されます。グラフ capture 中に起動された場合は同じ kernel が graph に capture され、後の実行では graph に記録された処理が使われます。

根拠: `src/kernels/cuda/iq_kernels.cu:3938-3953,3998-4026,4030-4070,5200-5205,5262-5269`。

## 文書・測定値との照合

`docs/EXPERTDEC.md` は EXPDEC を CUDA 限定・opt-in とし、対応 gate/up 形式と down の追加 opt-in、bitwise 同一性、engine / micro-benchmark の測定を記載しています。ここにあるベンチマーク結果は資料の記載であり、この調査で再測定したものではありません。同資料の RTX 2080 Ti、131k decode の nsys 例では T=2 の gate/up kernel 時間が 2.58 ms から 2.07 ms、T=4 では 4.16 ms から 3.20 ms と報告され、同条件の down Q2_0 は `STRATA_EXPDEC_DOWN=1` で約10%遅くなったとされています。`docs/DETAILS.md` の集計表では bit-exact、RTX 3060 で +0.5%、A4000 で短い context に +1〜5% と記載されています。これらは文書記載条件の結果であり、他の GPU やモデルでの性能を保証しません。

## 根拠

- 値判定と初回評価: `src/kernels/cuda/iq_kernels.cu:3273-3276,3938-3940`
- layout の条件、既定 kernel への fallback: `src/kernels/cuda/iq_kernels.cu:3955-3962,4030-4070,5200-5205,5262-5269`
- 診断ログと graph capture 表示: `src/kernels/cuda/iq_kernels.cu:3998-4026`
- EXPDEC の方式と測定説明: `docs/EXPERTDEC.md:1-40,90-101`
- 概要測定値: `docs/DETAILS.md:2508-2513`
