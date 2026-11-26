# `STRATA_FUSE_CONVAB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象 checkout は `main` で、調査開始時の作業ツリーに変更はなかった。

## 役割

HIP build の verify window で、GDN の convolution + L2 norm と a/b projection を別々の kernel launch ではなく `gdn_conv_ab_multi` の一回の launch にまとめる opt-in です。HIP backend は `STRATA_USE_HIP=1` を定義し、build source list に `verify.cpp` と `verify_kernels.cu` を含みます。`Verifier::record_window` が GDN layer を処理するときに条件を満たせば融合 launcher を選びます。値が有効でも、この変数単独で全 GDN 処理が融合されるわけではありません（`engine/src/core/verify.cpp:525-532,1860-1867,1931-1956`; `engine/cmake/hip_backend.cmake:105-109`; `engine/cmake/strata_gpu_engine.cmake:96,310-316`）。

CUDA build では、この関数は環境変数を読み取らず常に `false` を返すため、この切り替えによる融合は選ばれません。HIP build では GPU 世代を調べる条件はなく、対象処理の分岐条件を満たす GDN layer に適用されます（`engine/src/core/verify.cpp:526-532,1931-1956`）。

## 値と判定

HIP 側は `std::getenv` の結果を `std::atoi(v) != 0` で bool 化します。文字列全体の厳密な数値検証や `true` / `false` の文字列比較はありません。`atoi` が数値変換できない場合は 0 となり、数値の後ろにある文字も判定から除外されます。空文字は「設定済み」でも 0 と判定されます（`engine/src/core/verify.cpp:526-530`）。

| build | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP (`STRATA_USE_HIP`) | 無効 | `1`, `-1`, `+1`, `01`, `1anything`（先頭から `atoi` が非 0 を得る） | `0`, `0anything`, 空文字, `true`, `false`, `anything` |
| CUDA (`STRATA_USE_HIP` なし) | 常に無効 | なし | 設定値にかかわらず無効 |

`atoi` は先頭の空白を読み飛ばすため、表の HIP 行の ` 1` は**有効**です。大文字小文字は文字列として比較されません。`true` と `false` は整数変換の先頭で数字がないため、どちらも無効です。数値として表現できる範囲の検査、文字列末尾の検査、値の clamp はありません（`engine/src/core/verify.cpp:528-532`）。

## 有効になる条件

- HIP build であること。CUDA build では環境変数を読まず無効です（`engine/src/core/verify.cpp:527-532`）。
- verify window の処理対象 layer が GDN であること（QSA layer はこの分岐を通りません）（`engine/src/core/verify.cpp:1860-1862,1931`）。
- `STRATA_FUSE_CONVAB` が初回評価時に非ゼロとして変換されること（`engine/src/core/verify.cpp:528-529`）。
- `br`（DF branch）、`batch_rec_`（batch recording）、`prof_on_`（verify profile）、`sidem`（side mixer の実使用）がすべて false であること。これらのどれかが true なら `fuse_ab` は false となり、conv と a/b projection は別経路になります（`engine/src/core/verify.cpp:1262,1503-1515,1610,1931-1956`）。profile は `STRATA_VERIFY_PROFILE` が設定されていると有効になります。確保失敗時は `prof_on_` が false に戻ります（`engine/src/core/verify.cpp:1262-1276`）。
- `sidem` は side mixer が有効で、batch 時には `batch_side_mixer_on()` も有効な場合に true です。side mixer の設定は `STRATA_SIDE_MIXER` の値から決まります（`engine/src/core/verify.cpp:1503-1515`）。
- GPU 世代、OS、モデル量子化形式を判定する追加条件は、この融合選択箇所にはありません。呼び出し元は GDN の重み参照を解決し、必要な重みがなければ先に失敗します（`engine/src/core/verify.cpp:1860-1870`）。
- CLI 引数、設定ファイル、別環境変数による `STRATA_FUSE_CONVAB` 自体の上書きは、Strata のソース内に見つかりません。上記の別条件は有効値を上書きせず、この launch の選択だけを無効にします。

## 実行時の詳細

`fuse_convab_on()` 内の関数ローカル `static const bool` 初期化子が、最初にこの関数を呼んだとき一度だけ環境を読みます。そのため、その後プロセス内で環境を変更しても値は更新されません。未設定は false です（`engine/src/core/verify.cpp:526-532`）。

融合条件が成立すると `record_window` は `gdn_conv_ab_multi(...)` を呼び、成立しない場合は `gdn_conv_l2_multi(...)` を呼んだ後、通常の a/b projection を別に実行します。batch recording の場合は slot ごとに `gdn_conv_l2_multi` を実行する分岐に入り、融合選択に進みません（`engine/src/core/verify.cpp:1931-1965`）。融合 kernel は block 群を conv body と a/b body に分け、別入力・別出力の処理を同じ launch に載せます（`engine/src/kernels/cuda/verify_kernels.cu:185-201`）。launcher は引数を検証し、不正なら stderr に `gdn_conv_ab_multi: invalid arguments` を出して `exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:1199-1222`）。

## ログと測定値

融合選択箇所は dispatch stats に `gdn layer: conv+ab fused=%ld batch_rows=%ld` を記録します。これは通常の stderr ログではなく、dispatch stats が有効なときに集計され、`--stats` の stdout レポート、または `STRATA_DISPATCH_REPORT` で指定したファイルのレポートから確認できます。dispatch stats は既定で有効で、`STRATA_DISPATCH_STATS=0` で無効になります（`engine/src/core/verify.cpp:1931-1933`; `engine/include/strata/core/dispatch_stats.hpp:8-11,107-119,145-152`）。

`verify.cpp` のコメントには gfx1201 で `-0.3%` とありますが、モデル、OS、設定、測定回数などの条件が記載されていません。`docs/DETAILS.md` と `docs/GDN_CONTRACT.md` にこの環境変数または当該測定の条件付き記録は見つからないため、性能値を一般化できません（`engine/src/core/verify.cpp:525`; `docs/DETAILS.md`; `docs/GDN_CONTRACT.md`）。この環境変数専用の警告・終了ログはありません。融合 launcher 自体の引数不正時の stderr と終了については前節のとおりです。

## 根拠

- `engine/src/core/verify.cpp:525-532` — HIP/CUDA で異なる環境変数の読み取りと既定値。
- `engine/src/core/verify.cpp:1860-1870,1931-1965` — GDN 層の分岐、融合条件、通常経路と batch 経路。
- `engine/src/core/verify.cpp:1262-1276,1503-1515,1610` — profile、side mixer、DF branch の条件。
- `engine/src/kernels/cuda/verify_kernels.cu:185-201,1199-1222` — 融合 kernel と launcher の処理、引数不正時の終了。
- `engine/include/strata/core/dispatch_stats.hpp:8-11,107-119,145-152` — dispatch stats の有効条件とレポート方法。
