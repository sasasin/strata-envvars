# `STRATA_TQ_ROWCH`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の grouped trellis expert kernel が、一つの CUDA block で処理する row chunk 数を指定します。gate/up と down の staged kernel で grid の x 寸法を調整し、block が複数 chunk を順に処理するために使います。標準の未設定値は 4 です。

## 値と判定

値は `std::atoi` で整数に変換し、その結果を 1〜32 に clamp します。文字列全体の妥当性検査やエラー報告はありません。

| 環境値 | 変換後と適用値 |
|---|---:|
| unset | 4 |
| 空文字 | `atoi("")` が 0 となり、1 |
| 整数 1〜32 | その整数 |
| 0 または負数 | 1 |
| 32 より大きい整数 | 32 |
| 数字で始まらない文字列 | `atoi` が 0 を返し、1 |
| 数字の後ろに文字が続く文字列 | 数字の先頭部分を変換して clamp（例: `4tail` は 4） |

`atoi` のため、先頭空白と符号は変換規則に従います。整数の範囲を超える文字列について、実装は別途検査していません。読み取り結果は関数内の `static const int` に保存されるため、最初の `tq_row_chunks()` 呼び出し後にプロセス環境を変更しても反映されません。

根拠: `src/kernels/cuda/iq_kernels.cu:3347-3355`。

## 有効になる条件

- 対象は grouped trellis 型（TQ2_T / TQK6 / TQK7）の expert decode です。通常の密行列や trellis 以外の型では helper を使いません。
- gate/up 側では、型が split trellis の staged grid kernel に対応し、旧 kernel (`g_old_kernels`) と型別の `split_off<TG>()` が無効、`g_stage_grid` と trellis staging (`tq_stage_on()`) が有効な経路で row chunk 数を使って grid を縮めます。CUDA compute capability 6.0 でなくても、staging が有効な trellis 型なら対象です。
- down 側では、`n_ff == 640`、旧 kernel と `STRATA_NO_SUB16_GU` が無効、型別 `split_off<TD>()` が無効、down 型が TQ2_T または TQK7 で、`tq_stage_on()` または `tq_sub8_on()` が有効な場合に `tq_sub8` が成立し、row chunk 数を grid 計算へ使います。単に down の staged kernel が選ばれただけでは、row chunk 数を使わない経路があります。
- `STRATA_IQ_STAGE_GRID=0` なら `g_stage_grid` が無効になり、staged kernel を選ぶ gate/up 経路は使いません。`STRATA_TQ_STAGE` と `STRATA_TQ_SUB8` の設定も staging / sub8 経路の選択に関係します。これらは別変数であり、本書ではその完全な挙動を扱いません。
- 160-dot の gate/up row が `tq_sub8_on()` の専用経路に入る場合は、32-row 単位の grid を直接設定するため、gate/up 側で `STRATA_TQ_ROWCH` を使いません。down 側で条件を満たせば同じ呼び出し中に row chunk 数を使う場合があります。
- CPU、SYCL、Metal 実装にはこの環境変数の直接参照がありません。

根拠: `src/kernels/cuda/iq_kernels.cu:3280-3283,3310-3328,3334-3345,4073-4100,5232-5236`。名前の完全一致検索では、環境値を読む実装は `iq_kernels.cu:3350` のみでした。

## 実行時の詳細

gate/up の staged trellis 経路は `tq_row_chunks()` の値で `sg.x` を `(grid.x + chunks - 1) / chunks` に設定します。kernel は block ごとに row chunk を進め、共有メモリへ codebook を置くコストを複数 chunk で共有します。down 側も同様に `gd.x` を chunk 数で割り、staged down kernel が各 block で複数 chunk を処理します。値は block の割り当てと grid 寸法を変えますが、ソースはこの変数によるログや警告を出しません。

`docs/GYRO.md` と `docs/release-notes-0.2.2.md` は trellis staging / row kernel の測定を説明していますが、`STRATA_TQ_ROWCH` の値ごとの比較や、この変数単独の性能効果は記載していません。そのため、本書では性能差を断定しません。

根拠: `src/kernels/cuda/iq_kernels.cu:1962-1999,3347-3355,4091-4099,5232-5236`; 関連資料: `docs/GYRO.md:123-143`, `docs/release-notes-0.2.2.md:34-37`。
