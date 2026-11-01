# `STRATA_GDN_TC_FUSE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の prompt GDN（gated DeltaNet）Tensor Core **分割 scan** が、出力正規化も同じ kernel 内で行うかを選びます。融合可能な条件では、既定で scan に正規化を含めます。`STRATA_GDN_TC_FUSE=0` など `atoi` の結果が 0 になる設定では scan の後に別の `gdn_out_norm_kernel` を実行します。Tensor Core 経路そのものを有効にするスイッチではありません。

## 値と判定

`std::getenv` の結果を `std::atoi(v) != 0` で判定し、その結果を関数内の `static const bool` に保存します（`src/prefill/kernels.cu:2998-2999`）。したがって数値全体の厳密な検証はなく、`atoi` が先頭の空白と符号の後から読む十進数の接頭辞で判定します。変換できる数字がない文字列は 0 になります。

| 環境値 | `tc_fuse` | 意味（分割 scan が使われる場合） |
|---|---:|---|
| 未設定 | true | scan 内で出力正規化を行える条件なら融合する |
| 空文字 | false | scan 後に正規化 kernel を実行 |
| `0`、`0suffix`、`false`、数字で始まらない文字列 | false | scan 後に正規化 kernel を実行 |
| `1`、`1suffix`、`-1`、その他 `atoi` が 0 以外に変換する値 | true | 融合が可能な条件なら scan 内で正規化する |

`static` 初期化なので、値はこの分岐に初めて到達した時に読み取られ、その後の環境変更では再評価されません。設定が有効でも、後述の分割 Tensor Core scan が実行されなければ動作への影響はありません。

## 有効になる条件

- この読み取りと Tensor Core dispatch は `#if !defined(__HIPCC__)` 節にあります。HIP ではこの変数を読みません（`src/prefill/kernels.cu:2982-2999`）。
- `gdn_recurrence_impl` が通常の列挙 kernel へ進む `else` 節に入る必要があります。`(serial && with_out) || T <= 0 || variant == 2` の場合は別の kernel 経路になり、ここへ入りません（`src/prefill/kernels.cu:2977-2982`）。
- CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドで Volta 用 chunked または warp recurrence が選択された場合も、Tensor Core dispatch へ進まず、この変数は効果を持ちません。CUDA で同 macro が有効になるのは `STRATA_ENABLE_CUDA AND STRATA_EXPERIMENTAL_SM60` のときです（`src/prefill/kernels.cu:2937-2976`; `CMakeLists.txt:418-420`）。
- 実際に scan 内の正規化が変わるのは `with_out` が true、Tensor Core scan が分割形式、かつ `STRATA_GDN_TC_TILES` または自動選択による tile 数が 1 の場合です。2 tile のときは正規化が head 全体にまたがるため、常に後段の正規化 kernel を使います（`src/prefill/kernels.cu:3000-3002`）。
- 通常の自動 dispatch は `STRATA_GDN_TC` が `atoi` で非 0 かつ `T >= 128` のとき、まず非分割 Tensor Core scan を試します。それが失敗した場合に分割 scan を試し、成功すればこの変数が融合可否に関与します。診断用 `GdnProbe` が分割 scan を強制する経路もあります（`src/prefill/kernels.cu:935,2986-2989,3003-3009,3026-3037`）。
- `STRATA_GDN_TC_NP` は自動時の分割 scan のパス数を選び、未設定時は 3、`atoi` の値が 1 または 2 の場合のみその値、それ以外は 3 です。`STRATA_GDN_TC_TILES` は tile 数を選び、未設定または `atoi` の値が 0 以下なら GPU の SM 数に基づいて自動選択します（`src/prefill/kernels.cu:1283-1298,3033-3036`）。これらは融合の前提となる scan 経路に影響します。

## 実行時の詳細

通常の prompt 処理は `prefill.cpp` から `gdn_recurrence` を呼びます（`src/prefill/prefill.cpp:3830-3831,6953-6956`）。CUDA で上記の dispatch 節に入ると、`tc_fuse` と `with_out && tc_fuse && tcl == 1` から `GdnTcNorm` のポインターを作ります。ポインターが渡された分割 scan は各 chunk の結果から正規化した FP16 `y16` を書きます。渡されない場合は scan の後に `gdn_out_norm_kernel` が `y` を読み、正規化して `y16` に書きます（`src/prefill/kernels.cu:2998-3002,3068-3069`; `src/prefill/gdn_tc.cuh:448-455,600-645`; `src/prefill/kernels.cu:2200-2214`）。

非分割 Tensor Core scan が成功した場合、この変数による融合はなく、通常の後段正規化が実行されます。Tensor Core 経路に入らない場合も同様に値は処理経路を切り替えません。状態だけを進める `with_out=false` の呼び出しでは正規化自体がなく、`tc_fuse` の値は `tcnp` を有効にしません（`src/prefill/kernels.cu:3000-3002,3068-3069,3101-3106`）。

この変数専用の警告やログ出力はありません。テスト用 probe は選択された経路・理由等を記録しますが、通常の環境値を表示するものではありません（`src/prefill/kernels.cu:2990-2996,3059`）。kernel 起動エラーは共通の `check("gdn_recurrence")` により stderr に `prefill gdn_recurrence: <CUDA error>` と出力され、終了コード 1 で終了します（`src/prefill/kernels.cu:3071,102-105`）。このエラー処理は `STRATA_GDN_TC_FUSE` 固有ではありません。

## 根拠

- 環境値の読み取り、正規化ポインターの条件、dispatch と後段正規化: `src/prefill/kernels.cu:2977-3009,3026-3037,3060-3071`
- 分割 scan の融合制約と正規化計算: `src/prefill/gdn_tc.cuh:448-455,600-645`
- 分割 scan launch と norm pointer によるテンプレート選択: `src/prefill/kernels.cu:1308-1368`
- 通常の prompt 呼び出し、state-only の経路: `src/prefill/prefill.cpp:3824-3834,6953-6958`; `src/prefill/kernels.cu:3101-3106`
- 関連資料 `docs/DETAILS.md:1535-1545` は `STRATA_GDN_TC` の opt-in 経路を説明しますが、`STRATA_GDN_TC_FUSE` 自体の記述はありません。ここでは測定値を追加していません。
