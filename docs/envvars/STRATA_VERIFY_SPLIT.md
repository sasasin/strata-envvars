# `STRATA_VERIFY_SPLIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL の stepped verifier が decode window を graph segment に分ける位置を追加で設けるかを制御します。ON のとき、各 layer/group の VRAM expert 部分を記録した直後にも segment を閉じます。これにより、その先の CPU expert 計算と GPU の次 segment を重ねるための境界を作ります。

これは検証計算そのものを選ぶ設定ではなく、stepped 実行での graph 分割点を制御する設定です。現在の Strata ソースでこの名前を環境から読む箇所は `sycl/src/core/verify.cpp` の1か所です。

## 値と判定

`getenv()` の結果の有無と先頭文字だけで判定します。文字列全体の parse、数値変換、大文字小文字の変換はありません。

| 値 | `split_on` | 説明 |
|---|---:|---|
| 未設定 | ON | `e == nullptr` なので `!(e && ...)` は true |
| 空文字 | ON | 設定済みだが `e[0]` は `\0` であり `'0'` ではない |
| 先頭が `0` | OFF | `0`, `0anything` など |
| それ以外 | ON | `1`, `false`, `off`, 空白始まりの値など |

値は `capture_segments()` が最初に呼ばれた時に関数内 `static const bool` として評価されます。そのプロセス内ではキャッシュされ、後から環境を書き換えても再評価されません。

根拠: `sycl/src/core/verify.cpp:1704`。

## 有効になる条件

変数が ON でも、次の経路でのみ segment split に使われます。

- `STRATA_VERIFY_STEPPED` による stepped mode が有効であること。コードの `env_on()` は未設定・空文字・先頭が `0` の値を OFF、それ以外を ON とします。
- all-resident の verifier window ではないこと（`!ar_on()`）。
- `STRATA_VERIFY_EAGER` が未設定であること。設定されていると graph capture / `capture_segments()` を通らず、window body を eager replay します。

この候補は stepped mode が有効になる条件を変えません。`STRATA_VERIFY_STEPPED` と `STRATA_VERIFY_EAGER` の設定有無を確認した上で評価してください。

根拠: `sycl/src/core/verify.cpp:92-103,1726-1733`。

## 実行時の詳細

`capture_segments()` は通常、window graph を layer/group ごとの doorbell serve point で区切ります（`step_hook_`、segment kind `1`）。`STRATA_VERIFY_SPLIT` が ON なら `step_hook2_` も設定し、GPU が VRAM-resident expert group を計算した直後に追加の境界（segment kind `0`）を記録します。split hook は非 all-resident 経路で VRAM group の処理後に呼ばれます。

stepped window の実行時、次の segment が split point で終わる場合、serve 処理は CPU pool の処理と GPU segment をパイプラインできます。`STRATA_VERIFY_PIPE` は unset または先頭が `0` 以外なら ON、先頭 `0` なら OFF です。OFF の場合は pool を先に同期実行してから segment を投入するため、この分割だけではその overlap を行いません。`STRATA_VERIFY_SPLIT=0` なら追加の split segment がなくなり、VRAM group 後も後続の wait / PCIe group / CPU 結果処理を含む segment として実行されます。

コード上、追加境界は GPU 計算の順序や入力を変更する分岐ではなく、segment capture と投入タイミングを変えます。ただしこの環境変数単独の数値的な効果・性能値は資料から確認できません。

根拠: `sycl/src/core/verify.cpp:1687-1709,1440-1458,2088-2119,2138-2143`; `sycl/include/strata/core/verify.hpp:358-369`。

## 文書との照合

`sycl/src/core/verify.cpp` と verifier header は stepped mode の serve point / split point、および `STRATA_VERIFY_PIPE=0` 時の serial segment 動作を説明しています。`docs/DETAILS.md`、`docs/INTEL.md`、`docs/INTEL_ARC.md` では stepped mode の説明を確認できますが、`STRATA_VERIFY_SPLIT` 自体の値判定や既定値、個別の性能測定は見つかりませんでした。したがって、ここでは実装にある分岐だけを記述し、性能値は記載していません。
