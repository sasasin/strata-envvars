# `STRATA_DF2_MM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal 版 DFlash2 の Q8 行列積カーネルについて、simdgroup ごとの出力行数 `R` と threadgroup 内の simdgroup 数 `SG` を選びます。指定値から `df2_mm_R_SG` という Metal 関数名を作り、グリッドと threadgroup の大きさを決めます。CUDA/HIP 版の DFlash2 ではこの変数を読みません。

## 値と判定

読み取り時に `R=2, SG=8` を初期値にし、変数が設定されていれば `sscanf(value, "%d,%d", &R, &SG)` を一度実行します。2 整数の全体一致や後続文字の検査、範囲 clamp はありません。

| 値 | 結果 |
| --- | --- |
| 未設定 | `R=2, SG=8`（既定） |
| 空文字、先頭が整数でない文字列 | 変換されず既定値のまま |
| `4` | 1 個目だけ変換され `R=4, SG=8` |
| `4,16` | `R=4, SG=16` |
| `4,16tail` | 先頭の 2 整数を読み、後続の `tail` は無視 |
| 2 個目が欠ける・変換できない | 変換できた項目だけ更新し、残りは既定値 |

コンパイルされている関数名は `R` が 1, 2, 4, 8、`SG` が 4, 8, 16 の組み合わせのうち、`(8,16)` を除く 11 組です。その他の値も読み取り時には拒否されず、その組み合わせの関数名を要求します。

根拠: `metal/src/engine/dflash2.inc:435-445`、`metal/src/engine/msl/dflash2.metal:425-429,485-486`。

## 有効になる条件

- Metal バックエンド上で DFlash2 drafter が実行されること。Metal 実装は `metal/src/engine/dflash2.inc` にあり、通常の行列呼び出しは `df2_mmn()` から `df2_mm()` に進みます。
- 対象テンソルが Q4_0 ではないこと。Q4_0 は `df2_mm4()` に分岐するため、この変数の選択対象外です。
- 値が有効な関数名に対応すること。shader にない名前や Metal pipeline を作れない値には代替値への fallback がありません。

CLI 引数や他の環境変数でこの値を上書きする処理は見つかりませんでした。Metal の DFlash2 は `--draft dflash2` 経路で利用され、行列カーネルは context 更新および各 DFlash2 block の射影で呼ばれます（`metal/src/engine/dflash2.inc:497-503,558-569,598-616`）。

## 実行時の詳細

環境変数は `Window::df2_mm()` 内の function-local `static const` 初期化で評価されます。したがって最初の該当行列カーネル要求時に一度だけ読み、同じプロセス内の以後の呼び出しでは保存したペアを使います。プロセス起動後、最初の評価より前なら変更が反映されますが、評価後の変更は反映されません。

選択したペアから `df2_mm_R_SG` の pipeline を取得し、`grid[0] = ceil(rows / (SG*R))`、`tg[0] = SG*32` を設定します。要求された関数が Metal library にない場合は `mtl: no function <name> ...` を stderr に出して終了コード 3 で終了します。関数はあるが pipeline 作成に失敗する場合も `mtl: pipeline <name>: ...` を stderr に出して終了コード 3 で終了します。読み取り側で範囲検証や既定値への戻しは行いません。

根拠: `metal/src/engine/dflash2.inc:435-446`、`metal/src/engine/window.cpp:267-273`、`metal/src/mtl_rt.mm:484-521`。
