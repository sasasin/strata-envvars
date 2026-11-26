# `STRATA_SMALL_UNR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の2つの小さな密行列カーネルで、ループによるロード順を固定回数のアンロール済みロードへ切り替えるビットスイッチです。bit 0 は BF16 重みの router-shaped read、bit 1 は GDN の a/b 射影に対応します。対象処理では積和の順序を保ったまま複数パスのロードを先行させますが、切替対象は後述する `n_in == 2560` のカーネル分岐に限られます。候補名の全参照を検索した結果、本番コードで環境から直接読む箇所は以下の2関数で、他の一致は既定値表、資料、設定登録、テスト、コメントでした（`engine/src/kernels/cuda/native_bf16.cu:72-102,117-165`; `engine/src/kernels/cuda/verify_kernels.cu:112-135`）。

## 値と判定

両読取箇所とも、設定値を `std::atoi` で整数に変換し、bit 0 は `value & 1`、bit 1 は `(value >> 1) & 1` で取り出します。文字列全体の妥当性検査はなく、`atoi` が先頭の空白を読み飛ばして数値として読める先頭部分を変換し、先頭に数字がない文字列や空文字列は 0 になります。したがって `1x` は bit 0 のみ、`2x` は bit 1 のみが有効で、` 1` は bit 0 のみ有効です。`0anything`、`true`、`false` は 0 となり無効です。値の範囲検査や clamp はありません。`atoi` の変換範囲外の入力の結果は規定できません。大小文字の判定はありません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の BF16 matvec（bit 0） | CUDA sm_120 は既定 `3`（`STRATA_SM120_PERF` が未設定または `atoi` 結果が非 0 で、`STRATA_DEFAULTS` が `026` 系トークンでない場合）。sm_70 は可視 GPU が同一 compute capability で、`STRATA_SM70_PERF=0` と `STRATA_DEFAULTS=026` のいずれも指定されていない場合に、起動時に `3` が環境へ注入されます。それ以外の CUDA capability は読取関数の既定 `0`（sm_121 は本スイッチの既定値対象外）。読取関数では属性取得後の既定値をデバイスごとにキャッシュ | 奇数。例: `1` は bit 0 のみ、`3` は bit 0 と bit 1 | 偶数。例: `0`、`2`、`4`、空文字、`true` |
| CUDA の GDN a/b 射影（bit 1） | CUDA sm_120 は既定 `3`（`STRATA_SM120_PERF` が未設定または `atoi` 結果が非 0 で、`STRATA_DEFAULTS` が `026` 系トークンでない場合）。sm_70 は可視 GPU が同一 compute capability で、`STRATA_SM70_PERF=0` と `STRATA_DEFAULTS=026` のいずれも指定されていない場合に、起動時に `3` が環境へ注入されます。それ以外の CUDA capability は読取関数の既定 `0`（sm_121 は本スイッチの既定値対象外）。読取関数では属性取得後の既定値をデバイスごとにキャッシュ | bit 1 が立つ整数。例: `2` は bit 1 のみ、`3` は両方 | bit 1 が立たない整数。例: `0`、`1`、`4`、空文字、`false` |
| HIP コンパイル時の同じ2箇所 | `0` | なし | すべて。`__HIPCC__` 分岐で `0` を返す |

明示値は `atoi` 後の下位ビットで判定されるため、例えば `5` は bit 0 のみ、`6` は bit 1 のみを有効にします。設定値が存在する場合は `atoi` の結果をそのまま使うので、アーキテクチャ既定値を参照しません（`engine/src/kernels/cuda/native_bf16.cu:341-358`; `engine/src/kernels/cuda/verify_kernels.cu:1256-1273`）。

## 有効になる条件

- **BF16 matvec / bit 0:** `mmvf_fast_bit()` の値が非ゼロで、実際に起動されるカーネルが `BLOCK_SIZE == 256` かつ `n_in == 2560` の場合に限り、通常のペア単位ループに代わって5回の router-shaped load を使います。入力幅が別の値なら通常ループです（`engine/src/kernels/cuda/native_bf16.cu:72-102,142-165`）。
- **GDN a/b 射影 / bit 1:** `gdn_ab_fast()` の値が非ゼロで、`gdn_ab_body()` の `n == 2560` の場合に限り、10回の固定回数ロードを使います。それ以外は通常経路です（`engine/src/kernels/cuda/verify_kernels.cu:112-135`）。
- 2箇所の関数は HIP コンパイラでは環境値を読む前に `0` を返します。したがって、この環境変数はこの実装では CUDA 経路に限ってカーネル切替に作用します（`engine/src/kernels/cuda/native_bf16.cu:345-347`; `engine/src/kernels/cuda/verify_kernels.cu:1260-1262`）。
- 起動時のアーキテクチャ既定値は、明示設定がない場合だけ挿入されます。CUDA sm_120 は `small_unr_default()` が `3` を返す条件で既定有効、`STRATA_SM120_PERF=0` または `STRATA_DEFAULTS=026` では既定無効です。sm_121 ではこの既定値関数の当該スイッチ定数が `false` です（`engine/include/strata/core/bw_dense_defaults.hpp:18-19`; `engine/include/strata/core/sm120_series.hpp:60-81,93-101`; `engine/include/strata/core/defaults_026.hpp:21-29`）。
- NVIDIA sm_70 では、`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` でない場合に `nv_default_env()` が `3` を候補にし、全可視カードの compute capability が同一の経路で挿入します。RDNA4 gfx12、Windows gfx1151、および discrete RDNA3 gfx11 の表にも `"3"` が含まれますが、ここで説明している CUDA カーネル関数は HIP コンパイル時に常に 0 を返します（`engine/src/core/nv_defaults.cpp:136-163`; `engine/src/core/arch_defaults.cpp:30-62,64-105`; `engine/include/strata/core/gfx11_extra.hpp:39-73`; `engine/src/kernels/cuda/native_bf16.cu:345-347`; `engine/src/kernels/cuda/verify_kernels.cu:1260-1262`）。
- `STRATA_MMVF_CHECK` は bit 0 の経路だけに関係します。`STRATA_MMVF_CHECK` の先頭文字が `'1'` の場合、bit 0 が有効なときに `fast=2` とし、router-shaped 経路に加えて通常読出しも計算して比較します。診断自体の有効判定は初回に static cache されます（`engine/src/kernels/cuda/native_bf16.cu:360-370`）。

## 実行時の詳細

エンジンの GPU 初期化時に `apply_arch_defaults()` がアーキテクチャ表の値を環境へ追加し、明示的に設定済みならその値を保持します。NVIDIA は同じく `apply_nv_defaults()` が候補値を設定します。CUDA の `generate.cpp` は GPU プロパティ取得後に前者を呼び、全可視カードの compute capability が一致した場合に後者を呼びます（`engine/src/core/arch_defaults.cpp:302-323`; `engine/src/core/nv_defaults.cpp:222-239`; `engine/src/program/generate.cpp:4288-4320,4435-4449`）。表から値を設定した場合は起動ログにもスイッチ名が出ます（`engine/src/core/arch_defaults.cpp:325-332`; `engine/src/core/nv_defaults.cpp:240-255`）。

カーネル側では `mmvf_fast_bit()` と `gdn_ab_fast()` の呼び出しごとに環境値を読み直します。値が設定されていれば毎回それを優先します。未設定なら、現在デバイスの capability から既定値を初回取得時に `per_dev[64]` へキャッシュし、その後はそのデバイスの値を再利用します。実行中に環境変数を変更した場合、明示値は次回呼び出しから反映されますが、unset に戻した場合はすでにキャッシュされたアーキテクチャ既定値へ戻ります（`engine/src/kernels/cuda/native_bf16.cu:341-358`; `engine/src/kernels/cuda/verify_kernels.cu:1256-1273`）。

この変数専用の CLI 引数は確認できません。エンジンの親プロセスで環境変数を設定すれば、起動時の既定値処理より前に設定済みとなり、既定値より優先されます。`STRATA_MMVF_CHECK=1` による比較結果はプロセス終了時に `stderr` へ `strata mmvf check: ...` 形式で出ます。差異数が 0 でも同じ書式で報告します（`engine/src/kernels/cuda/native_bf16.cu:335-338,360-370`）。

## ログと測定値

sm_70 の既定値表が適用されて値を挿入した場合、`strata: sm_70 (Volta): ... exact speed switches on by default ...` の一覧に `SMALL_UNR` が含まれます。sm_120 での既定値による当該スイッチ単独の起動ログは、ここで確認した実装にはありません（`engine/src/core/nv_defaults.cpp:240-255`; `engine/include/strata/core/bw_dense_defaults.hpp:18-19`）。`STRATA_MMVF_CHECK` の診断ログは上記のとおり終了時に出力されます。

`docs/DETAILS.md:1487` は V100/Titan V/Quadro GV100（sm_70）の既定値に `STRATA_SMALL_UNR=3` を掲載しています。`docs/DETAILS.md:1490` と `docs/DGX_SPARK_LINUX.md:124-126` は GB10（sm_121）では測定上 level または遅く既定から外すと記載し、コードの `kGb10SmallUnr = false` と整合します。これらの記述は資料上の測定・既定判断であり、本調査では測定を実行していません。

## 根拠

- `engine/src/kernels/cuda/native_bf16.cu:72-102,117-165,335-370` — bit 0 の効果、環境値判定、診断経路。
- `engine/src/kernels/cuda/verify_kernels.cu:112-135,1255-1293` — bit 1 の効果、環境値判定と呼び出し。
- `engine/include/strata/core/bw_dense_defaults.hpp:18-19`; `engine/include/strata/core/sm120_series.hpp:60-81,93-101`; `engine/include/strata/core/defaults_026.hpp:21-29` — sm_120/sm_121 の既定値規則。
- `engine/src/core/nv_defaults.cpp:136-163,222-255`; `engine/src/core/arch_defaults.cpp:28-66,95-105,302-332`; `engine/include/strata/core/gfx11_extra.hpp:39-73` — NVIDIA/AMD 世代別既定値と挿入・ログ。
- `engine/src/program/generate.cpp:4288-4320,4435-4449` — GPU 起動時の既定値適用位置。
- `docs/DETAILS.md:1484-1490`; `docs/DGX_SPARK_LINUX.md:119-126` — 資料に記載された世代別適用・測定判断。
