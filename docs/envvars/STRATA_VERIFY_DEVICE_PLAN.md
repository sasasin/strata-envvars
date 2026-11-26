# `STRATA_VERIFY_DEVICE_PLAN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP と SYCL の verify window で、レイヤーの expert 配置計画の一部を GPU 側の `resident_plan` に作らせる開発・診断向けスイッチです。対象は routed expert が device の residency table 上で VRAM resident な場合の計画で、非 resident expert の CPU/PCIe 処理全体を無条件に GPU へ移す設定ではありません。初期化後は CUDA/HIP が `device_plan_`、SYCL が同名状態を使い、GPU が計画した group の host-side plan/row 待ちを skip flag と照合します（`engine/src/core/verify.cpp:1414-1428, 2686-2699, 2863-2908`; `engine/sycl/src/core/verify.cpp:919-925, 1612-1621, 1761-1789`）。

## 値と判定

両実装とも主な判定は `getenv` の値を `std::atoi` に渡し、結果が 0 以外かどうかです。文字列全体の検証や `true` の特別扱いはありません。未設定と空文字は無効、`1` や `-1` は有効、`0` と `0anything` は無効です。`atoi` のため、先頭空白の後の数字は変換され、数字の後ろの文字は無視されます（例: ` 1tail` は有効）。数値に変換できない文字列は 0 扱いです。範囲・overflow の検証はありません（`engine/src/core/verify.cpp:1418-1421`; `engine/sycl/src/core/verify.cpp:921-925`）。

| 実装 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP verify | `STRATA_VERIFY_DEVICE_HITS` が設定されていれば、その値で `device_plan_` を判定。なければ無効 | `atoi(value) != 0`。例: `1`, `-1`, ` 1tail` | `atoi(value) == 0`。例: 空文字、`0`, `0anything`, `true` |
| SYCL verify | 無効。ただし起動時に `STRATA_VERIFY_NO_HOST` が有効で、DEVICE_PLAN が未設定なら起動処理が `1` を設定 | `atoi(value) != 0`。例: `1`, `-1`, ` 1tail` | 空文字、`0`, `0anything`, `true` |

CUDA/HIP では PLAN が設定済みなら `atoi` が 0 でも `DEVICE_HITS` にフォールバックしません。PLAN が未設定の場合に限り HITS の値を使います。SYCL の判定には HITS fallback がありません（`engine/src/core/verify.cpp:1418-1421`; `engine/sycl/src/core/verify.cpp:921-925`）。

## 有効になる条件

- CUDA/HIP: `all_resident_` と `always_publish_` がどちらも false のときだけ `device_plan_` が有効です。全 expert が resident なら all-resident graph 側の処理となり、このフラグ自体は使われません。window の初期化で residency table が検査されます（`engine/src/core/verify.cpp:1377-1402, 1417-1428`）。
- SYCL: `all_resident_` と `always_publish_` が false のときだけ有効です。全 resident の場合は同様に別経路です（`engine/sycl/src/core/verify.cpp:904-917, 921-925`）。
- CUDA/HIP では `STRATA_VERIFY_DEVICE_HITS` が有効で residency/cache 情報があり、`device_hits_` が選ばれる場合、`device_plan_` は false に戻されます。`STRATA_GPU_METAL` build では `device_hits_` を無効化する分岐があります（`engine/src/core/verify.cpp:1422-1428`）。
- `always_publish_` を要求する経路では device plan/hits が停止されます。CUDA/HIP の `set_always_publish(true)` は両状態を false にし、window 初期化時点でも `!always_publish_` を条件にします（`engine/include/strata/core/verify.hpp:347-355`; `engine/src/core/verify.cpp:1417-1428`）。
- SYCL では `STRATA_VERIFY_NO_HOST` が未設定・空文字・`0` 以外の値で有効扱いされ、DEVICE_PLAN 自体が未設定なら起動時に `STRATA_VERIFY_DEVICE_PLAN=1` を設定します。明示的な `0` や空文字も「設定済み」なので自動設定を抑止します。したがって `NO_HOST` と PLAN=`0` の組合せは自動補完されません（`engine/sycl/include/strata/core/verify_env.hpp:14-19`; `engine/sycl/src/program/generate.cpp:1848-1856`）。
- 同梱 `strata-sycl.sh` は既定で PLAN=`1` と NO_HOST=`1` を engine に渡します。外部環境に同名変数があれば値で上書きされ、空文字は渡さず、`0` は渡します（`engine/sycl/serve/strata-sycl.sh:25-43, 47-53`）。
- SYCL の mirror adaptive expert usage は `device_plan_` と `STRATA_VERIFY_NO_HOST` の両方を必要とし、不足時は `mirror adaptive expert usage requires NoHost device planning` で例外になります（`engine/sycl/src/core/verify.cpp:977-983`）。
- CUDA serve の foresight swap は `STRATA_FS_SLOTS` が正数で初めて検討され、PLAN または HITS が `atoi != 0` なら無効化され、stderr に理由を出します（`engine/src/core/expert_source.cpp:7294-7305`; 呼び出し `engine/src/program/generate.cpp:14886-14899`）。
- SYCL の固定 B60 single-layout 条件は PLAN が文字列として厳密に `1` であることを要求し、それ以外を他の必須条件と合わせて満たさない場合 `B60 single layout requires the fixed single-device no-host decode scene` を throw します（`engine/sycl/src/program/generate.cpp:4591-4597`）。

## 実行時の詳細

CUDA/HIP は verify window の初期化ごとに PLAN（未設定なら HITS）を読み、`device_plan_` を設定します。SYCL も window の初期化で PLAN を読みますが、SYCL の起動時補完は engine の引数処理後・GPU処理開始前に行われます（`engine/src/core/verify.cpp:1417-1428`; `engine/sycl/src/program/generate.cpp:1848-1856`; `engine/sycl/src/core/verify.cpp:919-925`）。CUDA/HIP の expert source には別途 `static const bool device_plan` があり、最初にその経路へ入った際に PLAN または HITS のいずれかが有効かを cache し、mapped output の行を GPU がゼロ化する経路選択に使います。これは verify window の `device_plan_` を選ぶ判定そのものではなく、HITS 経路も考慮した行コピー用判定です。SYCL 側には PLAN だけを見る関数内 static cache があります（`engine/src/core/expert_source.cpp:5727-5735`; `engine/sycl/src/core/expert_source.cpp:2724-2728`）。したがって実行途中で環境を変える運用は、window 判定と expert-source cache の食い違いを招き得ます。

有効時は device residency table を参照する `resident_plan` が window の GPU plan buffer に計画を書き、host 側は skip flag に応じて plan/row の待機・コピーを省略します。CUDA/HIP は必要な skip buffer 等を確保し、確保または初期化に失敗すると `all_resident_` / `device_plan_` / `device_hits_` を false に戻します。SYCL でも buffer 確保・初期化失敗時に `device_plan_` を false に戻します（`engine/src/core/verify.cpp:1439-1449, 2686-2699, 2863-2908`; `engine/sycl/src/core/verify.cpp:952-975, 1612-1621, 1761-1789`）。

## ログと測定値

CUDA/HIP の dispatch note は window ごとに `win groups=%ld all_resident=%ld device_plan=%ld` を記録し、partial residency 経路では `experts layer: partial residency, plan from %ld (1 = device plan, 0 = host pool), pcie_mode=%ld, remote_opt=%ld` を出します。値は PLAN が要求されたかだけでなく、実際の window 条件を通過した `device_plan_` 状態です（`engine/src/core/verify.cpp:1543-1548, 2863-2865`）。

SYCL 起動時に NO_HOST から自動設定した場合は、stderr に次の文言を出します。

> `strata: STRATA_VERIFY_NO_HOST=1 needs the device-built plan for experts outside VRAM: STRATA_VERIFY_DEVICE_PLAN=1 is set too (STRATA_VERIFY_DEVICE_PLAN=0 keeps it off)`

（`engine/sycl/src/program/generate.cpp:1848-1856`）。SYCL の PLAN 要求時に skip buffer 等を初期化できなければ plan flag は無効に戻りますが、この箇所では専用の警告文を出しません（`engine/sycl/src/core/verify.cpp:952-975`）。

`docs/INTEL.md` は SYCL wrapper が PLAN を既定で渡すことと `0` が明示値であることを記載し、起動 wrapper と source の挙動に一致します。ここでは性能値や正確性の測定を新たに主張しません。

## 根拠

- `engine/src/core/verify.cpp:1377-1402, 1414-1449, 1543-1548, 2686-2699, 2863-2908`
- `engine/sycl/src/core/verify.cpp:904-925, 952-989, 1612-1621, 1761-1789`
- `engine/src/core/expert_source.cpp:5727-5735, 7294-7305`
- `engine/sycl/src/core/expert_source.cpp:2724-2728`
- `engine/sycl/include/strata/core/verify_env.hpp:14-19`
- `engine/sycl/src/program/generate.cpp:1848-1856, 4591-4597`
- `engine/sycl/serve/strata-sycl.sh:25-43, 47-53`
- `engine/include/strata/core/verify.hpp:347-360`
- `engine/src/program/generate.cpp:14886-14899`
