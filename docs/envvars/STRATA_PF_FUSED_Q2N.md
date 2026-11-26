# `STRATA_PF_FUSED_Q2N`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA の native Q2_0 量子化モデルで、prompt prefill 中の Q2_0 gate/up と Q2_0 down の組に fused int8 カーネルを使うための opt-in です。通常はこの gate/up カーネルを setup せず、対象層は CUDA の MMQ 経路に残ります。`STRATA_PF_FUSED_Q2N` が有効で、カーネル setup と層の形式条件を満たす場合、`native_supported()` が対象ペアを選び、`experts_native()` が Q2_0 gate/up と down の両カーネルを起動します（`engine/src/prefill/moe_fused_iq.cu:2942-2950`, `3061-3065`, `3515-3533`, `3686-3700`, `3903-3930`）。

対象は native Q2_0 pack の Q2_0 / Q2_0 層だけです。Q2_0 gate/up を別形式の down と組み合わせる用途には使われず、HIP・CPU・Metal のこの環境変数による切り替えもありません（`engine/src/prefill/moe_fused_iq.cu:3061-3078`, `3533-3561`）。

## 値と判定

CUDA の `dev_info()` 内で `std::getenv` の値を関数内 `static const bool` に一度保存し、値が存在し、かつ先頭文字が `'1'` の場合だけ有効です。文字列全体や数値としての妥当性は検査しません（`engine/src/prefill/moe_fused_iq.cu:2947-2949`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA build、Compute Capability 8.0 以上で `dev_info()` が setup に進む | 通常 build では無効。MMQ を含まない CUDA build では、起動時に未設定の場合 `"1"` が追加される | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `01`, `true`, ` 1`, `false` |
| CUDA build、Compute Capability 8.0 未満 | Q2N 判定に到達せず無効 | なし | すべて（Q2N による効果なし） |
| HIP build | この変数を読み取らず、HIP 用の起動時既定値リストにもない | なし | すべて（Q2N による効果なし） |

空文字は `getenv` 上は設定済みですが、先頭文字比較は false です。また MMQ なし CUDA build では、「未設定」のときだけ起動前に `"1"` を設定します。空文字を含む任意の既存値は上書きされないため、明示した空文字は無効のままです（`engine/src/prefill/prefill.cpp:223-255`, `engine/include/strata/prefill/own_only_switches.hpp:18-25`, `48-56`）。

## 有効になる条件

- CUDA build であること。HIP の `dev_info()` は別の gfx11/gfx12 setup を行って CUDA 専用の Q2N 判定に入らず、HIP の own-only 既定値一覧にも Q2N は含まれません（`engine/src/prefill/moe_fused_iq.cu:2854-2887`, `2942-2950`; `engine/include/strata/prefill/own_only_switches.hpp:19-25`）。
- 現在の device が Compute Capability 8.0 以上で、通常の native fused kernel setup（`d.ok`）が成功すること。8.0 未満は Q2N の読み取り行より前に `dev_info()` が戻ります（`engine/src/prefill/moe_fused_iq.cu:2887-2902`, `2942-2950`）。
- `setup_one<T_Q2_0, true>` が成功すること。これは WW=4 と WW=2 の両 setup を要求します。関数属性・動的 shared memory・occupancy のいずれかを満たさない場合は失敗し、`d.q2n` は false のままです（`engine/src/prefill/moe_fused_iq.cu:2748-2765`, `2948-2950`）。
- モデル層の gate/up と down がともに Q2_0 であること。`native_supported()` は CUDA の通常分岐で Q2_0 gate/up に対し他形式の down を拒否し、unset の fused 全体スイッチ時も Q2_0 / Q2_0 を個別に判定します（`engine/src/prefill/moe_fused_iq.cu:3515-3533`）。
- 別変数 `STRATA_PF_FUSED` が明示的に無効を指定していないこと。空文字・未設定は env 判定上 unset、先頭文字 `1` は on、その他の非空値は off として扱われます。`STRATA_PF_FUSED=0`（および `0anything`）は Q2N も含め native fused の選択を止めます。未設定時は Q2N が on なら対象ペアを使える特別分岐があり、`STRATA_PF_FUSED=1` のときも Q2N の setup が成功していれば対象ペアを選べます（`engine/src/prefill/moe_fused_iq.cu:3425-3432`, `3517-3533`, `3581-3586`）。
- `STRATA_PF_FUSED_NATIVE=0`（先頭文字が `0`）が指定されていないこと。このスイッチは native pack の `native_supported()` を早期に false にします。Q2N の setup 自体は別に行われますが、対象層の選択は抑止されます（`engine/src/prefill/moe_fused_iq.cu:3415-3432`）。
- `STRATA_PF_FUSED_NT=256` または `STRATA_PF_FUSED_WS=1` による別の native kernel 経路との併用制約を満たすこと。これらの経路では Q2_0 gate/up の Q2N setup も試されますが、対象ペアは NT=256 / warp-specialized 形式を持たないため、その経路からは選択されません（`engine/src/prefill/moe_fused_iq.cu:3007-3021`, `3441-3442`）。

CLI から Q2N を直接指定する引数は見つかりませんでした。サーバーの `--prefill auto` では、単一 CUDA device・native pack などの小容量 prompt 条件を満たすと `pf_fused_override` がセットされ、`STRATA_PF_FUSED` 未設定の判定を on 相当にすることがあります。これは別途 Q2N が有効で setup 済みの場合に限り Q2_0 / Q2_0 層を通します。`STRATA_PF_SMALL=0` はこの自動経路を止め、`STRATA_PF_SMALL_FUSED=0` は小容量経路中の fused kernels を止めます（`engine/src/program/generate.cpp:12562-12583`; `engine/include/strata/prefill/pf_fused_override.hpp:1-29`; `engine/src/prefill/moe_fused_iq.cu:3429-3432`, `3517-3533`）。

## 実行時の詳細

通常の CUDA build では、対象値は当該プロセスで Compute Capability 8.0 以上の device に対する `dev_info()` が初めて setup に進んだ際に読み取られます。`q2n` は process-wide の static cache、`d.q2n` と setup 結果は device ごとの `g_dev[32]` に保存されます。したがって実行中に環境を書き換えても、すでに cache 済みの値や setup 結果は変わりません。Compute Capability 8.0 未満しか使わない場合は Q2N の static 判定に到達しません（`engine/src/prefill/moe_fused_iq.cu:2690-2691`, `2847-2853`, `2887-2902`, `2942-2950`）。

MMQ を含まない CUDA build（`STRATA_PREFILL_FUSED` が定義され、`STRATA_PREFILL_MMQ` が未定義）では、`prefill.cpp` の静的初期化が `main()` より前に CUDA 用 opt-in 一覧を走査します。Q2N が未設定なら POSIX では `setenv(name, "1", 0)`、Windows では `_putenv_s(name, "1")` で有効値を追加し、その名前を build 既定値記録に保存します。すでに設定済みの値は空文字を含め保持します（`engine/src/prefill/prefill.cpp:223-255`; `engine/include/strata/prefill/own_only_switches.hpp:18-25`, `34-56`）。

Q2N の setup に失敗した場合は `d.q2n` が立たず、通常の `native_supported()` 判定から対象ペアが外れます。Q2N 固有の setup 失敗警告はありません。通常経路では対象が既定の MMQ / 他の prefill 経路に残ります。何らかの不整合で未対応形式が `experts_native()` に渡された場合は `prefill fused experts (native): types %d / %d are not covered here` を stderr に出して `exit(1)` します（`engine/src/prefill/moe_fused_iq.cu:2948-2950`, `3517-3533`, `3686-3700`）。

## ログと測定値

Q2N を有効にしたことや Q2_0 setup の成否を示す専用ログはありません。未対応ペアが native kernel dispatcher に渡った場合のエラーは `engine/src/prefill/moe_fused_iq.cu:3697-3700` の stderr 文言です。

`docs/DETAILS.md` は RTX 5080 16 GB（sm_120、Linux、CUDA 13.0）、i9-14900K、2,100 experts VRAM 内、CPU prompt share 無効の測定として、unset と同じ 4,864-token chunk では 4K/16K/23K prompt が 2–3.5%短縮（各4 interleaved rounds）、`--prefill auto` では fused path の chunk が 5,632 tokens となり 16K prompt が 32–33%短縮（2,592→3,438 tok/s）と記載しています。文書自身が大半の差は kernel でなく chunk 増加によると区別しています。1層の Q2_0 / Q2_0 は 2,048 / 4,864 / 8,192 tokens で MMQ 比 1.92x / 1.37x / 1.30x、FP16 prompt path との first-token KL は 30 prompts で 0.0110（MMQ 0.0112）と記載されています。これらは Strata の資料に記載された値であり、本調査で再測定していません。資料は他の sm_80+ GPU、Windows、生成文を未測定とし、RTX A4000 では以前の同 kernel が旧出力と一致せず 4K prompt が 4.5%遅かったため Ampere 未検証としています（`docs/DETAILS.md:1348-1366`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:2847-2905` — device 別 setup、HIP / CUDA 分岐、sm_80 未満の早期 return。
- `engine/src/prefill/moe_fused_iq.cu:2942-2950` — Q2N の唯一の直接 `getenv`、値判定、Q2_0 gate/up setup。
- `engine/src/prefill/moe_fused_iq.cu:3061-3078`, `3415-3432`, `3515-3533`, `3581-3586` — 形式条件、全体スイッチと native switch の優先、実際の層選択。
- `engine/src/prefill/moe_fused_iq.cu:3686-3700`, `3903-3930` — dispatch の安全確認、Q2_0 gate/up と down の launch。
- `engine/src/prefill/prefill.cpp:223-255`; `engine/include/strata/prefill/own_only_switches.hpp:18-25`, `48-56` — MMQ なし CUDA build の起動時既定値と環境値保持。
- `engine/src/program/generate.cpp:12562-12583`; `engine/include/strata/prefill/pf_fused_override.hpp:1-29` — server の小容量 prompt path が fused override を設定する条件。
- `docs/DETAILS.md:1348-1366` — 条件付き測定記録と未検証範囲。
