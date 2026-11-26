# `STRATA_ROUTE_RESIDENT_RANKS`

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

MoE の router が選んだ top-10 のうち、どの順位の非 resident expert を resident expert と交換するかを指定する。順位は 0 始まりで、既定値 6-9 は下位4枠を対象にする。交換条件の margin は別の STRATA_ROUTE_RESIDENT が指定し、この変数単独では機能を有効にしない。交換が起きた場合、選択 expert と router weight が変わるため出力が変わり得る。CUDA の verifier 経路と、条件を満たす単一 GPU の MTP draft 経路で参照される（engine/src/core/verify.cpp:126-132,178-186,2671-2677、engine/src/kernels/cuda/native_router.cu:253-257、engine/src/program/generate.cpp:13229-13239）。

## 値と判定

両方の読み取り箇所で std::sscanf(v, "%d-%d", ...) を使い、戻り値を確認しない。文字列全体の厳密な検証はなく、先頭から整数、ハイフン、整数の順に読めるところまで代入され、後続文字は無視される。%d は符号付き整数を読むため、先頭空白や符号も許容される。Verifier の既定値は lo=6, hi=9、MTP 側もローカル変数を同じ値で初期化する。明示的な空文字や変換不能な先頭では値は変わらない。部分変換では読み取れた lo だけが更新され、hi は既定値のままになる（engine/src/core/verify.cpp:129-132,178-184、engine/src/program/generate.cpp:13234-13235）。

| 条件 | unset | 有効になる値の例 | 無効・注意が必要な値の例 |
|---|---|---|---|
| Verifier / MTP 共通の rank parse | 6-9 | 2-5 は順位2〜5、6-9junk は 6-9 として読まれる | 空文字・abc は既定値のまま。3-x は lo=3, hi=9。9-6 はループ対象なし。10-12 も対象なし。 |
| 範囲の安全性 | 6-9 は順位配列内 | 0-9 は全 top-10 順位を走査 | 負の lo は下限検査がないまま ids[lo] を参照し得る。lo > hi は交換なし。値域の検査・clamp はない。 |

カーネル側は r=lo から r<=hi && r<10 の間ループするが、r>=0 は確認しない。hi が9より大きい場合は9までで止まり、lo が10以上ならループしない。負の lo は ids の範囲外参照になり得るため設定しないこと。順位の入れ替えが起きない場合、元の router weights はそのまま残る（engine/src/kernels/cuda/native_router.cu:273-299,303-310）。

## 有効になる条件

- Verifier 経路では、STRATA_ROUTE_RESIDENT の atof 結果が 0 より大きく、モデルの expert 数 NE が512、top-k K が10、resident table hits_.d_res が非 null であること。これらを満たすと router 処理後・plan 処理前に resident-aware swap を行う。STRATA_ROUTE_RESIDENT_RANKS が有効範囲でも、他の条件を満たさなければ使われない（engine/src/core/verify.cpp:181-182,2671-2677）。
- Verifier の初期化自体も VRAM expert tier などを要求する。resident table が無い場合は Verifier::init が "verify: needs the profile-filled VRAM expert tier ..." を返すため、この swap に到達しない（engine/src/core/verify.cpp:1000-1005）。
- MTP draft 経路では、use_mtp、stages.empty()（単一 GPU）、thits.d_res != nullptr、STRATA_ROUTE_RESIDENT の設定あり、STRATA_ROUTE_RESIDENT_MTP の設定ありかつ atoi が非0であることが必要。さらに STRATA_ROUTE_RESIDENT の atof 結果が正で、MTP router が512 experts / top-10である場合に設定される。設定表は最終 layer の resident row である（engine/src/program/generate.cpp:13229-13239、engine/include/strata/core/mtp.hpp:60-65、engine/src/core/mtp.cpp:1432-1435）。
- 実装は CUDA native router の kernel にあり、Strata の設定資料もこの routing 変更を CUDA 向けとして記載する。HIP、SYCL、Metal で同じ挙動になる根拠は確認できなかった（engine/src/kernels/cuda/native_router.cu:265-328、engine/cmake/strata_gpu_engine.cmake:55-76、docs/DETAILS.md:1282）。

## 実行時の詳細

Verifier では route_resident_cfg() の関数内 static 設定が初回呼び出し時に STRATA_ROUTE_RESIDENT とこの変数を読み、以後プロセス内で再読込しない。初回呼び出しは Verifier::init の GPU counter setup から行われる。したがって、その後にプロセス環境を変更しても Verifier 設定には反映されない（engine/src/core/verify.cpp:178-186,956-968）。

各 verifier window で、router が作った top-10 と logits を使い、指定順位を小さい順に調べる。対象順位の expert が非 resident の場合、まだ選ばれていない resident expert のうち logits が最大のものを探す。同点なら expert index が小さい方を選ぶ。元 expert の logit から候補 logit を引いた値が STRATA_ROUTE_RESIDENT の margin 以下なら置換し、選択 logits から softmax weights を再計算する。置換がなければ weights は書き換えない。各置換後の選択集合を次の順位の探索にも使う（engine/src/kernels/cuda/native_router.cu:253-299,303-310）。

MTP 経路は route_resident_cfg() の cache を使わず、この分岐の初期化時に環境値を別に読み、MtpDrafter に margin と ranks を設定する。Verifier側と異なり、MTPではこの環境変数を設定したかも条件に含まれる。実行途中の環境変更を継続監視する処理はない（engine/src/program/generate.cpp:13231-13239）。

## ログと測定値

Verifier は counter block を確保できない場合、stderr に route-resident: the counters could not be allocated on GPU %d; it runs without them と出し、counter なしで処理を続ける。counter が確保された GPU については終了時に prompt (windows T>8) と decode (windows T<=8) 別に、使用 ranks、tail entries、swap 数、前後の non-resident 数を route-resident... 行で出す。margin が0以下などで counter が作られない場合、この統計行は出ない（engine/src/core/verify.cpp:138-175,167-170）。

MTP 条件が成立して margin が正の場合、stderr に strata generate: STRATA_ROUTE_RESIDENT_MTP: the MTP draft's router is biased toward layer ... (margin ..., ranks ...; experimental) と出す。MTP kernel 例外は mtp route-resident: を付けたエラー文字列になり、Verifier kernel 例外は verify route-resident: を付けて失敗を返す（engine/src/program/generate.cpp:13236-13239、engine/src/core/verify.cpp:2673-2677、engine/src/core/mtp.cpp:1432-1435）。

## 根拠

- engine/src/core/verify.cpp:126-186 — 設定構造体、既定値、環境読み取りと cache。
- engine/src/core/verify.cpp:956-968,1000-1005,2671-2677 — verifier 初期化、resident table 条件、swap 呼び出しと失敗経路。
- engine/src/kernels/cuda/native_router.cu:253-328 — rank の走査、resident candidate 選択、margin 判定、weights の再計算と counter。
- engine/src/program/generate.cpp:13229-13239、engine/include/strata/core/mtp.hpp:60-65、engine/src/core/mtp.cpp:1432-1435 — MTP 経路の条件、ranks 設定、呼び出しと失敗経路。
- engine/cmake/strata_gpu_engine.cmake:55-76、docs/DETAILS.md:1282 — CUDA kernel の build source と関連する設定資料。
