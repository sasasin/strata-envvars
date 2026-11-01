# `STRATA_CVEC_FUSE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

制御ベクトルを適用する prefill の層で、hyper-connection の FFN 書き込み、制御ベクトル適用、次の半層の正規化を一つのカーネルにまとめます。対象は通常の CUDA/HIP prefill と SYCL prefill です。制御ベクトルの有効・無効そのものを切り替える変数ではなく、制御ベクトルがロードされ、その層が適用対象になった場合に融合経路を選ぶためのスイッチです。無効時や融合条件を満たさない場合は通常の書き込みと `cvec_apply` に分かれます（`src/prefill/prefill.cpp:5557-5563,5603-5615`; `sycl/src/prefill/prefill.cpp:4693-4707,4795-4807`）。

## 値と判定

CUDA/HIP と SYCL の実装は、`getenv()` が返す文字列の先頭文字だけを `'1'` と比較します。数値 parse や文字列全体の比較はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効（ただし後述のアーキテクチャ既定値または setup の設定が適用される場合を除く） |
| 空文字 | `getenv()` が空文字へのポインターを返す場合は無効。先頭文字が `'1'` ではない |
| `1` で始まる値 | 有効。例: `1`, `10`, `1anything` |
| その他 | 無効。例: `0`, `true`, ` 1`, `2` |

判定結果は `cvec_fuse()` 内の関数ローカル `static const bool` に保存されます。最初に関数が呼ばれて判定された後、プロセス内で環境値を変更しても再評価されません（`src/prefill/prefill.cpp:502-505`; `sycl/src/prefill/prefill.cpp:343-346`）。

## 有効になる条件

フラグが有効でも、次の条件がそろった層でだけ融合経路を使います。

- 層の第 2 half（FFN write 側）で、制御ベクトルがロード済みかつその層をカバーしている。
- `STRATA_GR_UNFUSED` が `1` でない（この変数も先頭文字が `1` かで判定）。
- 次の層 `nl` が `LE` 未満で、最終層ではない。
- `nl == 1 && ple_on` の例外経路でない。
- 制御ベクトルの `n_embd` と `hc` が現在の prefill と一致し、現在デバイスに制御ベクトルの表がある。

これらは CUDA/HIP と SYCL で同じ条件です（`src/prefill/prefill.cpp:5556-5563`; `sycl/src/prefill/prefill.cpp:4693-4700`）。制御ベクトルは `--control-vector` / `--control-vector-scaled` などからロードされます。ロードがなければ `Cvec::covers()` は false なので、この環境変数だけでは何も融合しません（`src/program/generate.cpp:3289-3304,2064-2069,2124-2127`; `include/strata/kernels/cvec.hpp:25-36,39-57`）。要求レベル（`Cvec::on`）がオフなら融合カーネル内の `steer` も false になり、そのリクエストでは制御ベクトルを適用しません。フラグはこの per-request 状態を上書きしません（`src/prefill/kernels.cu:221-225,251-266`; `sycl/src/prefill/kernels.dp.cpp:281-297`）。

## 既定値と優先順位

HIP エンジンはデバイス判定後、engine code が各 switch を初めて読む前にアーキテクチャ既定値を環境へ設定します。既定値の対象は gfx12（RDNA4）の表と gfx1151（Strix Halo）の表で、どちらも `STRATA_CVEC_FUSE=1` を含みます。`setenv(..., overwrite=0)` を使い、変数がすでに存在すれば値を変えません。したがって明示した `0` や空文字も既定値より優先されます（`src/core/arch_defaults.cpp:25-57,59-81,167-180`; `src/program/generate.cpp:3383-3400`）。gfx12 は `STRATA_GFX12_DEFAULTS` の先頭が `0` なら既定表全体を適用しません。gfx1151 も `STRATA_GFX1151_DEFAULTS` の先頭が `0` なら同様です。明示した `STRATA_CVEC_FUSE=1` はそれらの既定表を抑制しても読み取られます（同 `arch_defaults.cpp:38-47,55-57`）。

gfx1103 と gfx1150 は engine 側のアーキテクチャ既定表には含まれません。HIP でそれぞれの experimental opt-in を使った setup は、作成する実行設定の `env` にこの変数を含む switch 群を書き込みます（`setup.py:3684-3697,10316-10327`）。serve の engine 起動時は設定の `env` を継承環境へ上書き適用するため、設定にこの値があれば、起動元環境より設定値が優先されます（`serve/server.py:3750-3760`）。

`--control-vector-scaled` は制御ベクトルのロードを指定する CLI 引数であり、`STRATA_CVEC_FUSE` の値を直接指定する CLI 引数ではありません（`src/program/generate.cpp:3289-3304`）。この変数の値は prefill 側で初回参照時に static cache されます。

## 実行時の詳細

適用層で融合条件を満たすと `gr_write_cvec_norm_rs()` を呼び、残差 `R` への hyper-connection write、ベクトル適用、次 half の norm と BF16/FP16 画像生成をまとめて行います。通常経路ではこれを `gr_write`、`cvec_apply`、`gr_norm_rs` に分けます（`include/strata/prefill/kernels.hpp:32-40`; `src/prefill/prefill.cpp:5603-5615`; `src/prefill/kernels.cu:207-268`）。

この変数が無効、または層・モデル状態などの条件が不成立なら fused cvec 経路を選びません。`steered && !cv_fused` の場合は通常の書き込み後に `cvec_apply` を呼ぶため、環境変数がオフでも制御ベクトルの適用自体は続きます（`src/prefill/prefill.cpp:5607-5615`; `sycl/src/prefill/prefill.cpp:4799-4807`）。通常の有効・無効判定について専用の警告や起動ログはありません。

隣接する診断変数 `STRATA_CVEC_FUSE_CHECK` が正数として読み取られている場合、融合経路に入った最初の指定回数について、コピー上で従来経路も実行し、`R`・row scales・`xn16` が `identical` か `DIFFERS` かを stderr に出します。この比較は融合条件を通った場合だけ行われます（CUDA/HIP: `src/prefill/prefill.cpp:5570-5601`; SYCL: `sycl/src/prefill/prefill.cpp:4707-4710,4789-4793`）。

## 根拠

- 環境値の読み取りと static cache: `src/prefill/prefill.cpp:502-505`, `sycl/src/prefill/prefill.cpp:343-346`。
- 適用条件・fallback: `src/prefill/prefill.cpp:5556-5563,5603-5615`, `sycl/src/prefill/prefill.cpp:4693-4700,4795-4807`。
- fused kernel と通常経路に対応する処理: `include/strata/prefill/kernels.hpp:32-40`, `src/prefill/kernels.cu:207-268`, `sycl/src/prefill/kernels.dp.cpp:258-330`。
- 制御ベクトルの load / table 状態: `src/program/generate.cpp:2064-2069,2124-2127`, `include/strata/kernels/cvec.hpp:25-57`。
- HIP のアーキテクチャ既定値と明示環境値の優先: `src/core/arch_defaults.cpp:25-57,59-81,167-189`, `src/program/generate.cpp:3383-3400`。
- gfx1103/gfx1150 setup 設定と serve 起動環境への適用: `setup.py:3684-3697,10316-10327`, `serve/server.py:3750-3760`。
