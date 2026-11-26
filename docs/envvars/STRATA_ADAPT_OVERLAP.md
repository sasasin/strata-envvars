# `STRATA_ADAPT_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

適応型エキスパート層が GPU キャッシュへ行う swap コピーを、次の decode window の実行と重ねるスイッチ。コピーが到着する前に次 window のレジデンシ表を更新し、Verifier は各層の計画を、その層に必要なコピーが到着するまで待たせる。通常の逐次待機に比べてコピー待ちを window の実行中に隠す構成だが、コード上では生成 token は同じと説明されている。読み取りと制御は `engine/src/program/generate.cpp` の `adapt_overlap()` と生成ループにある（`engine/src/program/generate.cpp:2253-2289, 15113-15143, 22818-22835`）。

これは Strata engine の生成経路で使われる機能で、環境値は起動時の状態表示にも使われる。`--adapt-async` が省略された場合の自動選択では、このスイッチが有効だと非同期 adaptive tier の自動選択を抑止する（`engine/src/program/generate.cpp:11774-11794`; `engine/include/strata/core/adapt_async_default.hpp:41-60`）。

## 値と判定

`adapt_overlap()` は `std::getenv("STRATA_ADAPT_OVERLAP")` の値の**先頭文字だけ**を見て、`'1'` なら要求ありとする。文字列全体の数値変換や真偽値 parse はしない。関数内 `static const bool` に保存され、初回評価以後の環境変更は反映されない（`engine/src/program/generate.cpp:2269-2289`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の起動時判定 | OFF | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1`, `2` |
| CUDA、同じ compute capability の全カードが `sm_70` で、既定値適用が有効 | 起動時に `1` を設定して ON | 利用者が値を設定済みなら、その値を保持 | 利用者が空文字や `0` を設定済みなら保持され、OFF |
| Windows + HIP build | 値判定は通常どおり。ただし `STRATA_WIN_HIP_RISKY` が無効なら要求を拒否 | `STRATA_WIN_HIP_RISKY` が空でなく、かつ文字列全体が `0` でなければ要求を許可 | 同変数が unset、空文字、または厳密に `0` なら拒否 |

`sm_70` の既定値は、engine が CUDA build で、見えている全 GPU の compute capability が同じ場合に `apply_nv_defaults()` が適用する NVIDIA 既定値の一つ。`STRATA_SM70_PERF` の先頭が `0`、または `STRATA_DEFAULTS=026` の場合はこの既定値一覧から外れる。既定値適用は環境変数がすでに存在すれば値にかかわらず上書きしないため、明示的な空文字も利用者の設定として扱われる（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:15-18, 136-143, 222-238`）。

Windows + HIP で拒否を解除する `STRATA_WIN_HIP_RISKY` は `value != nullptr && value[0] != '\0' && strcmp(value, "0") != 0` で判定される。したがって `00` や `false` も解除扱いになる（`engine/include/strata/core/win_hip_risky.hpp:17-25`）。

## 有効になる条件

`STRATA_ADAPT_OVERLAP` が ON でも、次のいずれかに当たると overlap は実行されない。該当理由は `aov_why` の最初に一致した条件で決まる（`engine/src/program/generate.cpp:15122-15143`）。

- 層分割 GPU（`multi_gpu` または stage 分割）では使わない。
- `--remote-expert-opt`、`--adapt-async`、`--pipeline-windows` と併用しない。
- swap 元 blob の page-lock が有効な場合は使わない。
- `STRATA_DMA_BATCH` が有効な場合は使わない。
- `STRATA_ADAPT_LAG` が 1 以外、または `STRATA_ADAPT_NOWAIT` が有効な場合は使わない。これらは overlap と別の swap 到着タイミング制御である。
- resident RAM mode では、追加で `STRATA_ADAPT_OVERLAP_RESIDENT` の先頭文字が `1` でなければ使わない。
- adaptive tier が無効（`--adapt-every` または `--adapt-swaps` が正でない等で usage table が空）の場合は使わない。usage table は adaptive tier が有効で、全エキスパートが resident ではなく GPU cache slot がある場合に初期化される（`engine/src/program/generate.cpp:15001-15002`）。
- `STRATA_VERIFY_DEVICE_PLAN` による device-planned layers または device hits が有効だと `Verifier::set_adapt_gate()` が拒否する。
- Windows + HIP では `STRATA_WIN_HIP_RISKY` の解除がない限り、`STRATA_ADAPT_OVERLAP=1` の要求自体が拒否される。

逆に、`STRATA_ADAPT_FETCH` は overlap の実行条件を直接拒否しないが、overlap が有効なときは fetch 側の停止理由として扱われる（`engine/src/program/generate.cpp:15055-15060, 15067-15072`）。`--adapt-async` を明示した場合も overlap は実行されず、自動選択の場合は `adapt_overlap()` が true なら非同期 tier の自動選択を行わない（`engine/src/program/generate.cpp:11777-11794, 15122-15129`; `engine/include/strata/core/adapt_async_default.hpp:54-59`）。

## 実行時の詳細

初回の `adapt_overlap()` 呼び出しは、`--adapt-async` の自動選択判定中か、adaptive tier の起動準備時に行われる。前者が先なら、その値が関数内 static に保持され、後続の呼び出しも同じ値を使う。起動前に適用される `sm_70` 既定値は判定に反映されるが、初回評価後にプロセス環境を変えても再評価しない（`engine/src/program/generate.cpp:2269-2289, 11777-11794`; `engine/src/core/nv_defaults.cpp:222-238`）。

adaptive round で swap が残っていると、通常の「コピー完了を待ってから次 window」ではなく、まずホスト側のレジデンシ表を更新し、Verifier の gate を有効にして次 window を始める。コピー stream は層順に各 swap を転送し、その層のコピー完了を atomic counter または pinned-memory の copy signal で通知する。Verifier は GPU が層を要求した時点で、その層の swap があれば通知値まで host を待たせる。peer tier がある場合も同じ gate に参加する。resident RAM mode では `soft_commit_exchanges()` が成立しなければ通常の待機へ fallback する（`engine/src/program/generate.cpp:15138-15143, 15431-15479, 22818-22835`; `engine/include/strata/core/verify.hpp:46-78`; `engine/src/core/verify.cpp:3657-3673, 4071-4074`）。

## ログと測定値

- 機能が使われる場合、stderr に `strata serve: adaptive overlap (STRATA_ADAPT_OVERLAP=0 turns it off): the adaptive tier's copies land while the next window runs (same tokens, a layer waits for its own copies)` と出る。peer tier があれば末尾に peer の signal 方式も表示する（`engine/src/program/generate.cpp:15176-15181`）。
- 値が要求され、適用条件で止められた場合は `strata serve: STRATA_ADAPT_OVERLAP=1 is off: <理由>` と出る。理由には `not on a layer split`、`not with --adapt-async`、`not with STRATA_ADAPT_LAG / STRATA_ADAPT_NOWAIT`、`the adaptive tier is off` などがある。変数が無効値または未設定なら、`strata serve: adaptive overlap: off...` の状態行になる（`engine/src/program/generate.cpp:15182-15186`）。
- Windows + HIP で要求を拒否する場合は `strata: STRATA_ADAPT_OVERLAP=1 is off on Windows with an AMD card: it ended the first request with a GPU fault there, and it was only checked on NVIDIA cards. STRATA_WIN_HIP_RISKY=1 turns it on anyway.` と出る。解除値がある場合は `strata: STRATA_WIN_HIP_RISKY=1: STRATA_ADAPT_OVERLAP=1 is on as asked, on Windows with an AMD card; it has reset the display driver or ended requests with a GPU fault there.` と警告する（`engine/src/program/generate.cpp:2280-2286`; `engine/include/strata/core/win_hip_risky.hpp:27-40`）。
- gate がコピー完了を 20 秒超待つと、stderr に `strata verify: the adaptive gate waited ...` と進捗値を出し、Verifier は `verify: the adaptive tier's copies for layer ... never landed` をエラーとして返す（`engine/src/core/verify.cpp:3665-3689`）。
- Strata の `docs/DETAILS.md` は 6 組の interleaved 比較として、RTX A4000 の Q2_0 / IQ3_XXS で +5.5〜8.3%、Tesla P100 で +4.4%、RTX 5070 Windows で -2.6%、RTX 5090 Laptop（WSL2、Core Ultra 9 275HX、native IQ3_XXS pack、`--expert-cache-per-layer`）で 84.6 対 106.6 tok/s（-21%）を記録している。これらは記載された条件での資料値で、一般的な性能保証ではない（`docs/DETAILS.md:1720`）。

## 根拠

- 値の読み取り、Windows HIP 判定、cache: `engine/src/program/generate.cpp:2253-2289`
- NVIDIA 既定値の設定条件と優先: `engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:15-18, 136-143, 222-238`
- 有効条件・状態ログ・gate 準備: `engine/src/program/generate.cpp:15113-15186`
- swap と window の重なり: `engine/src/program/generate.cpp:15431-15479, 22818-22835`; `engine/src/core/verify.cpp:3657-3693, 4071-4074`
- 非同期 adaptive tier との関係: `engine/src/program/generate.cpp:11774-11794`; `engine/include/strata/core/adapt_async_default.hpp:41-60`
- Windows HIP の拒否・警告: `engine/include/strata/core/win_hip_risky.hpp:17-40`
- Strata に記載された測定値: `docs/DETAILS.md:1720`
