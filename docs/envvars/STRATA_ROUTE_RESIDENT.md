# `STRATA_ROUTE_RESIDENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

正の margin を指定すると、MoE の router が選んだ上位 10 experts のうち指定 rank 範囲にある非 resident expert を、logit 差が margin 以内の resident expert に置き換える。変更後は選択された experts の logits から routing weight を再計算するため、expert ID と重みが変わり、モデル出力も変わり得る。通常の router の出力を変えない設定は margin が正でない場合である。実装は Verifier の routing 後処理と CUDA/HIP カーネル（`engine/src/core/verify.cpp:2671-2677`、`engine/src/kernels/cuda/native_router.cu:253-257, 265-319`）。

## 値と判定

Verifier は `std::getenv` の戻り値を `std::atof` に渡し、変換結果を `margin > 0.0f` で判定する。数値文字列全体の検証、範囲 clamp、エラー通知はない。未設定時は `0.0f`。空文字、数値に変換できない文字列、`0`、負値は有効化しない。数値の後ろに文字があっても数値接頭部が変換される（例: `1tail` は 1）。正の有限値であれば有効で、`+inf` も比較上は正として通る。`nan` は `> 0` を満たさない。読み取り箇所は `engine/src/core/verify.cpp:129-131, 178-186`。

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Verifier（CUDA/HIP） | margin `0.0f`、無効 | `0.1`, `1`, `1tail`, `inf` など `atof` の結果が正 | 空文字、`0`, `-1`, `junk`, `nan` など結果が正でないもの |
| MTP 下書き router | MTP 経路自体が別途 opt-in。変数 unset なら無効 | 変数が設定済みで `atof` の結果が正（さらに `STRATA_ROUTE_RESIDENT_MTP` が必要） | 空文字や `0` を含め `atof` の結果が正でないもの |

MTP 経路も margin は `atof` で読みますが、設定の有無を先に調べてから同じく `margin > 0` の場合だけ設定します（`engine/src/program/generate.cpp:13229-13240`）。

関連する `STRATA_ROUTE_RESIDENT_RANKS` は別変数で、既定は `lo=6, hi=9`。設定時は `%d-%d` の `sscanf` で読み、完全一致や範囲検証をしない。Verifier と MTP の双方で同じ既定値・変換方法を使う（`engine/src/core/verify.cpp:129-131, 181-182`、`engine/src/program/generate.cpp:13234-13235`）。カーネルは `lo` から `hi` までを inclusive に走査し、`r < 10` の上限だけを設ける。したがって 9 を超える上端は rank 9 までに制限される一方、負の下端や `lo > hi` の補正はない。負の rank は `my[r]` の範囲外参照になり得るため、rank 値は 0–9 の範囲で指定する必要がある（`engine/src/kernels/cuda/native_router.cu:273-280`）。

## 有効になる条件

- Verifier 経路では margin が正で、対象 layer が `NE == 512` かつ `K == 10`、かつ `hits_.d_res` が非 null であること。条件を満たさない layer ではこの後処理は呼ばれない（`engine/src/core/verify.cpp:2671-2677`）。
- ソースの GPU engine は CUDA/HIP 共用で、`native_router.cu` をその kernel library に含める（`engine/cmake/strata_gpu_engine.cmake:1, 7-9, 68-76`）。Metal には対応 kernel の stub がある（`engine/metal/src/engine/stubs.cpp:286`）；この stub は呼ばれると `missing` に委譲する。したがって実際の routing kernel を提供する経路として確認できるのは CUDA/HIP である。
- MTP 下書き router にも適用するには、上記に加えて `use_mtp` が真、layer split がなく（`stages.empty()`）、`thits.d_res` が non-null、`STRATA_ROUTE_RESIDENT_MTP` が設定済みで `atoi` の結果が非 0 であること。`STRATA_ROUTE_RESIDENT_MTP` は値の全体を検証せず、例えば `1tail` は有効、空文字や `0` は無効（`engine/src/program/generate.cpp:13231-13240`）。
- Verifier と MTP の両方で `STRATA_ROUTE_RESIDENT_RANKS` が置換対象順位を決める。Verifier では `STRATA_ROUTE_PRIOR` の処理が先にあり、resident bias はその後、routing IDs/weights を plan/doorbell が読む前に適用される（`engine/src/core/verify.cpp:2662-2677`）。
- この環境変数に対応する CLI 引数による上書き・優先順位は、読み取り経路にない。MTP 側の追加ゲート以外に `STRATA_ROUTE_RESIDENT` の値を上書きする別設定も、この読み取り経路では確認できない。

## 実行時の詳細

Verifier の `route_resident_cfg()` は function-local static の設定オブジェクトと一度だけ評価される static 初期化処理を使う。最初の Verifier 初期化時に `stats_on(device_)` から呼ばれ、その時点で `STRATA_ROUTE_RESIDENT` と `STRATA_ROUTE_RESIDENT_RANKS` を読み取る（`engine/src/core/verify.cpp:178-186, 956-968`）。以後、同一プロセス内で環境を変更してもこの設定値には反映されない。正の margin なら device ごとに 8 個の 64-bit counter を確保し、失敗時は counter なしで続けようとする（`engine/src/core/verify.cpp:138-175`）。

各 routing row で、元の top-10 の ranks `lo..hi` を順番に調べる。対象が非 resident の場合、現在選択されていない resident expert の中から最大 logit のものを探し、`元の logit - 候補 logit <= margin` の場合だけ置換する。同点の候補は expert index が小さい方を選ぶ。置換が一つでもあれば、選択された 10 experts の logits に対する softmax を計算して weights を書き換える。置換がなければ router の weights を書き換えない（`engine/src/kernels/cuda/native_router.cu:273-310`）。これは routing ID と weights を変え得る制御で、生成 token の同一性を保証する処理ではない。

MTP 経路では `generate.cpp` の serve 初期化中に環境を読み、条件を満たすと最終 layer の residency row と margin/ranks を `MtpDrafter` に渡す。その後 MTP router が 512 experts/top-10 のとき、通常 router の後に同じ kernel を呼ぶ（`engine/src/program/generate.cpp:13226-13240`、`engine/include/strata/core/mtp.hpp:60-65`、`engine/src/core/mtp.cpp:1420-1435`）。この経路の環境値は各 generate 設定時に評価され、Verifier の static cache とは別である。

## ログと測定値

- Verifier の counter allocation に失敗すると stderr に `route-resident: the counters could not be allocated on GPU %d; it runs without them` を出し、counter なしで routing を続ける（`engine/src/core/verify.cpp:143-152`）。
- counter が確保された場合、終了時に GPU ごとに `route-resident...: margin=... ranks=... windows T>8 (prompt reads): ...` と `windows T<=8 (decode): ...` の2行を stderr に出す。各行には tail entries、swaps、swap 比率、置換前後の非 resident 件数を含む。同期または counter の読み戻しに失敗した GPU の行は出さずに続行する（`engine/src/core/verify.cpp:154-172`）。
- MTP 設定が実際に有効になると stderr に `strata generate: STRATA_ROUTE_RESIDENT_MTP: the MTP draft's router is biased toward layer ...` と出す（`engine/src/program/generate.cpp:13236-13240`）。
- CUDA kernel の起動エラーは例外となり、Verifier は `err = "verify route-resident: " + ...` を設定して失敗を返す。MTP 側は `err = "mtp route-resident: " + ...` を設定して失敗を返す（`engine/src/kernels/cuda/native_router.cu:321-328`、`engine/src/core/verify.cpp:2673-2677`、`engine/src/core/mtp.cpp:1432-1436`）。
- `docs/DETAILS.md:1282` は関連 routing 変更をまとめて記載するが、この変数単独の測定条件・値は示していないため記載しない。

## 根拠

- 読み取り、既定値、cache、counter: `engine/src/core/verify.cpp:126-186, 138-175, 956-968`
- Verifier の適用条件・順序・失敗伝播: `engine/src/core/verify.cpp:2662-2677`
- swap の閾値、順位走査、ID/weight の更新: `engine/src/kernels/cuda/native_router.cu:253-257, 265-328`
- MTP の追加ゲート・評価・ログ: `engine/src/program/generate.cpp:13226-13240`; kernel 呼び出し: `engine/src/core/mtp.cpp:1420-1436`
- backend の共用 build と Metal stub: `engine/cmake/strata_gpu_engine.cmake:1, 7-9, 68-76`; `engine/metal/src/engine/stubs.cpp:286`
