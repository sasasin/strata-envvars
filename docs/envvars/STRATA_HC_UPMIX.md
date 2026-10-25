# `STRATA_HC_UPMIX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの内部動作は対象外。

## 役割

prefill の hyper-connection read で、BF16 up projection と `gr_mix_r` 相当の後段計算を `gr_upmix` カーネルにまとめます。通常経路が書き出す `gated`（FP32 の up projection 結果）を介さず、projection の累積値を使って mix を計算します。通常経路と加算順序が異なり、実装コメントは結果の差を「rounding-level」と説明しているため、通常の gfx1151 既定スイッチには含まれず、opt-in です。

この設定は prefill のバッチ処理にある hyper-connection 読み取りに作用します。decode 用の環境変数ではありません。`docs/STRIX_HALO.md` は fast configuration の例に `STRATA_HC_UPMIX=1` を記載していますが、そこに示す速度測定は複数スイッチをまとめた構成の結果で、upmix 単独の寄与ではありません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値の先頭が `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効候補 |
| それ以外（例: `0`, `true`, ` 1`） | 無効 |

文字列全体や数値としての妥当性は検証せず、`getenv()` の結果が非 null で、先頭文字が `'1'` かだけを比較します。`hc_upmix()` 内の `static const bool` に初回評価結果を保存するため、同一プロセスで後から環境を書き換えても再評価されません。CUDA と SYCL 側の prefill 実装にも同じ判定があります。

根拠: `src/prefill/prefill.cpp:322-325`, `sycl/src/prefill/prefill.cpp:257-260`。

## 有効になる条件

値が有効でも、各 hyper-connection half の読み取り時に次の条件が揃った場合だけ `gr_upmix()` を呼びます。

- prefill chunk の token 数 `T` が `STRATA_PF_SWITCH_MIN_T` 以上。後者は `std::atoll` で読み、未設定時は `0` です。文字列全体の厳密な検証はなく、`atoll` の変換結果を使います。したがってコード上の既定では `T` による追加制限はありません。docs の gfx1151 fast configuration は別途 `STRATA_PF_SWITCH_MIN_T=4096` を設定し、短い prompt を従来経路に残す例です。
- `STRATA_GR_UNFUSED` が有効でない。`gr_unfused()` も設定値の先頭文字が `1` かを判定します。
- `m.lo16_lo` と `m.mixed_bf_lo` が null。つまりこの経路で BF16 low-remainder の補正バッファを使っていないこと。
- up weight が `Bf16InF32` でデータがあり、形状が `ne0 == LR` かつ `ne1 == D`。
- backend と現在の device がカーネルの対応範囲内であること。カーネル実装は HIPCC 時だけ存在し、`gfx1100`, `gfx1101`, `gfx1102`, `gfx1150`, `gfx1151` を許可します（architecture 名の後ろは終端または `:` の場合に一致）。gfx1103 や gfx1152 などは対象外です。CUDA build では `gr_upmix()` は常に false を返し、通常経路に戻ります。

`STRATA_GFX1151_DEFAULTS` の既定リストにも `STRATA_HC_UPMIX` は含まれません。ソースは、このスイッチが出力 bit を変えるため opt-in に保つと説明しています。

## 実行時の詳細

prefill は hyper-connection の down projection と SiLU を済ませた後、条件が合えば `gr_upmix()` を実行します。対応外 device、`T <= 0`、または HIP device property の取得失敗などで `gr_upmix()` が false を返した場合、呼び出し側は通常の BF16 up projection を実行し、続けて `gr_mix_r` を行います。upmix が true の場合は fused kernel が `mixed` と利用可能な BF16/FP16 出力 image を作るので、後段の個別 mix を省略します。

upmix カーネルは BF16 の up projection を FP32 累積しながら、hyper-connection の4 stream分を mix します。実装注釈では、up GEMM の K 加算順が hipBLASLt と異なるため、通常経路と数値が同一とは限らないとしています。`docs/STRIX_HALO.md` も、このスイッチを丸め方が変わる opt-in 群に含めています。

評価時期は `hc_upmix()` の初回呼び出し時です。併用される `STRATA_PF_SWITCH_MIN_T` も同様に関数内 `static` 値として初回評価時にキャッシュされます。通常の起動経路では、HIP build は engine が switch を読む前に gfx1151 / gfx12 の architecture defaults を適用しますが、HC_UPMIX 自体はその既定値リストにないため、そこで自動的に設定されません。

### 比較診断

別変数 `STRATA_HC_UPMIX_CHECK=N` は、upmix 条件を満たした読み取りでのみ初回評価され、`std::atoi` の値を使います。正の値なら、対象となる最初の N 回は通常の up projection + mix を先に実行し、その後 upmix の結果も計算して同期し、`mixed` の相対 RMS と最大絶対差を stderr に出します。ログ形式は次の実装文字列です。

```text
strata: STRATA_HC_UPMIX_CHECK layer %lld half %d T %lld: mixed rel RMS %.3e, max |diff| %.3e (%s)
```

この比較はログ用コードであり、差の許容範囲を検査して失敗終了する処理ではありません。比較後に通常経路の出力を再び使うのではなく、upmix が成功すればその `mixed` を後続処理に使います。チェック回数が 0 以下なら比較コピーを行わず、upmix を直接使います。

## 根拠

- 環境変数判定と prompt switch の既定値: `src/prefill/prefill.cpp:317-325`。
- upmix 選択条件、診断比較、通常経路への fallback: `src/prefill/prefill.cpp:2564-2600`。SYCL 側の対応箇所: `sycl/src/prefill/prefill.cpp:2833-2883`。
- gfx11 device gate と CUDA build の fallback: `src/prefill/kernels.cu:1852-1870`。許可 architecture: `include/strata/kernels/gfx_arch.hpp:15-25`。
- fused kernel の計算内容と加算順の差についての実装注釈: `src/prefill/kernels.cu:1725-1730`; API の説明: `include/strata/prefill/kernels.hpp:28-31`。
- gfx1151 の switch が opt-in であること、fast configuration の設定例と測定条件: `include/strata/core/arch_defaults.hpp:3-10`, `src/core/arch_defaults.cpp:32-58`, `docs/STRIX_HALO.md:100-117,132-136`。
