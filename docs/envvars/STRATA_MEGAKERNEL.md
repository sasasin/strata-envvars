# `STRATA_MEGAKERNEL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP で動く verifier の GDN 層に対し、条件を満たすと通常の複数カーネル列の代わりに `mk_gdn_dense` を使う opt-in です。融合カーネルは入力量子化、QKV / gate 射影、conv、GDN 再帰、出力射影を一つの persistent kernel にまとめます。環境変数はこの経路の候補を有効にするだけで、すべての verifier / GDN 層で使われる保証はありません。呼び出し箇所は `Verifier::init` と `Verifier::record_window` の GDN 処理です（`engine/src/core/verify.cpp:380-390, 1062, 1860-1896`）。

索引候補にはなっていますが、Strata が `getenv` で値を読む実装は `engine/src/core/verify.cpp:383` の一箇所です。`docs/SETTINGS.md:156` は対応を「NVIDIA and AMD」としていますが、実際の読み取り・有効化は `STRATA_USE_HIP` が定義され、`STRATA_HIP_GFX906` が未定義のビルドに限られます。CUDA では読み取り分岐自体がなく、Metal の初期化経路もこのコードより前に戻ります（`engine/src/core/verify.cpp:378-390, 978-993`）。

## 値と判定

HIP（`STRATA_USE_HIP` 定義、`STRATA_HIP_GFX906` 未定義）の場合、初回の `g_megakernel()` 呼び出し時に `std::getenv` で読み、非 null の値へ `std::atoi` を適用して、結果が 0 以外なら ON とします。文字列全体の検証、範囲検証、警告はありません。`atoi` の通常の変換規則では、先頭空白と符号の後の数字列を読み、数字列の後ろは無視します。数値として変換できない接頭部は 0 になります。

| ビルド条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP、gfx906 以外 | OFF | `1`, `-1`, `+2`, ` 1`, `1tail`（変換結果が非 0） | 空文字、`0`, `0tail`, `true`, `False`, `tail`（変換結果が 0） |
| CUDA / Metal / HIP gfx906 | OFF（読み取りなし） | 該当なし | すべて（このビルド分岐では変数を参照しない） |

`atoi` の戻り値に対する明示的な上下限チェックはありません。`atoi` で `int` に表せない値の結果は C/C++ の仕様上扱いが定義されないため、範囲外文字列の動作は保証できません（`engine/src/core/verify.cpp:380-390`）。

## 有効になる条件

- `STRATA_USE_HIP` ビルドであり、`STRATA_HIP_GFX906` が定義されていないこと。その他のビルドでは `g_megakernel()` は常に false を返します（`engine/src/core/verify.cpp:380-390`）。
- verifier の初期化が mapped staging の確保まで成功し、megakernel counter の確保も成功すること。確保失敗時はポインタが null のままなので融合経路は選ばれず、ここでは専用の失敗ログを出しません（`engine/src/core/verify.cpp:1041-1062`; `engine/src/kernels/cuda/megakernel_gdn.cu:566-571`）。
- verifier が全モデル層を単独で扱い（`lb_ == 0`, `le_ == g.n_layers`, `next_ == nullptr`）、branch / side mixer / side projection / batch recurrence / self-commit の各経路でないこと（`engine/src/core/verify.cpp:1878-1881`）。
- GDN 層の当該窓で `tb == 0`、トークン列数 `n` が 1〜8、QKV・gate・出力の各重み `native_type` がすべて `8`（`Q8_0`）であること（`engine/src/core/verify.cpp:1878-1881`; `engine/include/strata/quant/types.hpp:12-15`）。それ以外は通常の GDN カーネル列へ進みます（`engine/src/core/verify.cpp:1896` 以降）。
- `docs/SETTINGS.md` の「NVIDIA and AMD」という分類はこの実装条件を正確に表していません。ソース上で確認できるのは HIP 側の条件であり、CUDA/NVIDIA でこの変数が融合経路を有効にする根拠はありません（`engine/src/core/verify.cpp:380-390`; `docs/SETTINGS.md:156`）。

この変数を上書きする CLI 引数や別環境変数の読み取りは、Strata ソースの候補名全参照検索では見つかりませんでした。融合経路の成立は上記の verifier / データ条件にも依存します。

## 実行時の詳細

値は関数内 `static const bool on` の初期化で一度読み取られます。最初の `g_megakernel()` 呼び出しは verifier の初期化中、mapped staging 確保後の counter 確保判定です。そのため同一プロセスで後から環境を書き換えても反映されず、以後の呼び出しはキャッシュ値を使います（`engine/src/core/verify.cpp:380-390, 1058-1062`）。

有効時は verifier ごとに 16 個の `unsigned` 用 device buffer を確保・ゼロ初期化し、条件に合う GDN 層で `MkGdnArgs` を組み立てて `mk_gdn_dense` を呼びます（`engine/src/core/verify.cpp:1062, 1878-1894`; `engine/src/kernels/cuda/megakernel_gdn.cu:566-571`）。条件に合わない層は `else` 側の通常カーネル処理を使います（`engine/src/core/verify.cpp:1896` 以下）。

mapped stall word に非 0 の値が書かれていた場合、window 完了後に `strata verify: STRATA_MEGAKERNEL: phase %u stalled on CUDA%d (WDDM/occupancy guard); disabling megakernel and replaying window with plain kernels` を stderr に出し、word をクリアして megakernel を無効化したうえで同じ window を再実行します。この無効化フラグ `g_mk_off` はプロセス内で共有され、それ以降 `g_megakernel()` は false を返します（`engine/src/core/verify.cpp:379-390, 4291-4323`）。

## ログと測定値

通常の有効化・無効化だけを知らせるログはありません。counter 確保失敗にもこの箇所からの専用ログはありません。stall 検出時だけ、上記の固定文言を stderr に出して window を通常カーネルで再実行します（`engine/src/core/verify.cpp:1062, 4302-4309`）。Strata の説明資料からこの環境変数に結び付く条件付き測定値は確認できませんでした。

## 根拠

- 値の読み取り、変換、ビルドガード: `engine/src/core/verify.cpp:380-390`
- 初回の読み取り呼び出しと counter 確保: `engine/src/core/verify.cpp:1058-1062`; allocator: `engine/src/kernels/cuda/megakernel_gdn.cu:566-571`
- GDN 層で融合経路を選ぶ全条件とカーネル呼び出し: `engine/src/core/verify.cpp:1878-1896`; `Q8_0` type id: `engine/include/strata/quant/types.hpp:12-15`
- 融合カーネルがまとめる処理: `engine/include/strata/kernels/megakernel.hpp:4-7`
- stall の観測、無効化、window 再実行: `engine/src/core/verify.cpp:4291-4323`
- 索引表記との照合: `docs/SETTINGS.md:156`
