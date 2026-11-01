# `STRATA_NO_SUB16_GU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA/HIP の量子化 expert grouped kernel で gate/up と down に使う sub-warp 行 kernel を選ばず、multi-entry の全 warp 行 kernel を選ぶための診断・kernel 選択用スイッチです。名前に `GU` とありますが、CUDA/HIP では down 側の sub-warp kernel や複数の専用最適化の選択にも使われます。通常の dense 行列演算すべてを切り替える設定ではありません。

実験的 SYCL 実装にも同名の読み取りがありますが、そこで gate/up の sub-16 行 kernel は起動経路から呼ばれず、変数が直接変えるのは主に `n_ff == 640` の down grid の行幅です。根拠は CUDA/HIP 実装の `src/kernels/cuda/iq_kernels.cu:3395-3401,4195-4225,4276-4291,6323-6327,6443-6447` と SYCL 実装の `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3200-3211,4571-4606,4622-4634,5761-5764`。

## 値と判定

CUDA/HIP と SYCL の `env_on()` は `std::getenv()` の結果を読み、値全体の parse はせず、値が存在し、空文字でなく、先頭文字が `0` でなければ true とします。

| 環境変数の値 | 判定 |
|---|---|
| 未設定 | false |
| 空文字 | false |
| `0`, `0anything` | false |
| `1`, `2`, `true`, `false`, `anything` | true（先頭が `0` 以外かつ空でない場合） |

空白除去、数値変換、大文字小文字の正規化はありません。例えば `false` も有効扱いです。既定値は無効で、同じ名前の CLI 引数や設定ファイルによる上書きはこの実装にはありません。根拠: `src/kernels/cuda/iq_kernels.cu:3395-3401`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3200-3211`。

## 有効になる条件

### CUDA/HIP

環境値が true でも、対象処理が `native_expert_grouped()` 内の該当 kernel 経路を通る場合に限って効果があります。

- split 形式の gate/up multi kernel では template 引数 `SUB16=false` を選びます。既定の `SUB16=true` 経路は `n_embd == 2560` かつ1行あたりの dot 数が80の場合に16 lane行を使います。環境変数を有効にすると同じ multi kernel の全 warp 行経路を使います。split でない形式や `STRATA_OLD_IQ_MMVQ` 経路ではこの選択になりません（`src/kernels/cuda/iq_kernels.cu:1958-1964,2010-2015,4195-4225`）。
- down multi kernel でも `SUB_DOWN=false` を選ぶ分岐があります。また `n_ff == 640` の down grid を通常の8行単位にし、既定で選ばれる型別の32行または16行単位を使わなくします（`src/kernels/cuda/iq_kernels.cu:2222-2229,4282-4290,6443-6447`）。
- この設定は `tq_sub8_on()` を無効にし、TQ trellis の特別な8-lane down 行経路も抑制します（`src/kernels/cuda/iq_kernels.cu:3456-3467,6443-6447`）。`STRATA_DOWN_WS` が有効でも、この変数が true なら down shared-memory 専用経路は使われません（`src/kernels/cuda/iq_kernels.cu:4568-4579`）。
- `STRATA_GU_SWIGLU` の融合 gate/up + SwiGLU 経路は `g_no_sub16_gu` が true の場合に拒否され、通常の gate/up 経路へ進みます（`src/kernels/cuda/iq_kernels.cu:4251-4262,6353-6367`）。

通常の `STRATA_EXPERT_V2` 対象経路は `native_expert_grouped()` 内で早期 return し、`STRATA_EXPERT_V2K` 対象経路も早期 return するため、そこでは本変数が gate/up kernel 選択に介入しません（`src/kernels/cuda/iq_kernels.cu:6265-6279,6280-6321`）。`STRATA_EXPDEC` による専用 gate/up/down kernel が対象層で選択された場合も、通常の `launch_gu` / `launch_down` 分岐を通らない部分には適用されません（`src/kernels/cuda/iq_kernels.cu:6410-6415,6484-6489`）。

### SYCL

SYCL の `launch_gu_multi()` は `native_gu_multi_kernel<..., false>` を常に呼び、sub-16 gate/up kernel を起動しません。そのため `STRATA_NO_SUB16_GU` は gate/up の sub-16 可否を変えません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4571-4606`）。SYCL の `native_expert_grouped()` では、旧 kernel が無効かつ `L.n_ff == 640` の場合、環境変数が false なら down の `d_rows` は型に応じて32または16（それ以外は8）、true なら8になります。これが `gd` の行方向 grid を変えます。条件外ではどちらの場合も8で、この計算による差はありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5761-5795`）。

## 実行時の詳細

各 backend の `g_no_sub16_gu` は translation unit の namespace-scope 初期化時に一度 `env_on()` で設定される通常の global bool です。リクエストごとに環境を再読せず、起動後にプロセス環境を変更してもこの bool には反映されません。CUDA/HIP では同値を kernel 選択、row grid と他の専用経路の条件に使い、SYCL では down grid の行幅条件に使います。別の CLI 優先順位や fallback 値の変換処理はありません。

通常の grouped kernel 選択では、この変数自体を理由としたログ、警告、終了処理は見つかりません。選択後に実行される kernel launch の通常の `check()` は CUDA/HIP 側 `src/kernels/cuda/iq_kernels.cu:6420,6490`、SYCL 側 `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5759,5793-5795` にあります。

同梱の CUDA `expdec_bench` は別途この名前を直接 `getenv()` で調べます。値が設定済み・空でなく・先頭が `0` 以外なら `# warning: STRATA_NO_SUB16_GU is set, the kernel choice is bypassed` を stdout に出します。これは benchmark 内の警告であり、通常の Strata 起動時ログではありません（`src/kernels/expdec_bench.cpp:425-429`）。

## 根拠

- 候補一覧の `STRATA_NO_SUB16_GU` は grep 候補として記載されています（環境変数調査リポジトリ `docs/envvars/000_envvers.md:1157`）。実際の読み取りは CUDA/HIP と SYCL の `env_on("STRATA_NO_SUB16_GU")`、および `expdec_bench` の直接 `getenv()` で確認しました。
- `CMakeLists.txt:502` は `src/kernels/cuda/iq_kernels.cu` を GPU kernel target に含め、`CMakeLists.txt:14-20` は SYCL backend を別構成として `sycl/` から追加します。
- `CMakeLists.txt:1258-1266` は `iq_multi_parity_kq_nosub16` を `STRATA_KQ_SPLIT=1;STRATA_NO_SUB16_GU=1` で実行する設定を持ちます。これはテストの構成であり、本番動作の根拠は上記 kernel 分岐です。
- `docs/DETAILS.md` に本変数の説明や測定値は見つかりませんでした。したがって性能向上・数値的一致などはこの文書では主張しません。
