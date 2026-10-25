# `STRATA_VERIFY_LEAN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL verifier の decode window graph から、`STRATA_VERIFY_NO_HOST` と device plan が有効な場合にホストが処理しない doorbell / flag 待ちなどのノードを省きます。通常の演算や device plan はこの変数では切り替わりません。無効化する値は先頭文字 `0` で始まる文字列です。

この名前を値として読む実装は `sycl/src/core/verify.cpp` に一箇所あります。CUDA/HIP 共通 verifier にはこの変数の読み取りはありません。

## 値と判定

`record_window()` 内の `static const bool` で、最初の window 記録時に一度だけ判定されます。`getenv()` が未設定か、設定値の先頭文字が `0` でなければ `lean_env` は真です。文字列全体の parse、数値変換、大文字小文字の判定はありません。

| 値 | `lean_env` |
|---|---|
| unset | 有効（既定） |
| 空文字 | 有効 |
| `0`, `0anything` | 無効 |
| `1`, `false`, `anything` | 有効 |

プロセス内で判定後に環境を書き換えても反映されません。値単独では処理を有効にせず、以下の条件と組み合わさったときだけ graph 構築に使われます。

根拠: `sycl/src/core/verify.cpp:792-802`。

## 有効になる条件

実際に `lean` が真になる条件はすべて満たす必要があります。

- SYCL backend の `Verifier::record_window()` を通る。
- `STRATA_VERIFY_NO_HOST` が設定され、空でなく、文字列全体が `0` でない。ここは先頭文字比較でなく `strcmp(v, "0")` を使うため、例として `00` は有効扱い。
- `device_plan_` が有効。これは `STRATA_VERIFY_DEVICE_PLAN` が設定され `atoi(value) != 0` で、かつ all-resident graph と `always_publish_` を使わない場合に設定される。
- step hook / split hook、remote expert optimization、`always_publish_`、`STRATA_VERIFY_STEPPED` がいずれも無効。

`device_plan_` の補助 device buffer 確保に失敗した場合、実装は `device_plan_` を false に戻すので lean も成立しません。all-resident graph は `device_plan_` と別経路であり、この変数による lean 対象ではありません。`STRATA_VERIFY_NO_HOST` は GPU が window 全体を処理するまでホストが layer ごとの応答をしない動作にも関係しますが、lean の graph 簡略化には上記の追加条件があります。

Intel の設計資料では `STRATA_VERIFY_NO_HOST` は全 expert が VRAM にある場合に限って使う設定として説明されています。device plan は各 layer の routed expert が resident の場合に device 側で plan し、非 resident expert に対する CPU doorbell 応答が必要な経路を省きます。外部 driver の挙動はここでは説明対象外です。

根拠: `sycl/src/core/verify.cpp:693-720,740-763,795-802,2180-2183`、`docs/INTEL.md:242-247`。

## 実行時の詳細

`lean` が真のとき、window の各 layer で次を省略します。

- device plan に伴う `doorbell_publish_res()`。
- device plan 完了 flag の待機と host plan の copy。
- PCIe staging 経路の待機、blob の staging / pointer 再配置。
- PCIe share の grouped kernel launch。
- CPU share の flag 待ち。

これらは `record_window()` が graph を記録する際に条件分岐されます。`STRATA_VERIFY_LEAN=0`（または `0` 始まりの値）では `lean` が偽になり、条件に該当するノードが通常どおり記録されます。変数専用のログ出力は見つかりません。

根拠: `sycl/src/core/verify.cpp:1332-1351,1444-1485`。

## 文書と測定値

`docs/INTEL.md` は Arc Pro B70（xe、32 GB）の IQ3_S に関する 0.1.43 の測定節で、`STRATA_VERIFY_NO_HOST` 下の不要 graph node を省く変更について「-2%」と記載しています。これは資料に記録された同節の測定値で、他の GPU やモデルでの性能を保証しません。条件の個別比較値や反復回数は当該箇所には記されていません。

根拠: `docs/INTEL.md:818-822,842`。
