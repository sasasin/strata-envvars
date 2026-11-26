# STRATA_GDN_PP

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-26 時点）。

## 役割

AMD HIP の gated-delta-net (GDN) recurrence で、通常の STRATA_GDN_HEAD=1 経路が選んだ quad recurrence kernel を、PP kernel に切り替える診断・最適化スイッチです。値 2 は 2 列/レーンの gdn_rec_quad2c_kernel、それ以外の非ゼロ整数は gdn_rec_quad_pp_kernel を選びます。0 は標準の gdn_rec_quad_kernel を使います。いずれも recurrence の状態と出力を計算し、その後の出力 norm も呼び出し経路に応じて実行します（engine/src/prefill/kernels.cu:1579-1587,1705-1719,3122-3139）。

この分岐は __HIPCC__ の AMD 用コード内にあります。通常の CUDA build ではこの読み取り分岐がコンパイルされず、STRATA_GDN_PP は CUDA 側の recurrence kernel を選びません（engine/src/prefill/kernels.cu:1461,3088,3142-3144）。engine/sycl/src/prefill/kernels.dp.cpp にも同じ __HIPCC__ 条件の実装があります（同ファイル 1341,2817-2863）。

## 値と判定

T > 0 かつ recurrence の variant == 1 で初めて分岐を通る際、std::getenv の結果を std::atoi に渡し、その結果を関数内 static const int pp に保存します。未設定は 0、設定された空文字列も atoi("") == 0 です。文字列全体の妥当性検査、範囲検査、clamp はありません（engine/src/prefill/kernels.cu:3122-3130）。

| 判定結果 | 例 | 選択される kernel |
|---|---|---|
| unset または atoi 結果が 0 | unset、空文字、0、true、x、0anything | gdn_rec_quad_kernel |
| atoi 結果がちょうど 2 | 2、02、+2、2tail、先頭空白の後の 2 | gdn_rec_quad2c_kernel |
| atoi 結果が 0 以外で 2 ではない | 1、3、-1、1tail | gdn_rec_quad_pp_kernel |

atoi は先頭の空白と符号付き10進数を解釈し、数字の後ろの文字列は検査しません。数値に変換できない先頭なら 0 です。整数型に収まらない入力の動作は C ライブラリの atoi の範囲外であり、Strata は定義していません。

HIP の起動時アーキテクチャ既定値が設定される場合、既に値が設定されていればその値（空文字を含む）を尊重し、未設定時のみ "2" を入れます。該当するのは gfx1151、gfx12 (gfx1200/1201)、および discrete RDNA3 の gfx1100/1101/1102 です。gfx1151 は STRATA_GFX1151_DEFAULTS=0、gfx12 は STRATA_GFX12_DEFAULTS=0、gfx1100/1101/1102 は STRATA_GFX11_DEFAULTS=0 でその既定値群を無効化できます（engine/src/core/arch_defaults.cpp:41-49,64-73,302-324; engine/include/strata/core/gfx11_extra.hpp:27-50）。

## 有効になる条件

- HIP build で AMD 用 recurrence 実装が使われること。CUDA build にはこの PP 分岐がありません（engine/src/prefill/kernels.cu:1461,3088-3144）。
- 通常経路で STRATA_GDN_HEAD が非ゼロとして解釈され、STRATA_GDN_REC_HEADS が未設定であること。head と serial はそれぞれ初回読み取り時に static cache され、両者から variant == 1 が作られます（engine/src/prefill/kernels.cu:3286-3293,3309-3314）。
- 対象呼び出しの token 数 T が 1 以上であること。T <= 0 では pp の読み取りも kernel launch もありません（engine/src/prefill/kernels.cu:3122-3124）。
- STRATA_GDN_REC_HEADS は設定有無で判定され、空文字でも serial 経路となり、この PP 分岐を通りません（engine/src/prefill/kernels.cu:3087,3289-3293）。

アーキテクチャ既定値は HIP build の起動処理 generate.cpp から呼ばれる apply_arch_defaults が設定します。GFX1151/GFX12 の表は GPU 0 の arch に基づき、RDNA3 discrete の追加表は integrated == false の場合に適用されます。ユーザーが設定した値は既定値処理により上書きされません（engine/src/program/generate.cpp:4287-4320; engine/src/core/arch_defaults.cpp:302-324; engine/include/strata/core/gfx11_extra.hpp:41-50）。

## 実行時の詳細

通常の HIP recurrence は gdn_recurrence が STRATA_GDN_HEAD を見て variant を決め、STRATA_GDN_REC_HEADS が未設定なら variant 1 を渡します。full-output 経路と state-only 経路の双方が共通の gdn_recurrence_impl を通り、variant 1 かつ T > 0 の場合に STRATA_GDN_PP を読みます（engine/src/prefill/kernels.cu:3083-3087,3122-3139,3286-3293,3309-3314）。

値 2 の kernel は lane あたり 2 列を処理します。0 以外で 2 でない値は別の PP kernel に切り替えます。0 は標準 quad kernel です。読み取り値は関数内 static に一度だけ保存されるため、最初の該当呼び出し後にプロセス環境を変更しても反映されません。最初の該当呼び出しが T <= 0 なら初期化されず、その後の T > 0 呼び出しで読み取られます（engine/src/prefill/kernels.cu:3122-3130）。

この変数を読む CLI 引数や別の環境変数による優先順位変更はありません。起動時の arch defaults は「未設定かどうか」で値を補いますが、kernel 側の atoi 結果が最終選択を決めます（engine/src/core/arch_defaults.cpp:307-310,320-324; engine/src/prefill/kernels.cu:3124-3130）。

## ログと測定値

この変数の値を表示する個別ログはありません。既定値が arch defaults によって新たに設定された場合は、gfx1151/gfx12 で strata: gfx1151 (Strix Halo) または strata: gfx12 (RDNA4) から始まる既定 switch 一覧、discrete RDNA3 で strata: gfx11 (RDNA3): ... exact speed switches on by default ... の一覧に GDN_PP が現れます。ユーザー設定済みの値は一覧に含まれません（engine/src/core/arch_defaults.cpp:307-310,325-332,360-370,397-404）。kernel launch 後の CUDA/HIP エラーは check("gdn_recurrence (quad)") から exit_device_error に渡され、表示名は prefill gdn_recurrence (quad) です（engine/src/prefill/kernels.cu:3139,110-116）。

コードコメントは PP=1 と PP=2 の実装について元 kernel と同じ arithmetic/order と記しています。Strix Halo の技術資料も STRATA_GDN_PP=2 を GDN recurrence の「two columns per lane」と説明し、maintainer の測定条件で同一出力と報告しています。これは資料に記載された測定内容であり、本調査では再測定していません（engine/src/prefill/kernels.cu:1579-1584,1705-1710; docs/STRIX_HALO.md:104-112）。

## 根拠

- engine/src/prefill/kernels.cu:1461-1479,1579-1587,1705-1719 — HIP 専用 kernel 群と PP kernel の説明。
- engine/src/prefill/kernels.cu:3083-3144,3281-3314 — recurrence variant、STRATA_GDN_PP の読み取り、選択、cache。
- engine/src/core/arch_defaults.cpp:28-73,302-332,360-404 — アーキテクチャ別既定値、ユーザー値の維持、ログ。
- engine/include/strata/core/gfx11_extra.hpp:27-50 — discrete RDNA3 の対象条件と PP=2 既定値。
- engine/src/program/generate.cpp:4287-4320 — HIP 起動時の GPU 判定と既定値適用。
- engine/sycl/src/prefill/kernels.dp.cpp:1341-1359,2817-2863 — 同名の HIP 条件付き実装。
- docs/STRIX_HALO.md:104-112 — Strix Halo の説明と記載された測定範囲。
