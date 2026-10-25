# `STRATA_PF_OCC_W`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

HIP 版の native fused prompt-expert カーネルのうち、occupancy variant を使う場合に、各 work-group の起動 grid を計算する際の「1 WGP あたりのブロック数」を上書きします。これは occupancy variant の実験用調整値です。CUDA ビルドではこの変数を読むコードがコンパイルされず、通常 variant の grid にも影響しません。

## 値と判定

値は `occ_blocks()` の関数内 static 初期化で一度 `std::getenv()` から読み、`std::atoi()` で変換します。変換結果が正のときだけ上書きに使います。

| 値 | 動作 |
|---|---|
| 未設定 | GPU 世代・型別の既定値を使う |
| 空文字、数値に変換できない文字列、`0`、負値 | `atoi` の結果が正でないため、既定値を使う |
| 正の数値 | 変換された整数を、対象 occupancy variant 全てのブロック数として使う |

`atoi` は文字列全体の厳密な数値検証をしません。先頭の空白と符号を許し、数字列の後ろに文字があっても数字列を変換します（例: `"  +3x"` は `3`）。数字列が始まらない文字列や空文字は `0` になります。したがって `3x` は 3、`-2` は既定値です。範囲外の文字列に対する `atoi` の結果は C/C++ の仕様上保証されないため、使用できる値として扱いません。

既定値は HIP の実装で次のとおりです。

| GPU / 対象 | 既定値（blocks per WGP） |
|---|---:|
| gfx11 | 4 |
| gfx12 の gate/up、型が IQ2_S または IQ2_XS | 3 |
| gfx12 のその他の occupancy variant | 4 |

## 有効になる条件

- HIP ビルドであること。環境変数の読み取り関数自体が `#if defined(__HIPCC__)` 内にあります。CUDA 側は CUDA occupancy API から得た `d.occ` を使い、この変数は参照しません。
- 対象 device で gfx11 / gfx12 の native WMMA カーネルが利用可能であること。`native_supported()` は対応する expert 型、fused 経路の有効状態、および `dev_info()` の device / kernel 判定を要求します。gfx12 の既定有効対象は IQ3_S または IQ3_XXS の gate/up で、その他の対応形式は `STRATA_PF_FUSED=1` などの fused 経路条件が必要です。`STRATA_PF_FUSED_NATIVE=0` は native 経路を無効にします。
- prompt 層が native fused 経路を選ぶこと。呼び出し側では fused/MMQ plan、`stream_all`、単一 GPU（peer 無効）、native pack および `native_supported()` を確認します。streaming chunk が `stream_all_min()` 未満ならこの経路を取りません。
- `STRATA_W_NO_OCC` が定義されていないこと。この macro が定義されると occupancy variants を使わず、grid は `wgp_blocks(d.occ)` で計算されます。その場合、この変数は無関係です。

変数が有効でも、呼び出された型が occupancy variant の対象でなければ grid に反映されません。gate/up の occupancy variant は IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ4_XS。down 側は Q2_0、Q8_0、IQ4_NL です（Q8_0 を native 経路で使う条件には別途 `STRATA_PF_FUSED_KQ=1` が含まれます）。対象外型は通常 variant と `STRATA_PF_OCC` に基づく grid を使います。

## 実行時の詳細

`occ_blocks()` は occupancy variant 用 grid を `min(タイル数に応じた上限, SM 数 × blocks-per-WGP)` で計算する箇所から呼ばれます。正の設定値は、この積の blocks-per-WGP を gate/up と down の対象型について一律に置き換えます。0 以下なら gfx11 の 4、gfx12 の型別既定値に戻ります。値が GPU の実際の同時常駐数に合うかをこの環境変数は検査しません。

読み取った値は関数内の `static const int` に保存されるため、最初の `occ_blocks()` 呼び出し時に一度だけ評価されます。その後プロセス内で環境を変更しても再読込されません。変数固有のログや警告はありません。fused native 経路を選択した場合は、呼び出し側から初回 prompt に一般的な fused-kernel の stderr ログが出ますが、その文面にはこの変数の値は含まれません。

## 根拠

- `src/prefill/moe_fused_iq.cu:988-1015`: HIP 限定の `wgp_blocks()` / `occ_blocks()`、`atoi`、既定値、環境変数の読み取り。
- `src/prefill/moe_fused_iq.cu:1027-1050,1118-1139`: gfx11/gfx12 判定、device/kernel の利用可否、および native fused 経路の条件。
- `src/prefill/moe_fused_iq.cu:1158-1178`: `STRATA_W_NO_OCC` 分岐、occupancy variant の対象型、grid 計算。
- `src/prefill/prefill.cpp:228-240,2982-2987,3013-3023`: native pack の buffer 条件、peer / stream / plan 条件、prompt 経路の選択。
- `docs/DETAILS.md:1982` と `docs/AMD_HIP.md:357-369`: fused prompt expert 経路と `STRATA_PF_FUSED` の説明。`STRATA_PF_OCC_W` の値・挙動に関する説明や測定値はこれらの資料にはありません。
