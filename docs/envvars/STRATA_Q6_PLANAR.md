# `STRATA_Q6_PLANAR`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。Strata 所有のソースを対象とし、外部ライブラリの環境変数動作は含めない。

## 役割

SYCL backend の Q6_K 出力ヘッドを、GGUF のブロック配置から ql / qh / scales / d の平面配置へロード時に変換し、decode の行列ベクトル積で平面向けカーネルを使います。通常の Q6_K 重みと平面配置の重みは同じデータで、変換に成功すると元の device allocation を解放して置き換えます。適用先は NativeHead の出力ヘッドと、条件を満たす MTP draft head です。

## 値と判定

環境変数を文字列として厳密に比較します。数値 parse や空白除去はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効 |
| 文字列全体が `0` | 無効 |
| その他すべて（例: `1`, `false`, `0 `, `00`） | 有効 |

判定結果は `native_q6_k_planar_enabled()` の関数内 `static const bool` に保存されます。初回呼び出し時に一度だけ評価されるため、その後プロセス内で環境値を変更しても反映されません。NativeHead と MTP のロード経路で参照されます。

## 有効になる条件

- SYCL backend のコードで使われます。調査した参照は `sycl/` 配下にあり、CUDA/HIP backend でこの変数を読む実装はありません。
- 対象は Q6_K（型 ID 14）の出力ヘッドです。入力次元は正で256の倍数、出力次元は正である必要があります。
- `STRATA_Q6_PACKED` が有効な出力ヘッドでは、packed 形式が優先され、planar 化は呼び出されません。Q6_PACKED 側も関数内 static 判定で、文字列全体が `1` の場合だけ有効です。
- 適格な形状でも平面配置用 device memory の確保に失敗した場合は変換せず、元の GGUF 配置を維持します。

MTP draft vocabulary の部分ヘッドでは、元の出力ヘッドが planar 登録済みなら、選択行を planar 配置のまま gather します。そうでなければ、Q6_K かつ Q6_PACKED が無効で、planar が有効な場合に draft head 自身の変換を試みます。

## 実行時の詳細

`native_q6_k_planar_adopt()` は無効ポインタ、無効な次元、256で割り切れない入力次元、無効設定、既登録ポインタの場合は入力ポインタをそのまま返します。その他の場合、ブロックごとに ql / qh / scale / d の平面を作る device kernel を実行して待機し、成功後に元の allocation を解放して新しいポインタを registry に登録します。変換されたポインタと行列形状が registry に一致すると、`native_q6_k_mmvq()` は通常の Q6_K dispatch より先に planar MMVQ kernel を使います。registry にないポインタや形状不一致では planar 経路を使いません。

確保失敗時は stderr に `strata: STRATA_Q6_PLANAR: no VRAM for the %s's planar copy (+%.1f MiB), keeping the GGUF layout` を出します。成功時は `strata: STRATA_Q6_PLANAR: the %s (%d x %d) is stored as 16-byte-aligned planes (same bytes)` を出します。SYCL 変換例外は `strata: STRATA_Q6_PLANAR conversion failed: %s`、MTP の部分 gather 例外は `strata: STRATA_Q6_PLANAR gather failed: %s` と stderr に出し、変換失敗時は呼び出し元が既存配置を使えるように戻ります。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3062-3068`: unset と文字列全体 `0` の判定、static cache。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3075-3115`: 適格条件、allocation、変換、元 allocation の解放、registry 登録、失敗時 fallback とログ。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2970-2998,3810-3814`: registry に基づく planar MMVQ dispatch。
- `sycl/src/core/native_head.cpp:91-96`: Q6_K output head での packed 優先と planar adopt。
- `sycl/src/core/mtp.cpp:762-787`: planar head からの部分 gather、および draft head の条件付き planar 化。
- `sycl/include/strata/kernels/native_mmvq.hpp:118-127`: planar 配置の説明と helper 宣言。
- `docs/INTEL.md:491-500`: B70 での記載測定。文書は 2560x248320 の MMVQ が1列 800→662 µs、4列 1230→1020 µs、同資料記載の end-to-end decode が 33.16→33.25 tok/s と報告しています。これは同資料の特定条件での記録であり、ここでは独立測定していません。
