# `STRATA_GDN_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の GDN（gated DeltaNet）prefill recurrence で、`T >= 128` の入力に tensor-core を使う chunked scan を自動選択するスイッチ。`T` が短い場合、GPU 条件を満たさない場合、または scratch を確保できない場合はこの実装を使わず、他の recurrence kernel に進む。HIP / Metal の実装にはこの読み取り分岐がない。実装は `engine/src/prefill/kernels.cu` の `gdn_recurrence_impl` と `gdn_rec_tc`。

## 値と判定

CUDA の dispatch では `std::getenv` が返す文字列に `std::atoi` を適用し、結果が 0 以外なら有効とする。文字列全体の検証や `true` / `false` の特別扱いはない。したがって `1`、`-1`、`+1tail` は有効、未設定・空文字・`0`・`0anything`・`true`・数字で始まらない文字列は無効（`atoi` が 0 を返す）。先頭の空白と符号は `atoi` の規則で処理され、後続の非数字は数値変換後に無視される。読み取りは `static const bool` に保存される（`engine/src/prefill/kernels.cu:3186-3189`）。

| 条件 | 未設定時 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| 非 Windows の CUDA ビルドで generate の起動処理を通る場合 | 起動時に `STRATA_GDN_TC=1` を設定する | 既存値は変更しない。`atoi` が非 0 なら有効 | 空文字を含め、設定値をそのまま保持し、`atoi` が 0 なら無効 |
| Windows CUDA、または起動時の既定値設定を通らないプロセス | dispatch の parse 結果は無効 | `atoi` が非 0 なら有効 | `atoi` が 0 なら無効 |
| HIP / Metal | 当該変数を読む CUDA dispatch はない | 対象外 | 対象外 |

非 Windows CUDA の既定値設定は `generate.cpp` のコンパイル条件内で `apply_gdn_defaults_cuda(true)` を呼び、engine プロセスの環境変数が **存在すれば値にかかわらず** 上書きしない。このため明示した空文字も既定値 `1` に置き換わらず、dispatch では無効になる。`strata launch --set STRATA_GDN_TC=VALUE` は run config の env に値を置き、起動時にその env が親プロセス環境へ重ねられるので、engine の既定値設定より優先される。設定値がない場合は親プロセスから継承し、それもなければ非 Windows CUDA の engine が `1` を設定する。直接起動する engine に `STRATA_GDN_TC` 専用 CLI option はない（`terminal/strata_cli/launch/cmd.py:124-125`、`terminal/strata_cli/launch/runner.py:757-762`、`terminal/serve/server.py:3870-3891`、`engine/src/program/generate.cpp:4405-4409`）。

## 有効になる条件

- CUDA の recurrence dispatch に入ること。`STRATA_GDN_TC` の読み取りは `#if !defined(__HIPCC__)` の範囲にあり、HIP 経路にはない（`engine/src/prefill/kernels.cu:3177-3189`）。
- `T >= 128` であること。`T < 128` では tensor-core scan を試さず、通常の fallback に進む（`engine/src/prefill/kernels.cu:992, 3227-3229`）。
- 通常の自動 dispatch では、CUDA device の compute capability major が 8 以上、SM 数が value head 数 `HV`（このモデル形状では 48）以上で、scan に必要な shared memory があること。属性取得に失敗した場合も unsupported として扱う（`engine/src/prefill/kernels.cu:1365-1382`）。完全プランは 124,944 bytes/block を必要とする。完全プランに失敗すると分割プランも試し、こちらは 97,808 bytes（出力 norm を融合する場合は 98,832 bytes）を必要とする（`engine/src/prefill/gdn_tc.cuh:42-55`）。
- per-device scratch を確保できること。初回使用時に最大約 60.3 MB を `cudaMalloc` し、device ごとの static pointer に保持する。確保失敗時は通常の自動 dispatch では次の経路に進む（`engine/src/prefill/gdn_tc.cuh:57-90`、`engine/src/prefill/kernels.cu:1383-1384, 3227-3237`）。
- `STRATA_GDN_TC=0` など parse 結果が 0 の場合でも recurrence 自体は実行される。`STRATA_GDN_CHUNKED` が非 0 で `T >= 128` なら次に FP32 chunked scan を試し、それも選ばれなければ `STRATA_GDN_PIPELINE` と key-head kernel の適用条件に従って通常 kernel に進む（`engine/src/prefill/kernels.cu:3180-3185, 3239-3255`）。
- 分割 tensor-core scan の設定は別環境変数にも依存する。`STRATA_GDN_TC_TILES` は `1` / `2` 相当または自動選択（SM 数に応じて 2 tiles）を指定し、`STRATA_GDN_TC_FUSE=0` は分割 scan 内の出力 norm 融合を無効にする。分割経路の `STRATA_GDN_TC_NP` は `1` または `2` 以外を 3 に戻す（`engine/src/prefill/kernels.cu:1339-1355, 3198-3202, 3233-3236`）。
- CUDA の診断用 `GdnProbe` が force 指定を持つ場合は環境変数による通常の自動 dispatch ではなく指定経路を試す。これは harness / probe 用の経路である（`engine/src/prefill/kernels.cu:3190-3209`）。

## 実行時の詳細

起動時に既定値を設定する処理は、HIP・gfx906・Metal・Windows を除く CUDA コンパイル経路で呼ばれ、engine の switch 読み取りより前に環境へ `1` を加える。環境変数がすでに設定されていれば、ユーザー値を保持する（`engine/src/program/generate.cpp:4405-4409`、`engine/src/core/arch_defaults.cpp:263-275`）。

dispatch の `static const bool tc` は、CUDA recurrence が先行条件を通って自動 dispatch 部分に初めて到達した時に評価され、そのプロセス内で cache される。初回評価後の環境変更は反映されない。通常経路では `T >= 128` かつ `tc` が true のとき full tensor-core scan を試す。full plan が使えなければ split scan を試し、どちらも成功しなければ `STRATA_GDN_CHUNKED`、key-head、pipeline / column recurrence の順に fallback する。tensor-core recurrence は状態と出力を更新する。scan は FP16 の hi/lo operands と FP32 accumulation を使うため、通常の FP32 kernel と出力が丸めの範囲で異なりうる（`engine/src/prefill/kernels.cu:3186-3189, 3227-3255`、`engine/src/prefill/gdn_tc.cuh:11-24`）。

この自動選択を行わない経路は、`T <= 0`、`variant == 2`、または `serial && with_out` の条件で先に fused kernel を選ぶ場合。state-only 呼び出しは `with_out=false` であり、上記の `serial && with_out` 条件には該当しない（`engine/src/prefill/kernels.cu:3075-3079, 3177-3189, 3273-3276, 3301-3306`）。

## ログと測定値

通常の自動 dispatch は tensor-core の選択理由や fallback 理由をログに出さない。probe がある場合だけ選択経路や理由を probe state に記録する。実行後の CUDA エラーは `check("gdn_recurrence")` が拾い、通常は stderr に `prefill gdn_recurrence: <CUDA error>` を出して終了コード 1、serve mode では追加で stderr に `strata serve: fatal GPU error (...)`、stdout に `ERR fatal GPU error: ...` を出して終了コード 3 で終了する（`engine/src/prefill/kernels.cu:3259-3271`、`engine/include/strata/core/device_error_exit.hpp:25-33`）。適格性不足や scratch 失敗は自動経路で fallback するため、それ自体ではエラー終了しない。

`docs/DETAILS.md:1784-1803` は、変更作者による CMP 170HX（GA100、70 SMs）、Qwen3.8-Flash-Next IQ3_S native pack の報告として、約 3.3K prompt の recurrence が 105 ms から 34 ms、prompt が 4K / 16K / 52K でそれぞれ +3.9% / +6.0% / +6.7% と記載する。同資料は測定を本リポジトリの著者が行ったものではないと明記している。20 prompts の teacher-forced 比較は mean KL 0.0157、top-1 agreement 100% と報告されている。これらは資料上の報告値であり、本調査で再測定していない。

## 根拠

- 環境値の parse、CUDA 自動 dispatch、fallback: `engine/src/prefill/kernels.cu:3182-3189, 3227-3271`
- 起動時の既定値と既存値の保持: `engine/src/program/generate.cpp:4405-4409`、`engine/src/core/arch_defaults.cpp:263-275`
- 入力長しきい値、tensor-core eligibility、scratch 初期化: `engine/src/prefill/kernels.cu:992, 1365-1384`、`engine/src/prefill/gdn_tc.cuh:42-55, 57-90`
- probe 用の選択理由: `engine/src/prefill/kernels.cu:3190-3202, 3259-3261`
- CUDA エラーの観測方法: `engine/src/prefill/kernels.cu:110-116, 3271`、`engine/include/strata/core/device_error_exit.hpp:25-33`
- 資料記載の数値: `docs/DETAILS.md:1784-1803`
