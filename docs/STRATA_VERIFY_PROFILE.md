# `STRATA_VERIFY_PROFILE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

Verifier の decode window で GPU stage の時間を記録し、GDN/QSA layer ごとの区分（例: `attention`、`VRAM hits`、`PCIe grp`、`head`）と合計を ms/window で報告します。設定自体がログを常に出すわけではありません。通常の `--serve` では `STRATA_DECODE_TIMING` も設定され、リクエスト終了時に集計を出力する必要があります。SYCL の `STRATA_VERIFY_EAGER` 経路には、各 window ごとに出す例外があります。

## 値と判定

CUDA/HIP と SYCL の両実装で `std::getenv("STRATA_VERIFY_PROFILE") != nullptr` を使います。文字列を parse しないため、unset のみ無効です。`1`、`0`、`false`、空文字を含め、何らかの値が設定されていれば有効化を試みます。Verifier の初期化時に `prof_on_` に保存され、そのインスタンスでは後から環境を変更しても再評価されません。

有効化時は layer 数に比例する device profile buffer を確保して初期化します。確保に失敗すると `prof_on_` を false に戻し、計測・レポートを行いません（この箇所に専用の警告ログはありません）。pipelined windows 用の pinned host buffer が別途確保できない場合、その経路は window の計測を行いません。

## 有効になる条件と相互作用

- CUDA/HIP (`src/core/verify.cpp`) および SYCL (`sycl/src/core/verify.cpp`) の GPU Verifier で使われます。CPU-only 経路の環境変数ではありません。
- window の stamp 集計は `prof_on_ && G == 1` の場合に行われます。複数 group の window は通常の集計対象外です。layer split では各 Verifier が担当 layer の時間を計測します。
- CUDA/HIP の `--serve` でリクエスト単位の GPU stage 行を出す条件は、少なくとも decode window があり、`STRATA_DECODE_TIMING` が設定されていることです。`STRATA_VERIFY_PROFILE` だけでは同じ per-request の行は出ません。SYCL でも同様に per-request の出力は `STRATA_DECODE_TIMING` による集計内で行われます。
- SYCL ではさらに `STRATA_VERIFY_EAGER` が設定されていると、各 window 後に `verify stages T=... (ms/window):...` を stderr に出します。この経路は host-clocked とソースコメントに記されています。通常の SYCL 経路は集計された GPU stamp を報告します。
- 計測 stamp を使う都合で一部の重ね合わせ・融合経路を抑止します。CUDA/HIP では side-stream の DF branch と shared-expert fork、conv/ab 融合、wait/copy 融合、hit combine 融合などに `!prof_on_` 条件があります。プロファイル中の速度を通常実行の速度として扱わないでください。

## 実行時の詳細

window 内で GPU stage の stamp を集め、`collect_profile()` / `accumulate_profile()` が layer 種別（GDN または QSA）ごとに時間差を加算します。`profile_report()` は各項目を `prof_windows_` で割って ms/window にし、`GDN layers:`、`QSA layers:`、`total ... ms/window over ... windows` の形式で返します。呼び出し後に累計値と window 数をゼロに戻すため、次回の報告は前回報告以降の分です。

CUDA/HIP の serve 経路では、`STRATA_DECODE_TIMING` のレポート時に stderr へ `strata decode GPU stages (ms/window):...` を出します。後段の layer stage は `strata decode GPU stages, stage N (ms/window):...` です。SYCL の eager 経路では前述の per-window 行も出ます。ほかに batch の集計時にも profile report を stderr へ出す呼び出しがあります。

`docs/DETAILS.md` は `STRATA_DECODE_TIMING=1` と `STRATA_VERIFY_PROFILE=1` を合わせて使い、各 request の decode 内訳と GPU stage 内訳を読む手順を案内しています。同資料は GPU stage の event 計測が decode を少し遅くすると説明しており、速度測定ではなく比較・内訳確認向けです。特定環境の性能値はこの調査では確認していません。

## 根拠

- 値の有無判定、profile buffer 確保と失敗時の無効化: `src/core/verify.cpp:733-738`, `sycl/src/core/verify.cpp:628-641`。
- stamp の集計条件: `src/core/verify.cpp:2434`, `sycl/src/core/verify.cpp:2401-2405`。
- GDN/QSA の名称、平均値の計算、報告後の累計リセット: `src/core/verify.cpp:1836-1859`, `sycl/src/core/verify.cpp:1634-1657`。
- CUDA/HIP の計測によって一部経路を抑止する条件: `src/core/verify.cpp:906,1161,1459,1634,1662,1677`。
- SYCL eager の per-window host-clocked report: `sycl/src/core/verify.cpp:1946-1952,2401-2405`。
- serve における `STRATA_DECODE_TIMING` 判定と GPU report 出力: `src/program/generate.cpp:11883-11884,12767-12788`, `sycl/src/program/generate.cpp:10610-10611,11499-11516`。
- batch report: `src/program/generate.cpp:10157-10159,10301-10303`。
- 利用手順と計測コストの説明: `docs/DETAILS.md:314-321`。
