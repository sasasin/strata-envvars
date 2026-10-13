# `STRATA_NO_MMVQ_ROWS2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

native MMVQ の multi-column（`ncols` が 2〜8）exact kernel で、入力幅が大きい場合の出力行数を、1 block/work-group あたり2行から1行に切り替えます。既定では2行のままです。環境変数名に `NO` が含まれますが、これはMMVQ全体を無効にする設定ではありません。

## 値と判定

CUDA と SYCL の両実装で、`getenv()` の結果が null でなく、かつ先頭文字が NUL と `'0'` のどちらでもなければ有効です。値全体の parse や比較はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。2行の経路を使う |
| 空文字 | 無効。`v[0]` が NUL |
| `0`、`0abc` | 無効。先頭文字が `'0'` |
| `1`、`true`、`false`、`2abc`、空白で始まる値 | 有効。先頭文字が NUL / `'0'` 以外 |

大文字小文字、空白の trim、数値としての妥当性は検査されません。通常は `STRATA_NO_MMVQ_ROWS2=1` のように指定します。

値は `launch_multi_n<F, NCOLS>()` の関数内 `static const bool` として保持されます。したがって各テンプレート特殊化で初めてこの関数を通った時に評価され、その特殊化では以後の環境変更は反映されません。異なる `F` または `NCOLS` の特殊化はそれぞれ初回に評価します。

## 有効になる条件

- `ncols` が2〜8で、`small_mmvq()` から multi-column 経路に入ること。
- CUDA の wave 経路など、先に別の実装へ分岐していないこと。
- `g_multi_exact` が true であること。false の場合は別の multi-column kernel に入り、この環境変数を読みません。
- 入力幅の判定 `n_in / F::DIV >= F::BPI` を満たすこと。

最後の条件を満たさない小さい入力では、変数が有効でも2行の経路を使います。判定は整数除算による `n_in / F::DIV` です。`F::DIV` と `F::BPI` は量子化形式 `F` の trait 定数であり、型によって実際の閾値は異なります。

## 実行時の詳細

条件を満たす場合、CUDA は `n_out` 個の block を起動し、`ROWS=1` の exact multi-column kernel を選びます。SYCL は同じ `ROWS=1` の kernel を `n_out` 個の work-group で起動します。環境変数が無効、または入力が閾値未満なら `ROWS=2` とし、出力行数を2で割り上げた数の block/work-group を使います。`STRATA_TSUM` が有効な場合も、1行/2行の選択自体は同じで、それぞれ対応する reduction kernel を選びます。

この設定によるログ出力やエラー分岐はありません。ここで確認できる効果は kernel と grid/work-group の選択です。`native_mmvq_pair()` は独自の固定 `ROWS=1` kernel を使い、この環境変数を参照しません。

## 根拠

- CUDA の読み取り・閾値分岐・ROWS選択: `src/kernels/cuda/native_mmvq.cu:1261-1290`。
- CUDA の上位呼び出し（`ncols > 1` の場合）: `src/kernels/cuda/native_mmvq.cu:1642-1655`。
- SYCL の読み取り・閾値分岐・ROWS選択: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2005-2100`。
- SYCL の上位呼び出し（`ncols > 1` の場合）: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2230-2245`。
- `STRATA_TSUM` の初回評価: `src/kernels/cuda/native_mmvq.cu:1156-1160`。SYCL にも同等の `s26_tsum_on()` がある。
- pair kernel が固定で1行を使用: `src/kernels/cuda/native_mmvq.cu:2406-2414`。
- `docs/DETAILS.md` と `docs/MMVQ_IL_TABLE.md` を照合しましたが、この変数の値判定や効果を説明する記載は見つかりませんでした。上記の動作説明はソース実装に基づきます。
