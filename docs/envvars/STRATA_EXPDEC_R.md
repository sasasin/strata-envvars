# `STRATA_EXPDEC_R`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の EXPDEC gate/up カーネルで、1 lane がまとめて計算する出力行数 `R` を選びます。値が 2 と判定された場合だけ `R=2`、それ以外は `R=1` です。これは gate/up の実行形状を変える調整値で、EXPDEC 自体を有効にするスイッチではありません。EXPDEC の有効化は別の `STRATA_EXPDEC` が担います。

## 値と判定

環境変数の読み取りには `env_int_or()` を使います。環境変数が未設定、または空文字列なら既定値 `1` です。それ以外は `atoi()` で整数変換し、その値を保持します。最終的に `expdec_r()` は保持値が厳密に `2` の場合だけ 2 を返し、それ以外を 1 に正規化します。

| 設定例 | 読み取り値 | カーネルで使う R |
|---|---:|---:|
| 未設定、空文字列 | 既定値 1 | 1 |
| `2`, `2tail` | `atoi()` の結果 2 | 2 |
| `1`, `0`, `-2`, `junk`, `junk2` | `atoi()` の結果は 1、0、-2、0、0 | 1 |

`atoi()` は文字列全体の厳密な検証をしないため、先頭の空白や符号の後にある数字を変換し、数字以降の文字列は無視します。先頭から整数として読めない値は 0 となり、結果として `R=1` です。空白だけの非空値も `R=1` です。値に範囲エラーを返す検査はありません。

## 有効になる条件

- この調整値を使うのは CUDA の EXPDEC gate/up カーネルです。ソースの EXPDEC 実装は `!__HIPCC__` の条件下に置かれています。
- EXPDEC の gate/up 経路が選ばれる必要があります。`STRATA_EXPDEC` が無効、旧 multi kernel が有効、または layout が対応外の場合、呼び出し元は通常のカーネルを使い、この値は実行に影響しません。
- 対応 layout は `gu_type` が 16、17、18、21、22 のいずれかで、`n_embd == 32 * ED_XB`、`n_ff > 0` かつ 64 の倍数です。
- 実際に使われる `R` は環境変数の数値をそのまま使うのではなく、`2` かどうかだけで決まります。1 以外の値を設定しても R=2 にはなりません。

## 実行時の詳細

`g_expdec_r` は `iq_kernels.cu` のグローバル初期化で一度読み取られ、同じプロセス中はその値を使います。したがって、読み取り後にプロセス環境を変更しても反映されません。なお、`native_expert_set_expdec_params()` が `gu_rows_per_lane > 0` の値を受け取ると、環境変数由来の値を上書きします。

EXPDEC gate/up launch は `expdec_r()` を使って R=1 または R=2 のテンプレート kernel を選びます。`R` は起動行列の rows-per-block 算出にも使われ、その基準は `16 * R` 行です。初めて対応する形式で EXPDEC kernel を使う際、stderr の `strata expdec:` 行に実際の `R` と rows-per-block が表示されます。対応外なら `not covered: the default kernel runs` と出ます。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3934-3953` — `atoi()` を使う共通 helper、既定値 1、R の正規化。
- `src/kernels/cuda/iq_kernels.cu:3955-3958` — gate/up 対応形式と layout 条件。
- `src/kernels/cuda/iq_kernels.cu:3976-3995` — rows-per-block の基準と R=1/2 の kernel 選択。
- `src/kernels/cuda/iq_kernels.cu:4015-4019` — 実際に選ばれた R を含む stderr ログ。
- `src/kernels/cuda/iq_kernels.cu:5020-5030` — EXPDEC の明示設定 API と、パラメーターによる `g_expdec_r` 上書き。
- `docs/EXPERTDEC.md:1-4,16-29,31-42` — CUDA 限定、EXPDEC 有効化と gate/up の役割・対応形式についての設計資料。
