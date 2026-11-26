# `STRATA_HEAD_MIX_MULTI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

verify の窓に含まれる複数 token と MTP draft の複数 row について、最終 head hyper-connection mixer の read を row ごとの gr_read から、まとめた fused_gr_read_multi に切り替える。検証側は Verifier::record_window、draft 側は MtpDrafter の通常・batch 経路で参照される。ソースコメントでは両経路とも和は bitwise 同一としている。HIP では opt-in、CUDA と SYCL の非 HIP 分岐では unset 時に有効である（engine/src/core/verify.cpp:450-465、engine/src/core/mtp.cpp:1160-1174、engine/src/core/verify.cpp:3072-3092、engine/src/core/mtp.cpp:1495-1513,2631-2647、engine/sycl/src/core/verify.cpp:265-280、engine/sycl/src/core/mtp.cpp:1094-1101,1208-1225）。

## 値と判定

直接読み取りでは std::getenv の結果を std::atoi に渡し、ゼロかどうかで判定する。文字列全体の妥当性検査はなく、atoi が先頭から数値として読める部分を変換する。したがって空文字、true、false、0、0anything、数値で始まらない文字列は 0 になり無効、1、-1、2、1anything は非ゼロとなり有効。先頭空白や符号は atoi の変換規則に従う。大文字小文字を区別する文字列比較はない（engine/src/core/verify.cpp:452-465、engine/src/core/mtp.cpp:1160-1174）。

| 実装経路 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA/HIP 共通ソースの HIP 以外分岐、および SYCL の同分岐 | 有効 | 1, -1, 2, 1anything | 空文字, 0, 0anything, true, false, abc |
| HIP | 無効 | 1, -1, 2, 1anything | unset, 空文字, 0, 0anything, true, false, abc |

ただし AMD gfx11/gfx12 の既定値注入対象では、後述の起動時処理が unset を 1 に設定する場合がある。このとき実装側の読み取り値は set 扱いになる。明示的な空文字も getenv(...) != nullptr を満たして既定値注入を止めるが、atoi("") は 0 となり機能自体は無効となる（engine/src/core/arch_defaults.cpp:318-323,360-370、engine/include/strata/core/gfx11_extra.hpp:41-46,69、engine/include/strata/core/gfx12_extra.hpp:41-48）。

## 有効になる条件

- 値の判定が有効であること。HIP では unset は無効。gfx11/gfx12 の自動設定が適用された場合は unset でも有効になる。
- verify 側では head が存在して loaded であること。そうでなければ head mixer のこの分岐には入らない。STRATA_FUSE_HEAD_GR が有効な場合は先行する分岐が使われ、この変数による選択は行われない（engine/src/core/verify.cpp:3072-3092）。
- MTP 側では STRATA_FUSE_HEAD_GR が有効なら fused read-and-write 分岐が優先され、この変数の分岐は使われない（engine/src/core/mtp.cpp:1481-1513,2615-2647）。
- AMD/HIP の自動既定値は、gfx1100/gfx1101/gfx1102 の discrete RDNA3（integrated ではない）または gfx12（RDNA4）で apply_arch_defaults が実行される場合に限られる。gfx11 は STRATA_GFX11_DEFAULTS=0 または STRATA_DEFAULTS=026 で既定値表から外れ、gfx12 は STRATA_GFX12_DEFAULTS=0 または STRATA_DEFAULTS=026 で外れる。どちらも環境変数が既に存在すればその値を保持する（engine/include/strata/core/gfx11_extra.hpp:27-30,41-46,69、engine/include/strata/core/gfx12_extra.hpp:41-48、engine/src/core/arch_defaults.cpp:318-323,360-370）。
- 有効分岐で verify の head weight が engine 形式でない場合、record_window は false を返し、err に verify: the output_hc_* weights have the wrong engine forms を設定する（engine/src/core/verify.cpp:3072-3078）。

## 実行時の詳細

verify の head_mix_multi_enabled() と MTP の mtp_head_mix_multi_on() は、各関数内の関数ローカル static で初回評価結果を保持する。評価時点はプロセス開始時ではなく、その関数が最初に呼ばれたときで、以後の環境変更は同じプロセス内の判定に反映されない。SYCL の verify と MTP にも同様の static 判定がある（engine/src/core/verify.cpp:452-465、engine/src/core/mtp.cpp:1160-1174、engine/sycl/src/core/verify.cpp:270-280、engine/sycl/src/core/mtp.cpp:1094-1101）。

有効時、verify は head_ が loaded のときに窓の HT 行を一度の fused_gr_read_multi で処理し、無効時は各行を lm_head_mix に渡す（engine/src/core/verify.cpp:3072-3098）。MTP の通常・batch draft 経路では各 row の head mixer 引数を構成して fused_gr_read_multi を呼び、無効時は gr_read を row ごとに呼ぶ（engine/src/core/mtp.cpp:1495-1513,2631-2647）。いずれも変わるのはこの mixer read のまとめ方で、後続の quantize/head projection と token 選択処理は同じ関数内で続く。

HIP の gfx11/gfx12 既定値は generate 起動処理から apply_arch_defaults を呼ぶ際に環境へ設定され、その前にユーザー値の有無を確認する。CLI 引数による個別 override は見つからない（engine/src/program/generate.cpp:4287-4320、engine/src/core/arch_defaults.cpp:318-323,360-370）。

## ログと測定値

gfx11 の既定値を注入した場合、Strata は stderr に「strata: gfx11 (RDNA3): %zu exact speed switches on by default (STRATA_GFX11_DEFAULTS=0 turns them off; a switch you set is kept): 」を出してから有効化した名前を列挙し、その一覧に HEAD_MIX_MULTI を含める。gfx12 でも注入時に「strata: gfx12 (RDNA4): exact extra switches on by default (STRATA_GFX12_DEFAULTS=0 turns them off; a switch you set is kept): HEAD_MIX_MULTI」を stderr に出す。明示値がある場合や該当既定値が無効の場合、この変数の注入ログは出ない（engine/src/core/arch_defaults.cpp:318-332,360-370）。

gfx12 の設計コメントには、Radeon AI PRO R9700、p620、IQ3_S、serve、static residency、8 interleaved pairs、A/A 同時比較の条件で json_extract が +0.82%（6/8 pairs）、agent が +0.63%（6/8）、code_py が -0.96%（3/8）、greedy ids はそれぞれ比較セットで同一と記載されている。これはソースコメントに記載された測定値であり、別 GPU や workload への一般化はできない（engine/include/strata/core/gfx12_extra.hpp:5-9）。

直接設定した値そのものについての有効・無効ログはない。数値変換後にゼロとなる値は通常の per-row gr_read 経路へ進み、変数単独を理由とした警告や終了処理はない。

## 根拠

- engine/src/core/verify.cpp:450-465,3072-3098 — verify の値判定と head mixer 分岐。
- engine/src/core/mtp.cpp:1160-1174,1385-1390,1495-1513,2532-2536,2631-2647 — MTP の値判定、呼び出し、通常・batch draft 分岐。
- engine/sycl/src/core/verify.cpp:265-280,1910-1935、engine/sycl/src/core/mtp.cpp:1094-1101,1208-1225 — SYCL 実装。
- engine/include/strata/core/gfx11_extra.hpp:27-46,69、engine/include/strata/core/gfx12_extra.hpp:40-48、engine/src/core/arch_defaults.cpp:302-323,360-370 — AMD 向け既定値とユーザー値の保持。
- engine/src/program/generate.cpp:4287-4320 — HIP 起動時の architecture defaults 呼び出し。
- engine/include/strata/core/gfx12_extra.hpp:5-9 — gfx12 の測定記載。
