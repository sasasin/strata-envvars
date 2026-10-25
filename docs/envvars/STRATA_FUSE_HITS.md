# `STRATA_FUSE_HITS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

検証 window の MoE 経路で、GPU resident expert の出力を `parts` に加える `moe_hit_add` と、その後の重み付き combine を一つの combine kernel にまとめます。条件を満たす場合、`moe_hit_add` の kernel launch を省きます。HIP ビルド専用です。CUDA ビルドではこの変数を読みません。

機能を使うには、環境変数だけでなく native MoE combine も有効である必要があります。これは `--native-moe-combine`、またはそれを含めて複数の native 機能を有効にする `--native` で設定されます。

## 値と判定

HIP では値を `std::atoi()` に渡し、結果が 0 かどうかで判定します。文字列全体の検証はしません。

| 値 | `fuse_hits_on()` の結果 |
|---|---|
| 未設定 | 現在の GPU が gfx1200 または gfx1201 なら有効。それ以外は無効 |
| `0`、空文字、数字で始まらない文字列 | 無効（`atoi` の結果が 0） |
| 先頭の整数部分が 0 以外 | 有効。例: `1`, `-1`, `1xyz`, ` 2` |

`atoi` は先頭の空白と符号の後にある整数部分を変換し、数字でない後続部分を無視します。したがって `0xyz` は無効、`1xyz` は有効です。オーバーフロー時の結果はここでは規定しません。

CUDA ビルドでは関数が常に `false` を返し、`getenv("STRATA_FUSE_HITS")` は実行されません。

根拠: `src/core/verify.cpp:259-275`、gfx12 判定は `include/strata/kernels/gfx_arch.hpp:35-36`。

## 有効になる条件

環境変数の判定が有効でも、各 verify group で次の条件を満たす必要があります。

- stage profiler が無効で、remote expert 最適化を使っていない。
- shared-gate combine (`sg_gated_[grp]`) の経路ではない。
- `STRATA_DEC_BATCH` が有効。これは未設定なら有効、設定時は `atoi(value) != 0` です。
- group 内の token 数 `n` が 2 以上 8 以下。
- native MoE combine が有効。
- `native_moe_combine_hits_supported()` が要求する形状とアラインメントを満たす。top-k `k` が 10、shared 出力があり、埋め込み幅 `N` が正で 4 の倍数、`parts` / `shared` / 出力が 16-byte aligned であること。

融合 kernel の呼び出し側は `hits` も 16-byte aligned であることを確認します。これを満たさない場合は融合を通常経路に切り替えず、`native_moe_combine_multi_hits_added()` が例外を投げ、verify は `verify combine: ...` をエラーとして返します。

条件を満たさない通常経路では、`moe_hit_add()` の後に通常の multi-token combine（または token ごとの combine）が実行されます。

## 実行時の詳細

`STRATA_FUSE_HITS` の値は `fuse_hits_on()` が最初に呼ばれた時点で関数内の `static const int` に保存されます。unset 時の GPU 世代判定結果もデバイス番号ごとの static 配列に保存されます（有効範囲は device index 0..63）。そのため、初回判定後の環境変数変更は反映されません。デバイス番号の取得または properties 取得に失敗した場合、unset 時の既定は無効です。明示値がある場合は世代判定を行わず、その値の判定結果を返します。

融合時は `moe_hit_add()` を省略し、fused combine kernel が destination/count から GPU hit 行を識別し、各 hit を expert part に加えてから重み付き和と shared expert 出力の加算を行います。ここは `k = 10` の vec4 kernel です。融合機能専用のログはありません。kernel 呼び出し時の例外は verify のエラー経路に渡されます。

## 根拠

- `src/core/verify.cpp:259-275`: HIP 限定の環境変数読み取り、unset 時の gfx12 判定とキャッシュ。
- `src/core/verify.cpp:845`: `STRATA_DEC_BATCH` の既定と値判定。
- `src/core/verify.cpp:1641-1666`: 融合条件、通常の `moe_hit_add()` への分岐、融合 combine の例外処理。
- `src/kernels/cuda/native_moe.cu:98-139`: hit mask を使い hit を足しながら重み付き combine を行う kernel。
- `src/kernels/cuda/native_moe.cu:177-191`: 対応形状・アラインメントの判定と、fused kernel 呼び出し時の追加検査。
- `src/program/generate.cpp:352,1866,2501-2505,3052`: native combine の既定値、`--native-moe-combine` / `--native` の設定、および kernel 側への反映。
- `docs/DETAILS.md` を `STRATA_FUSE_HITS` で検索した範囲には、この変数の動作や測定値の記載はありません。
