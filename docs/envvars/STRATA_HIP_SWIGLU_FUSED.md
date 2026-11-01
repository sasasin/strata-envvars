# `STRATA_HIP_SWIGLU_FUSED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `## main...origin/main` で、`git status --short` に変更はありませんでした。

## 役割

gfx906 HIP ビルドの grouped expert 計算で、SwiGLU 活性化と q8_1 量子化を別々のカーネルで行う既定経路から、両方を一つのカーネルで行う経路へ切り替えます。切り替えを読むのは `src/kernels/cuda/iq_kernels.cu` の `native_expert_grouped()` です。同ファイルは gfx906 向け HIP 互換ビルドに含まれます（`CMakeLists.txt:81-92,190-207,490-503`）。

## 値と判定

`env_on()` は `std::getenv()` の戻り値が null でなく、先頭文字が NUL と `'0'` のどちらでもないときだけ true を返します。文字列全体の parse や数値変換はしません（`src/kernels/cuda/iq_kernels.cu:3395-3398`）。

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | false | fused 経路を要求しない |
| 空文字 | false | fused 経路を要求しない |
| `0`、`0anything` | false | fused 経路を要求しない |
| `1`、`2`、`false`、`-1`、先頭が空白の文字列 | true | fused 経路を要求する |

大文字小文字や後続文字は検査されません。先頭文字が `'0'` なら後続に何があっても false、それ以外の非空文字列は true です。無効値エラーや値の clamp はありません。

## 有効になる条件

- `STRATA_HIP_GFX906` を定義した gfx906 向け HIP 互換ビルドでのみ、この環境変数を使う分岐がコンパイルされます。通常の CUDA ビルドと、別 backend の wave32 HIP ビルドではこの分岐はありません（`CMakeLists.txt:81-93,190-207`）。
- `native_expert_grouped()` が呼ばれ、容量チェックなどの早期 return を通過する必要があります。同関数は grouped expert の gate/up 計算後に SwiGLU/q8_1 処理へ進みます（`src/kernels/cuda/iq_kernels.cu:6246-6257,6420-6441`）。
- `native_grouped_set_v1(true)` または `STRATA_GROUPED_V1` が有効にした `v1` モードでは、`sw_v1 = v1 || !sw_fused` となるため、この変数が true でも別カーネル経路になります。`g_grouped_v1` は起動時に `STRATA_GROUPED_V1` から初期化され、API から変更できます（`src/kernels/cuda/iq_kernels.cu:6210-6214,6323-6327,6423-6429`）。
- `L.had_block > 0` のレイアウトでは、fused 指定があっても SwiGLU 後の float 値に Hadamard 変換を行う必要があるため、別カーネル経路を使います（`src/kernels/cuda/iq_kernels.cu:6431-6439`）。

CLI 引数、設定ファイル、別の環境変数が `STRATA_HIP_SWIGLU_FUSED` の値を上書きする処理は見つかりません。`STRATA_GROUPED_V1` と `native_grouped_set_v1()` は上記のとおり fused 経路を抑止できます。

## 実行時の詳細

変数は `native_expert_grouped()` 内の `static const bool sw_fused` 初期化で読みます。したがって初めてこのコード位置に到達した時点の値がプロセス内にキャッシュされ、その後の環境変更は再評価されません。容量チェックによる早期 return などでまだ初期化されていない場合は、最初に分岐へ到達した呼び出しで読みます（`src/kernels/cuda/iq_kernels.cu:6246-6251,6423-6429`）。

fused 経路では `swiglu_q8_1_entries_kernel` が SwiGLU の積を作り、同じカーネル内で `q8_1_store()` を呼びます。従来経路は `swiglu_entries_kernel` で float の活性値を作り、続けて `quantize_q8_1_kernel` で量子化します（`src/kernels/cuda/iq_kernels.cu:2818-2849,6431-6441`）。対象領域は呼び出し内の expert entries です。Strata のソースコメントは fused 計算結果が従来経路と bitwise 同じになる意図を記しています（`src/kernels/cuda/iq_kernels.cu:2824-2830`）。

この変数に対する専用ログや警告、無効値時の終了処理はありません。両経路とも処理後に `check("native_expert_grouped/swiglu")` を呼びます（`src/kernels/cuda/iq_kernels.cu:6441`）。

SYCL の移植ファイルにも同名の読み取り分岐があります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5693-5705`）。ただし調査対象 commit の `sycl/CMakeLists.txt` は `STRATA_HIP_GFX906` を定義しておらず、通常の SYCL ビルド設定ではこの `#if defined(STRATA_HIP_GFX906)` 節は有効になりません（`sycl/CMakeLists.txt:21-44`）。

## 根拠

- 候補一覧での掲載: `docs/envvars/000_envvers.md:907`。
- 環境値の読み取りと判定: `src/kernels/cuda/iq_kernels.cu:3395-3398,6423-6429`。
- gfx906 ビルド条件と対象ソース: `CMakeLists.txt:81-93,190-207,490-503`。
- v1 の既定値と変更 API: `src/kernels/cuda/iq_kernels.cu:6210-6214,6323-6327`。
- fused / separate の dispatch と Hadamard 条件: `src/kernels/cuda/iq_kernels.cu:6431-6441`。
- fused kernel と量子化処理: `src/kernels/cuda/iq_kernels.cu:2818-2849`。
- SYCL 側の同名分岐とビルド定義: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5693-5705`, `sycl/CMakeLists.txt:21-44`。
