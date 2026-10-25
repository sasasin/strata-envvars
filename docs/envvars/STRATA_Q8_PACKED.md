# `STRATA_Q8_PACKED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

ネイティブ密行列 (`NativeDense`) がロードする一部の Q8_0 重みについて、decode 用の packed copy を追加で作ります。元の GGUF 配置の重みは残し、prompt 側の GEMM は元の copy を使います。登録済みの重みを native MMVQ で decode するときは packed copy を使い、条件に合わない呼び出しは通常の Q8_0 MMVQ に進みます。通常の pack / arena に入った重み全般を切り替える設定ではありません。

## 値と判定

値は文字列全体で判定され、`std::getenv()` の結果がちょうど `"1"` の場合だけ有効です。数値変換や trim、大文字小文字変換はしません。

| 状態 | 判定 |
|---|---|
| 未設定 | 通常は無効。gfx1151 では後述の起動時既定値が適用される場合がある |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`01`、`1 `、`1anything`、`true` | 無効 |

判定結果は `native_q8_0_packed_enabled()` の関数内 `static const bool` に初回呼び出し時に保存されます。最初の判定後にプロセス環境を書き換えても、そのプロセス内では再評価されません。

根拠: `src/kernels/cuda/native_mmvq.cu:1945-1951`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2726-2732`。

## 有効になる条件

- ネイティブ密行列のロードが実行されること。通常の `strata generate` では `--native-dense-gguf` で指定した GGUF が対象です。multi-GPU の各 stage にも同じ条件でロード箇所があります (`src/program/generate.cpp:1916,3066-3070,3465-3468`)。CLI の native 設定から同オプションに GGUF shard が渡される場合もあります。
- 読み込む tensor が型 Q8_0 (`tensor.type == 8`) で、名前が `blk.1.ple_key.weight` ではないこと。PLE key は専用 kernel があるため除外されます。
- 行列形状が `1024 <= n_in <= 4096`、`n_out >= 2048` であること。カーネル側の条件は `n_in > 0`、32 の倍数、`n_in / 32 >= 32`、`n_in <= 4096`、`n_out >= 2048` です。
- multi-column の呼び出し (`ncols > 1`) では `g_multi_exact` も有効であること。登録があっても exact layout が使えない場合、packed kernel は選ばれません。

gfx1151 (Strix Halo) では、HIP ビルドの起動時に GPU 0 の arch を取得できれば `apply_arch_defaults()` が呼ばれ、既定スイッチ表が適用されます。表は `STRATA_Q8_PACKED=1` を含みます。`STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら表全体を止めます。`STRATA_Q8_PACKED` 自体が何らかの値で設定済みなら、値が `1` 以外でもユーザー設定として保持されるため、packed 機能は有効になりません。gfx12 の既定表にはこの変数がなく、他 arch や CUDA ビルドにも gfx1151 の既定設定は適用されません。

根拠: `src/core/arch_defaults.cpp:32-35,45-47,61-70`、`src/program/generate.cpp:2190-2196`。既定表の適用条件と記述は `docs/STRIX_HALO.md:83-96` とも一致します。

## 実行時の詳細

`NativeDense::load()` は通常の device copy を作った後、上記条件を満たす matrix についてだけ GGUF の Q8_0 block を host 側で packed plane に並べ直し、同サイズの追加 device allocation に転送します。値の再量子化は行わず、Q8 の `qs` と各 block の fp16 scale `d` を別 plane に置きます。成功した copy は元の GGUF 配置 device pointer を key に registry へ登録されます。適格 tensor が複数あれば、該当するものごとに追加 allocation が作られます。

decode 時は `native_q8_0_mmvq()` が registry と形状を確認し、対象があれば packed kernel を launch します。kernel は 1〜8 列に対応します。registry にない重み、形状不一致、multi-column で `g_multi_exact` が無効などの場合は packed 経路から戻り、通常の Q8_0 MMVQ に fallback します。CUDA 実装では fallback は `small_mmvq`、SYCL port では `try_wide32` を試してから `small_mmvq` に進みます。

packed copy の確保または転送が失敗すると `NativeDense::load()` は失敗し、`strata generate` は native dense projections のエラーを stderr に出して終了コード 1 を返します。1 個以上の copy を作成した場合は stderr に `native dense: STRATA_Q8_PACKED=1 packed %zu Q8_0 matrices for decode (+%.1f MiB)` の形式で個数と追加量を表示します。対象 tensor がなければこのログは出ません。

実装コメントと公開 header は packed kernel の出力が元の GGUF 配置の kernel と bitwise equal である設計を記載しています。これはソースコメント上の説明であり、この調査では build や実機測定をしていません。性能値は記載しません。

根拠: `src/core/native_dense.cpp:190-198,302-321,350-375`、`src/kernels/cuda/native_mmvq.cu:1684-1696,1783-1806,1945-1955,1969-1978,2443-2447`、`sycl/src/core/native_dense.cpp:277-316,381-401`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2496-2519,2726-2736,3628-3633`、`include/strata/kernels/native_mmvq.hpp:93-104`。

## 根拠

- 環境値の読み取りと exact string 判定: `src/kernels/cuda/native_mmvq.cu:1945-1951`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2726-2732`。
- 形状条件と packed registry の参照: `src/kernels/cuda/native_mmvq.cu:1783-1806,1953-1955`。
- GGUF matrix の選択、pack、追加 allocation と登録: `src/core/native_dense.cpp:302-321,357-375`。
- gfx1151 の既定値、ユーザー値優先、既定値を設定した旨の stderr ログ: `src/core/arch_defaults.cpp:32-35,45-47,61-80`、呼び出し位置 `src/program/generate.cpp:2190-2196`。
- Strix Halo の既定スイッチ表の説明: `docs/STRIX_HALO.md:83-96`。
