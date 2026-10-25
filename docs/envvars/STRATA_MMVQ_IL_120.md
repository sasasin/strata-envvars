# `STRATA_MMVQ_IL_120`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）が 2〜4 列を処理するとき、compute capability 12.0 かつ SM 数が 80 以上の GPU に専用の行数テーブル `kIlRows_120` を使うか選びます。無効にすると同じ GPU は共通テーブル `kIlRowsShared` を使います。変数は interleaved kernel 全体を有効・無効にするものではありません。

## 値と判定

`il_env_on()` は `getenv()` の結果が未設定なら `true`、設定済みなら先頭文字が `'0'` でない場合に `true` を返します。文字列全体の parse は行いません。

| 値 | 専用テーブルを選ぶ判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（先頭文字が NUL で `'0'` ではない） |
| `1`、`true`、`2`、`false` など、先頭文字が `0` 以外 | 有効 |
| `0`、`0anything` など、先頭文字が `0` | 無効。共通テーブルへ戻る |

判定結果は `native_mmvq_il_rows_for()` 内の関数ローカル `static const bool` に保持され、最初の評価後は同じプロセスで環境を変更しても再評価されません。

## 有効になる条件

この変数が選択に影響するのは、CUDA 実装で、GPU の compute capability が 12.0、かつ SM 数が 80 以上と判定された場合です。コードは該当デバイスを capability 値 `1201` としてテーブル検索します。80 SM 未満の 12.0 GPU は capability 値 `120` のままなので、変数の値に関係なく共通テーブルです。

さらに、行数選択に到達するのは 2〜4 列の場合です。5〜8 列は先に `STRATA_MMVQ_IL_WIDE` を使う別テーブル経路へ進み、1 列は single-column 用テーブル経路へ進みます。`STRATA_MMVQ_IL_ROWS` に該当する独自設定があれば、それがアーキテクチャ別テーブルより先に返されるため、この変数はその呼び出しの選択を変えません。Q3_K は `STRATA_MMVQ_IL_Q3K` が無効なら、専用テーブル選択前に通常 kernel に戻ります。

通常の verify 経路では `STRATA_MMVQ_IL=0` が interleaved 経路全体を止めます。2〜4 列の interleaved matvec 自体が使われるには、対応 quant type、テーブルの該当セルが非ゼロ、正確な multi-column layout、および対応 GPU architecture などの条件も必要です。HIP 側の実装は `native_mmvq_il_supported()` が常に `false` を返し、通常 matvec を呼ぶため、この変数は HIP 実行では作用しません。

## 実行時の詳細

`native_mmvq_il_rows_for()` は独自行設定を確認した後、2〜4 列の経路で Q3_K の設定を確認し、初期値として共通テーブルを選びます。デバイス値 `1201` に一致し、かつ `STRATA_MMVQ_IL_120` が有効なら `kIlRows_120` に切り替えます。対象型と出力行数クラスに対するテーブル値が 0 なら、`native_mmvq_il_supported()` は未対応と判定し、呼び出し元は `native_mmvq()` を使います。非ゼロなら interleaved kernel が呼ばれます。この変数自体についてのログ出力はありません。

コードコメントと `docs/MMVQ_IL_TABLE.md` によると、`kIlRows_120` は RTX PRO 5000 Blackwell（110 SM）で測定された表です。共通表は RTX 3060 と RTX 5070 の測定に基づくと説明されています。これらの資料は表の作成根拠であり、この環境変数による性能差を別の GPU で確認した結果ではありません。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:3092-3095` — unset と設定値の判定方法。
- `src/kernels/cuda/native_mmvq.cu:3038-3047,3105-3108` — 12.0 専用テーブルと `1201` の登録。
- `src/kernels/cuda/native_mmvq.cu:3112-3138,3143-3174` — 独自行設定の優先順位、列数別経路、Q3_K 条件、専用表と共通表の選択。
- `src/kernels/cuda/native_mmvq.cu:3177-3195` — capability と SM 数の取得、および 80 SM 以上を `1201` に分類。
- `src/kernels/cuda/native_mmvq.cu:3229-3273` — 対応条件、通常 kernel への fallback、HIP stub。
- `src/core/verify.cpp:164-165,1320-1342,1375-1384,1607-1614,2233-2241` — verify 側の全利用箇所と `STRATA_MMVQ_IL` による上位ゲート。
- `docs/MMVQ_IL_TABLE.md:1-17`、`docs/DETAILS.md:2483-2485` — 表の説明、測定対象と関連する環境変数。
