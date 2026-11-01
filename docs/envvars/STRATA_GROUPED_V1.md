# `STRATA_GROUPED_V1`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリは調査開始時点で `main...origin/main`、未コミット変更なし。

## 役割

CUDA/HIP および SYCL の native grouped expert GPU kernel で、旧 grouped 実行方式を選びます。通常方式では、呼び出し側が `grid_groups` で指定した少数 group だけを並列 grid に出し、SwiGLU と q8_1 量子化を一つの kernel にまとめます。この変数を有効にすると、group grid を `cap_groups` 全体にし、SwiGLU と q8_1 量子化を別々の kernel にします。旧方式と通常方式の結果は同一になるよう実装されており、header は bitwise 同一と説明しています。

主な利用経路は `native_expert_grouped()` です。verify window の PCIe expert 呼び出しなど、実際にある group が `cap_groups` より少ない呼び出しで grid の形を変えます。対象外の CPU expert 経路ではこの変数を読みません。

## 値と判定

CUDA/HIP 実装と SYCL 実装の `env_on()` は `std::getenv()` の結果について、未設定でなく、先頭文字が NUL でも `'0'` でもない場合に true を返します。数値変換や文字列全体の比較はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0anything` | 無効（先頭が `'0'`） |
| `1`、`true`、`false`、`2x`、先頭が空白の文字列 | 有効（非空で先頭が `'0'` 以外） |

値の fallback、範囲制限、警告ログはありません。CLI 引数や別の環境変数による本番時の優先順位もありません。parity 用の `native_grouped_set_v1(bool)` は内部状態を書き換えますが、呼び出しは parity プログラムに限られます。

## 有効になる条件

- CUDA/HIP では `src/kernels/cuda/iq_kernels.cu`、SYCL では対応する `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の grouped expert GPU 実装が使われること。CPU の `native_expert_grouped` 相当処理や Metal 経路でこの名前は参照されません。
- `native_expert_grouped()` が呼ばれ、通常の gate/up および down kernel 経路へ進むこと。CUDA の `STRATA_EXPERT_V2` / `STRATA_EXPERT_V2K` 専用経路は関数冒頭で別 kernel を起動して return するため、そこで `g_grouped_v1` による grid・SwiGLU 分岐の効果はありません。
- `grid_groups` が `1..cap_groups-1` なら、有効時は `gy=cap_groups`、無効時は `gy=grid_groups` です。`grid_groups<=0` または `grid_groups>cap_groups` なら両方とも `cap_groups` です。

`STRATA_EXP_LAYOUTS` の特殊 layout、4-bit nibble kernel、EXPDEC などの選択は引き続き別条件で行われます。そこでも `gy` を使う通常の launch は grid の変更対象ですが、特殊実装が明示的に `cap_groups` を使う部分はこの変数でさらに変わりません。CUDA の fused gate/up layout は独立した分岐なので、この変数が gate/up kernel 自体を常に旧版へ戻すわけではありません。

HIP gfx906 では `STRATA_HIP_SWIGLU_FUSED` も相互作用します。fused SwiGLU が選ばれていれば、この変数が有効な場合は `sw_v1` が true となり別々の SwiGLU・量子化 kernel に戻します。fused SwiGLU が選ばれていない場合は、無効時も同じ別 kernel 経路です。

## 実行時の詳細

値は kernel ソース内の namespace-scope `g_grouped_v1` 初期化時に一度読み取られます。プロセス起動後に環境値を変更しても再評価されません。CLI やサーバーのリクエストごとに読む処理ではありません。

通常経路では `gy` を gate/up grid と down grid の group 次元に渡します。無効時に `grid_groups` が小さければ少数 group を起動し、各 block row が残りの group を stride して扱います。有効時は `gy` を `cap_groups` に固定し、group ごとに block row を配置します。続く SwiGLU/量子化は、旧方式では `swiglu_entries_kernel` と `quantize_q8_1_kernel` の二段、新方式では `swiglu_q8_1_entries_kernel` の一段です。CUDA の `L.had_block > 0` の場合は必要な Hadamard 変換のため、環境値にかかわらず float 中間値を作る別段経路になります。

有効・無効を示す専用ログはありません。CUDA の kernel launch 後にエラーがあれば `check()` が `stderr` に `<kernel名>: <CUDA error string>` を出し `exit(1)` します。SYCL 側の `check()` は移植コード上、CUDA error code の置き換え値を確認するだけで、変数固有のログはありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3395-3398`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3200-3203`: 未設定・空文字・先頭 `'0'` の判定。それぞれ `6211`、`5604` で起動時に状態を初期化。
- `src/kernels/cuda/iq_kernels.cu:6246-6258,6267-6324`: early return する V2/V2K 経路、通常経路の `v1` と `gy`。
- `src/kernels/cuda/iq_kernels.cu:6353-6368,6423-6442,6444-6447`: fused gate/up との独立、fused SwiGLU の条件、SwiGLU/量子化 kernel の分岐と group grid。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5609-5636,5696-5708,5742-5759,5761-5764`: SYCL の grouped kernel、`gy`、SwiGLU/量子化の分岐。
- `include/strata/kernels/iq_kernels.hpp:79-92`: `grid_groups` の意味、旧方式が block row を group ごとに置くこと、結果同一との注記、setter の宣言。
- `src/core/verify.cpp:2217-2221,2234-2236`: verify window で group 数 `gy` を決め、native kernel に渡す呼び出し。
- `src/kernels/cuda/iq_kernels.cu:38-40`: CUDA の launch error のログと終了処理。parity 用 setter の呼び出しは `src/kernels/native_grouped_parity.cpp:194-200,277-289`、`src/kernels/iq_nibble_parity.cpp:668-696`、`sycl/src/kernels/native_grouped_parity.cpp:260-276` にあり、製品経路での setter 呼び出しはありません。
- `CMakeLists.txt:80-95` と `sycl/CMakeLists.txt:1-5`: CUDA/HIP と SYCL が別の backend 実装であること。
