# `STRATA_GR_Q32_G`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP の fused hyper-connection read が Q8_0 up weights と Q8_1 出力を使う場合に、up kernel が warp ごとにまとめてロード・計算する行数 `G` を選びます。`G=1` は通常の 1 行ずつの処理、`2` / `4` / `8` はその行数をまとめてロードしてから計算します。カーネル内の各行の演算順序は変えず、ソースコメントは出力が bitwise 同一としています。CUDA と HIP gfx906 ではこの変数を読む分岐がコンパイルされません。

## 値と判定

値は `std::atoi` で変換され、変換後の値が `2`、`4`、`8` のときだけその値を使います。それ以外は `1` にフォールバックします。文字列全体の検証はありません。たとえば `2tail` や ` 2` は `atoi` の結果が `2` なら `G=2`、空文字・数字で始まらない値・`0`・負数は `G=1` です。

| 状況 | 選ばれる `G` |
|---|---:|
| 変数が未設定 | 通常 `1`。ただし下記の gfx12 既定値が適用される場合は `2` |
| `2` / `4` / `8` に `atoi` で変換される値 | 変換後の値 |
| 空文字、無効な文字列、`0`、その他の数値 | `1` |

HIP gfx12（gfx1200 / gfx1201）では、`STRATA_GFX12_DEFAULTS` が無効化しておらず `STRATA_DEFAULTS=026` でもない場合、Strata は unset の `STRATA_GR_Q32_G` に `"2"` を設定します。ユーザーが空文字を含む何らかの値を設定済みなら、その値を保持し、`atoi` による判定に進みます。gfx12 既定値が適用されない場合の unset 値は `1` です。

## 有効になる条件

- ビルドが HIP で、かつ `STRATA_HIP_GFX906` が定義されていないこと。`fused_gr.cu` は CUDA または HIP gfx906 で `STRATA_GR_FAST_BUILD=1` とし、`STRATA_GR_Q32_G` の読み取りと選択を含むコードを除外します。
- hyper-connection read が fused 経路を通ること。通常の `strata generate` では `--gr-native-mmvf`（または native preset が設定する同等の状態）が必要で、`--no-fused-gr`、GPU stage、layer/half dump、stage timing があると fused 経路を設定しません。形状が `fused_gr_supported()` の対象外でも使用されません。
- 選ばれた fused read の引数に Q8 down/up weights があり、Q8 分岐から `launch_q8_t()` に入り、さらに `q8_mixed` があり `STRATA_QFUSE_HC_LOCAL` が有効であること。このときだけ `gr_up_q8_q32_kernel` が起動し、`STRATA_GR_Q32_G` が使われます。`STRATA_QFUSE_HC_LOCAL` は未設定なら有効、設定時は `atoi(value) != 0` で判定されます。
- `STRATA_GR_Q32_PL` が `atoi(value) != 0` なら preload 版のテンプレートを選びます。この組み合わせでは `G=2` / `4` は同じ `G` の preload 版、その他（`G=1` / `8` を含む）は `G=1` の preload 版です。PL が無効なら `G=2` / `4` / `8` と `1` がそれぞれ対応する kernel variant を選びます。

Strata の `STRATA_HC_Q8` 要求は single-GPU の native dense 経路で hyper-connection weights を Q8_0 として扱う条件の一つです。Q8 weights のない read や Q8_1 出力を作らない read では、この変数の値が有効でも `G` の選択は実行されません。

## 実行時の詳細

HIP gfx12 の既定値は、`generate` 起動後、GPU の architecture を取得して `apply_arch_defaults()` を呼ぶ段階で適用されます。既存値を `getenv()` で調べ、unset の場合だけ設定します。POSIX では既定値を `setenv(..., 0)` で設定するため既存値を上書きせず、Windows 分岐でも `_putenv_s` を同じ unset 判定の後に呼びます。`STRATA_GFX12_DEFAULTS=0`（先頭文字判定）なら gfx12 table 全体を返さず、`STRATA_DEFAULTS=026` なら当該変数を含む decode 側の追加を行いません。

`G` は `launch_q8_t<T>()` 内の `static const int` で初回評価時に読み取られます。テンプレート引数 `T` ごとに初回評価結果を保持するため、その後の同じ specialization の呼び出しでは環境の変更は再評価されません。`G=2` / `4` / `8` のカーネルは複数行の weight・residual・norm 等をまとめてロードした後に行ごとの計算を行います。PL 版は次のグループを先読みします。`G` を認識したことを示す専用ログはありません。

gfx12 の既定値が設定された場合は、起動時の `strata: gfx12 (RDNA4): ... exact speed switches on by default ...` 一覧に `GR_Q32_G` が含まれます。Q8 kernel launch 後に `cudaGetLastError()` が失敗すると `fused_gr_read_multi q8: <エラー文字列>` を stderr に出して `exit(1)` します。値が未対応でも警告は出ず `G=1` を使います。

## 根拠

- `src/kernels/cuda/fused_gr.cu:38-43` — CUDA と HIP gfx906 を `STRATA_GR_FAST_BUILD` として扱い、後続の Q32 分岐をコンパイル対象外にする条件。
- `src/kernels/cuda/fused_gr.cu:2182-2201,2260-2304` — HIP Q8 up の Q32 kernel、`G` 行をまとめてロードする実装、PL 先読み、および演算が同じで bitwise 同一という実装注釈。
- `src/kernels/cuda/fused_gr.cu:2582-2606` — Q8 read からの kernel 選択、`atoi` の fallback と許可値、`STRATA_GR_Q32_PL` との組み合わせ。
- `src/kernels/cuda/fused_gr.cu:1536-1540,2824-2845` — `q8_mixed` / local QFUSE 条件、Q8 read の選択、launch error の stderr 出力と終了。
- `src/core/arch_defaults.cpp:27-61,185-190,221-229,257-265` — gfx12 既定値表、ユーザー値を保持する unset 判定、環境への設定と起動ログ。
- `src/program/generate.cpp:3702-3719,4951-4952` — HIP 起動時の architecture 既定値適用と fused hyper-connection の CLI 条件。
- `src/program/generate.cpp:4806-4809` — single-GPU native dense で `STRATA_HC_Q8` が hyper-connection weights の Q8_0 化に関与する条件。
- `src/core/layer.cpp:1491-1492` — fused read の形状条件。

同名のその他の参照は `src/core/arch_defaults_test.cpp:289,296,445-446` の既定値表テストで、実行時動作の根拠にはしていません。`docs/envvars/000_envvers.md` に候補名があります（同索引は今回変更していません）。`docs/DETAILS.md` にはこの変数名の直接の記載が見つからず、値の意味は実装から記述しました。
