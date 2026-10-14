# `STRATA_NO_NVFP4_256`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU の native expert 経路で、AVX2 版 NVFP4 行カーネルを使わず、該当する計算を ggml-cpu の `vec_dot` へフォールバックさせるための抑止スイッチです。ゲート／アップ行とダウン行の両方に別々の判定があります。GPU の NVFP4 カーネルや AVX-512 版 NVFP4 カーネルを直接制御しません。

## 値と判定

値の parse はせず `std::getenv(...) != nullptr` で設定の有無だけを調べます。

| 環境の状態 | AVX2 NVFP4 カーネルの許可判定 |
|---|---|
| 未設定 | CPU が AVX2 条件を満たせば許可 |
| 任意の値を設定（空文字、`0`、`false` を含む） | 不許可 |

`native_gu_rows()` と `native_down_rows()` はそれぞれの関数内の `static const bool` に結果を保存します。各関数で最初に判定した後の環境変更は、その関数の判定には反映されません。2関数の初回呼び出し時期は独立しています。

根拠: `src/kernels/cpu/native_expert.cpp:213-215,265-268`。

## 有効になる条件

環境変数が未設定でも、次の条件が必要です。

- native expert の CPU 計算経路が使われること。`ExpertPool` の native mode でゲート／アップ行またはダウン行を処理すると、各行関数が呼ばれます。
- CPU が `cpu_avx2_ok()` を満たすこと。これは CPU の ISA 上限、AVX/FMA/F16C/AVX2 機能、OS による AVX 状態保存を確認します。条件不足なら AVX2 専用コードには進みません。
- 対象行列の型が NVFP4（ggml type 40）であること。
- 次元が AVX2 カーネルに適合すること。`nvfp4_256_fits(n)` は `n` が NVFP4 ブロック幅 `QK_NVFP4` の倍数で、かつブロック数が `kMaxBlocks` 以下の場合に true です。ゲート／アップでは `n_embd`、ダウンでは `n_ff` が検査されます。

AVX-512 対応 CPU では、各関数は先に AVX-512 NVFP4 カーネルを検討します。その経路が有効で次元にも適合すればそこで戻るため、`STRATA_NO_NVFP4_256` を設定しても AVX-512 カーネルは止まりません。AVX-512 経路が使えない、または次元不適合で AVX2 判定まで進んだ場合に、この変数が AVX2 経路を止めます。

根拠: `src/kernels/cpu/native_expert.cpp:204-216,258-268`, `src/kernels/cpu/nvfp4_avx2.cpp:161`, `src/kernels/cpu/expert_layout.cpp:110-142`。

## 実行時の詳細

native expert のゲート／アップ処理では、NVFP4 専用カーネルが使われると gate と up の積和を計算して SiLU と up の積を出力します。ダウン処理では NVFP4 行列と中間活性の積を出力します。AVX2 経路を許可しない場合、または CPU・型・次元条件を満たさない場合は、各行について ggml-cpu の `traits(...)->vec_dot` を呼ぶ汎用ループへ進みます。したがって、この変数は NVFP4 計算自体を無効にするのではなく、AVX2 実装の選択を抑止します。

通常の CPU expert pool は native mode のゲート／アップ処理で `native_gu_rows()`、ダウン処理で `native_down_rows()` を呼びます。参照した本番ソースではこの変数に対応するログ出力はありません。`docs/DETAILS.md` にこの変数固有の説明は見つかりませんでした。カーネルのコメントには AVX2 経路の性能測定への言及がありますが、この調査では実行・測定を行っていません。

根拠: `src/kernels/cpu/pool.cpp:684-719`, `src/kernels/cpu/native_expert.cpp:194-229,233-279`, `src/kernels/cpu/nvfp4_avx2.cpp:1-9`。
