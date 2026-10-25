# `STRATA_PF_BK64`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドの gfx11 向け FP16 prefill GEMM で、出力幅 `N >= 1024` かつ内積幅 `K` が 64 の倍数の場合に、BK 64 の専用 WMMA kernel を使うかを選びます。無効にすると、この幅のケースにも BK 32 の kernel を使います。この変数自体は prefill GEMM 経路を有効化しません。

## 値と判定

関数内の `static const bool` として一度だけ読み、文字列全体の parse はせず先頭文字を調べます。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| 空文字 | 有効（設定値の先頭は終端文字で、`0` ではない） |
| その他（例: `1`, `true`, `false`, `-1`） | 有効 |

空白や数値としての妥当性、大文字小文字は検査しません。プロセス起動後に環境値を変更しても、最初の判定後は反映されません。

## 有効になる条件

この切り替えが使われるには、HIP ビルドで `STRATA_PF_GEMM=1` が選択され、`Gemm::f16` の `T >= STRATA_PF_SWITCH_MIN_T` を満たすなどして専用経路が呼ばれ、さらに `strata_pf_gemm_f16_ld()` が入力検査を通過する必要があります。入力検査には `T >= 64`、`N >= 512`、`K` が 32 の倍数、`beta` が 0 または 1、先行次元の整合性が含まれます。また実行デバイスは WMMA 対応 gfx11（gfx1100/1101/1102/1150/1151）でなければなりません。非 HIP ビルドや未対応デバイスではこの専用 kernel は実行されません。

値が有効でも、BK 64 kernel を選ぶ追加条件は `N >= 1024` と `K % 64 == 0` です。`N < 1024` は別の BK 32 kernel へ進み、`N >= 1024` でも `K` が 64 の倍数でない場合は BK 32 kernel へ進みます。したがって `STRATA_PF_BK64=0` は狭い出力幅の経路には影響しません。

## 実行時の詳細

`Gemm::f16()` は `STRATA_PF_GEMM` と `STRATA_PF_SWITCH_MIN_T` による条件を満たすと、まず `strata_pf_gemm_f16()` を呼びます。これは leading dimension を既定値にして `strata_pf_gemm_f16_ld()` に渡します。後者は引数とデバイスを検査した後に `STRATA_PF_BK64` を読み、条件を満たす場合は 128 行 × 256 列タイルの `kernel_bk64` を起動します。無効または形状条件外なら、`N >= 1024` では `kernel<256, 64>`（テンプレート内の K tile は 32）、それ以外では `kernel<128, 32>` を起動します。

kernel 起動後の戻り値は `hipGetLastError() == hipSuccess` です。prefill 経路が `false` を返した場合、呼び出し元は次の GEMM 経路を試します。パディング済み入力の native 経路でも、dequantize 後に同じ `strata_pf_gemm_f16_ld()` が呼ばれる場合があります。

## 根拠

- `src/prefill/wmma_gemm.cu:681-707`: 引数・GPU 条件、環境値の読み取りとキャッシュ、BK 64 / BK 32 の dispatch。
- `src/prefill/wmma_gemm.cu:314-324,398-402`: BK 32 template kernel と BK 64 専用 kernel の寸法。
- `src/prefill/gemm.cu:675-688`: HIP の FP16 GEMM から `STRATA_PF_GEMM` 経由で呼ぶ条件、および失敗時に後続経路へ進む構造。
- `src/prefill/gemm.cu:819-833`: 条件を満たす padded native 入力で同じ専用 GEMM を呼ぶ経路。
- `docs/STRIX_HALO.md:100-116`: `STRATA_PF_GEMM` が opt-in の prefill FP16 projection 用 GEMM であることと、関連する token 閾値の説明。`STRATA_PF_BK64` 自体の説明はこの資料にはありません。

