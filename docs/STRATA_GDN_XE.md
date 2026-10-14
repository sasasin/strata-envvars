# `STRATA_GDN_XE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有の SYCL 実装。

## 役割

SYCL backend の GDN（Gated Delta-Net）事前入力で、再帰計算に Xe 向け variant 6（16-lane sub-group kernel）を選ぶか制御します。対象箇所は `sycl/src/prefill/kernels.dp.cpp` の `gdn_xe_on()` と `gdn_recurrence()` です。CUDA/HIP の直接読み取りはこの変数にはありません。

## 値と判定

`gdn_xe_on()` は環境変数を `getenv()` で読みます。値を文字列全体として検証せず、空でない設定値には `atoi()` を適用し、結果が 0 以外なら Xe デバイス条件を調べます。

| 設定 | 選択結果 |
|---|---|
| 未設定 | Alchemist 世代かつ Xe デバイス条件を満たす場合だけ有効 |
| 空文字 | 未設定と同じ。既定条件を使う |
| 空でない値で `atoi(value) == 0` | 無効。例: `0`, `false`, `abc`, `0xyz` |
| 空でない値で `atoi(value) != 0` | Xe デバイス条件を満たす場合に有効。例: `1`, `1xyz`, `-1` |

`atoi()` のため、先頭の空白や符号、数値の後ろの文字を含む入力も整数変換規則に従います。大文字小文字は意味を持ちません（たとえば `true` は数値変換が 0 なので無効）。明示値が 0 でも、未設定時の Alchemist 既定有効には戻りません。

判定結果は関数ローカルの `static const bool` に保存されます。したがって環境変数の変更は再評価されず、最初の `gdn_xe_on()` 呼び出し時の stream/device が既定有効条件の判定にも使われます。

根拠: `sycl/src/prefill/kernels.dp.cpp:2609-2622`。

## 有効になる条件と優先順位

明示値が非ゼロ、または未設定時の Alchemist 既定条件に該当しても、device が GPU で、vendor ID が `0x8086`（Intel）、かつ device が 16-lane sub-group をサポートするときだけ有効です。未対応 device では `STRATA_GDN_XE=1` を設定しても Xe variant は選ばれません。

選択は `gdn_recurrence()` が行います。`STRATA_GDN_REC_HEADS` が設定されている場合（空文字でも presence 判定）は serial 経路となり、Xe 選択を抑止します。そうでなく `STRATA_GDN_HEAD` が非ゼロなら variant 1 が先に選ばれ、Xe 判定は行われません。それ以外で `gdn_xe_on()` が真なら variant 6、偽なら variant 0 を選びます。`STRATA_GDN_HEAD` の値も `atoi()` で判定され、こちらも最初の呼び出し時に cache されます。

variant 6 は `T > 0` のときだけ Xe device 判定後に起動します。別 device の queue で Xe variant が実行されると、`GDN Xe variant requires an Intel GPU with 16-lane sub-groups` の例外を送出します。通常の呼び出し元は GDN layer ごとに `gdn_recurrence()` を呼び、生成された `y_h` を次の出力 projection に渡します。

根拠: `sycl/src/prefill/kernels.dp.cpp:2671-2675,2763-2771`; `sycl/src/prefill/prefill.cpp:2902-2907`。

## 実行時の詳細

variant 6 は `gdn_xe_launch()` を起動します。実装は 16-lane sub-group で四つの row group と四つの列をまとめ、入力バッファを local accessor に置き、トークンごとに local-space barrier を使って状態再帰を進めます。状態を更新し、再帰の出力を `y` に書きます。通常の variant 0 は列方向の再帰カーネルを起動した後、`gdn_out_norm_kernel()` で `z`、gamma、epsilon を使った正規化と sigmoid gate を適用して `y16` に半精度出力を書きます。

**実装上の不整合:** variant 6 の分岐（`kernels.dp.cpp:2694-2698`）は `gdn_xe_launch(..., y, T)` のみを呼び、通常経路の `gdn_out_norm_kernel()` を起動しません。Xe kernel の引数にも `z`、gamma、epsilon、`y16` がなく、実装（`gdn_xe.hpp:26-29,82-86`）は再帰値を `y` に書き、状態を保存するだけです。一方、直後の出力 projection は `m.y_h`（`uint16_t*`）を入力にします（`prefill.cpp:2904-2907`）。このため、ソース上では variant 6 の経路で `y_h` を生成する処理が確認できず、通常経路と同じ最終出力処理が行われるというコメント・文書の説明を実装から裏付けられません。variant 6 が選ばれた実行で `y_h` がどのような値になるか、また出力の正しさについてはこのソース調査のみでは保証できません。

`sycl/include/strata/prefill/gdn_xe.hpp:1-5` のコメントは variant 6 を既存列カーネルと同じ bits と説明し、`docs/INTEL.md:731-742` は Alchemist での既定有効と Arc A770 での計測を記載しています。しかし、上記の `y16` 書き込みの差は現行実装で確認できるため、文書上の parity / 同一出力の主張とソースの実処理を区別する必要があります。記載計測値は同 docs にある Arc A770、oneAPI 2026.1 JIT、記載モデル・引数の条件に限られ、ここでは再計測していません。

## 根拠

- `sycl/src/prefill/kernels.dp.cpp:2605-2622` — variant の意図、Intel device 判定、値判定と static cache。
- `sycl/src/prefill/kernels.dp.cpp:2671-2698,2731-2761,2763-2771` — 選択優先順位、variant 6 起動、通常経路の norm kernel。
- `sycl/include/strata/prefill/gdn_xe.hpp:26-29,82-102` — Xe kernel の引数、出力・状態更新、launch 条件。
- `sycl/src/prefill/kernels.dp.cpp:1645-1664` — 通常経路が `z` と gamma を使い `y16` を書く処理。
- `sycl/src/prefill/prefill.cpp:2902-2907` — `gdn_recurrence()` 呼び出しと `y_h` の後続利用。
- `docs/INTEL.md:731-742` — 実装意図と計測条件（資料記載値。現行コードとの照合結果は上記のとおり）。
