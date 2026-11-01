# `STRATA_MMVQ_IL_T1`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の `native_mmvq_il` にある 1 列（1 token）の interleaved matvec 用 row table を有効／無効にします。table が非 0 のセルでは、その型・出力幅・GPU 用に定義された row 数で専用 kernel を選びます。`0` のセル、またはこの変数で無効にした場合は `native_mmvq` の通常 kernel に戻ります。1 列用の table は Q3_K、IQ4_XS、Q4_K、Q5_K の一部の GPU 世代にだけ定義されています（`src/kernels/cuda/native_mmvq.cu:3740-3766`）。

Strata 内での利用箇所は speculative verify の projection と head です。通常の `src/core/layer.cpp` の 1 列 projection は `native_mmvq` を直接呼び、`native_mmvq_il` を通らないため、この変数の制御対象ではありません（`src/core/layer.cpp:168-183`）。

## 値と判定

`il_t1_on()` は共通 helper `il_env_on()` に名前を渡し、`std::getenv()` の結果が未設定なら有効、設定済みなら先頭文字が `'0'` 以外で有効とします。文字列全体や数値としては parse しません（`src/kernels/cuda/native_mmvq.cu:3768-3772`）。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（先頭は終端文字 `\0` で、`'0'` ではない） |
| `0`, `0anything` | 無効 |
| `1`, `true`, `false`, `2`, その他先頭が `0` でない文字列 | 有効 |

判定値は関数内の `static const bool` に保存されます。最初に 1 列 table の判定が行われた後の環境変更は再読込されません。無効の場合は row 数を 0 として返し、呼び出し側は通常 kernel に fallback します（`src/kernels/cuda/native_mmvq.cu:3842-3850,3930-3942`）。

## 有効になる条件

この変数が有効でも、次のすべてを満たす場合に限り 1 列 interleaved kernel が選ばれます。

- 呼び出し側の `STRATA_MMVQ_IL` が無効でないこと。verify 側では同じ先頭文字判定で、未設定を有効、先頭が `0` を無効とし、無効なら interleaved 呼び出し自体を行いません（`src/core/verify.cpp:172-175,1508-1517,2454-2460`）。
- CUDA 実装であること。HIP コンパイル側は `native_mmvq_il_supported()` が常に false を返し、通常 kernel に委譲します（`src/kernels/cuda/native_mmvq.cu:3960-3976`）。
- `g_multi_exact` が true であること。初期値は true ですが、native MMVQ API で変更可能です（`src/kernels/cuda/native_mmvq.cu:1228,3051-3052,3930-3933`）。
- 現在の GPU 世代が interleaved 対応であること。sm_80 以上は対象、sm_70・sm_75・sm_60・sm_61 は各世代の別スイッチ条件が必要です（`src/kernels/cuda/native_mmvq.cu:3914-3926`）。さらに 1 列 table がある compute capability（60/61/80/86/89）と量子化型・`n_out` クラスに該当し、table の row 数が非 0 である必要があります（`src/kernels/cuda/native_mmvq.cu:3742-3766,3830-3850`）。sm_89 は `STRATA_MMVQ_IL_89` の解決結果が opt-in でなければ固有 table を使いません（同ファイル `:3774-3780,3846-3849`）。
- `native_mmvq_il_supported()` が受け付ける型（IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K）であること（`src/kernels/cuda/native_mmvq.cu:3930-3933`）。1 列 table に Q6_K の行はないため、Q6_K はこの table 経由では通常 kernel になります。

他の環境変数との優先関係として、`STRATA_MMVQ_IL_ROWS` に有効な `ncols=1` 行がある場合、その row が `STRATA_MMVQ_IL_T1` の判定より先に返されるため、T1 を `0` にしてもその行は抑止されません（`src/kernels/cuda/native_mmvq.cu:3795-3825,3842-3849`）。`STRATA_MMVQ_IL=0` は verify 呼び出し全体を止める上位 gate です。

## 実行時の詳細

verify の projection では、`n`（window 内 token 数）が 1 のときも `native_mmvq_il_supported()` を確認します。サポートされる row が選ばれた場合、1 列は通常の q8_1 blocks をそのまま使い、複数列用の interleave copy は作りません。選択された型の kernel を launch し、row が 0 または条件不成立なら `native_mmvq()` に fallback します（`src/core/verify.cpp:1508-1517`; `src/kernels/cuda/native_mmvq.cu:3936-3956`）。verify head も同じ判定を使います（`src/core/verify.cpp:2452-2460`）。

この環境変数専用のログ、警告、終了経路は見つかりませんでした。変数が無効、または条件不成立の場合は fallback するため、Strata 側からは通常 kernel が実行されます。設計資料は interleaved table の選択が通常 kernel と同じ出力 bit を保ち、速度選択だけを変えると説明しています（`docs/MMVQ_IL_TABLE.md:3-7,18-21`）。この調査では build や GPU 実行による実測確認はしていません。

## 根拠

- 候補名の全参照: `src/kernels/cuda/native_mmvq.cu:3740,3772,3844`。直接の getenv は共通 helper に集約され、`il_t1_on()` から渡されます（同ファイル `:3768-3772`）。
- 1 列 table・row lookup: `src/kernels/cuda/native_mmvq.cu:3740-3766,3829-3850`。
- 対応条件、通常 kernel への fallback、kernel launch: `src/kernels/cuda/native_mmvq.cu:3914-3958,3960-3976`。
- verify 側の master gate と呼び出し: `src/core/verify.cpp:172-175,1490-1517,1547-1561,1788-1798,2452-2463`。
- 設計説明との照合: `docs/MMVQ_IL_TABLE.md:3-10,14-22`。`docs/DETAILS.md:1231-1234` は 2–8 token と sm_89 の 1 token Q3_K table に触れます。ソースでは 1 列 table に sm_61 / sm_80 / sm_86 の行もあります。
