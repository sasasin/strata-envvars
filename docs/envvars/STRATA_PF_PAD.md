# `STRATA_PF_PAD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの内部動作は対象外。

## 役割

prefill の FP16 GEMM で、入力 activation と一時 weight の行 stride に 64 half 分の余白を加える最適化です。`STRATA_PF_GEMM=1` と組み合わせて使います。Strix Halo（gfx1151）の HIP 実行では `STRATA_PF_PAD` が未設定ならアーキテクチャ既定値として有効になりますが、`STRATA_PF_GEMM` は別途有効化が必要です。

## 値と判定

値は数値として parse せず、環境変数が設定されていて先頭文字が `'1'` かを見ます。文字列全体、大文字小文字、後続文字は検査しません。

| `STRATA_PF_PAD` | 判定 |
|---|---|
| 未設定 | 通常は無効。gfx1151 HIP では起動時のアーキテクチャ既定値設定により `1` が設定される場合がある |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1xyz`） | 有効候補 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

有効候補でも `STRATA_PF_GEMM` の先頭文字が `1` でなければ、prefill 側の `pf_pad()` は false です。両方の判定は各翻訳単位の関数内 `static const` に保存されるため、最初の参照後にプロセス環境を変更しても再評価されません。`STRATA_PF_SWITCH_MIN_T` は別途 `std::atoll` で読み、未設定時は 0 です。

## 有効になる条件

- `STRATA_PF_PAD` と `STRATA_PF_GEMM` の両方が先頭文字 `'1'` であること。
- activation 側の行 stride を変更するのは GDN の `ssm_out` と QSA の `attn_output` の出力処理で、token 数 `T` が `max(STRATA_PF_SWITCH_MIN_T, 64)` 以上のときです。このとき stride は既定の 6144 から `6144 + 64` half になります。それより短い chunk はこの activation padding を使いません。
- quantized weight を扱う `Gemm::native` 側では HIP ビルドに限り、`T >= STRATA_PF_SWITCH_MIN_T`、`T >= 64`、`N >= 512`、`K` が 32 の倍数、`N * (K + 64) <= scratch_elems_` の全条件を満たすと、weight を `K + 64` stride に dequantize し、`strata_pf_gemm_f16_ld` を試します。変数が有効でも shape や scratch 条件を満たさない GEMM はこの最適化経路に入りません。
- gfx1151 HIP では `apply_arch_defaults()` が `STRATA_PF_PAD=1` を既定で追加します。ただし、利用者が `STRATA_PF_PAD` を何らかの値（空文字を含む）で既に設定していればその値を保持します。`STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら既定値群の追加自体を止めます。gfx12 の既定値一覧には `STRATA_PF_PAD` がありません。
- この既定値適用は HIP の generator 起動時に GPU architecture を取得できた場合に実行されます。CUDA ビルドでは呼ばれません。

## 実行時の詳細

prefill のバッファ sizing と確保は `pf_pad()` を参照し、GDN/QSA の FP16 activation 用領域を `T * (6144 + 64)` 要素に拡張します。該当 projection の直前に `ld_y` / `ld_a` を `6144 + 64`（または padding 無効時の 0）として kernel に渡し、その値を `native_proj()` から `Gemm::native()` の入力 stride にも渡します。padding 部分は行間の隙間で、GEMM の有効な `K` 要素や出力幅を増やす設定ではありません。

HIP の `Gemm::native()` は、最適化条件を満たすと `dequant_f16_ld()` で weight を padded stride に展開して `strata_pf_gemm_f16_ld()` を呼びます。この組み合わせが使えない場合も、padded X が渡されていれば HIP では通常 stride の weight を行 slice ごとに展開して padded X を読む fallback を試します。fallback に失敗すると stderr に `prefill gemm: a padded X (ldx ..., K ...) needs STRATA_PF_PAD's path` を出し、プロセスを終了します。

CUDA ビルドでも prefill 側の `pf_pad()` と activation stride の指定はコンパイルされますが、`Gemm::native()` の padded X fallback は HIP 専用です。したがって CUDA で両変数を有効にし、該当する長さの GDN/QSA projection に到達すると、padded X を処理できず上記エラーを出して終了します。通常の CUDA 起動では gfx1151 用の自動設定は行われず、既定ではこの状態になりません。

SYCL ツリーの `prefill.cpp` にも同じ activation stride 判定・適用があります。ただし、その GEMM 実装は `.dp.cpp` にあり、生成・変換済みコードを根拠にしないという調査条件に従って、ここでは SYCL GEMM の fallback や backend 固有の結果を断定しません。

## 根拠

- `src/core/arch_defaults.cpp:12-34,61-80` — gfx1151 の既定値、gfx12 の別分岐、ユーザー設定の保持、既定値追加ログ。
- `src/program/generate.cpp:2190-2196`, `sycl/src/program/generate.cpp:1999-2005` — HIP build guard と起動時の既定値適用。
- `src/prefill/prefill.cpp:350-359,963-964,1245-1255,2648-2653,2880-2883` — 両環境変数の判定、activation 領域の確保、GDN/QSA での padded stride 適用。
- `src/prefill/gemm.cu:819-853` — HIP での shape/scratch 判定、padded weight GEMM、padded X の fallback と失敗時の終了。
- `sycl/src/prefill/prefill.cpp:284-293,1184-1193,2905-2909,3194-3196` — SYCL ツリーの activation padding 判定、バッファ、呼び出し。
- `docs/STRIX_HALO.md:100-125` — gfx1151 向け設定例と `STRATA_PF_SWITCH_MIN_T` が padding にも適用される説明。ここでは測定値を新たに記載していません。
