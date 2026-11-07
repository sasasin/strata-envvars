# `STRATA_IQ512_FUSED_TYPES`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

AVX-512 native expert CPU 経路で、複数 token の IQ expert の gate/up 行を融合して計算する対象の ggml type 番号を選びます。この変数だけでは機能は有効になりません。別変数 `STRATA_IQ512_FUSED_MAX` が 2 以上の token 数を許可し、native expert の gate/up 計算が該当条件を通った場合にだけ、この type リストが参照されます。

読み取りは `src/kernels/cpu/native_expert.cpp:530-544`、native expert の実行時呼び出しは `src/kernels/cpu/pool.cpp:1231-1237` です。この名前の参照はソース全体でこの箇所だけです。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | 既定リスト `18,21,22` を使用する。 |
| 空文字 | 未設定と同様に `18,21,22` を使用する。 |
| 空でない文字列 | カンマで区切った各項目の先頭を `std::atoi` で整数変換し、`1..31` の値を bitset に加える。 |

文字列全体の厳密な parse やエラー検査はありません。`atoi` が読む各項目は、先頭の空白と符号を許し、数字の後ろにある文字を無視します。そのため `"18junk, +21, 22x"` は 18, 21, 22 を選びます。数値に変換できない項目、0、負数、32 以上は無視されます。連続カンマや末尾カンマもエラーにはなりません。たとえば `"18,abc,22,"` は 18 と 22 を選び、`"garbage"` は空の選択になります。大文字小文字は関係ありません。

パーサー上は 1..31 を保持できますが、融合カーネルが対応するのは type 16, 17, 18, 21, 22 だけです。さらに現在の `iq512f_supported()` は AVX512 VPOPCNTDQ がある CPU でのみ true になり、この5 type のうち選択された type が実行候補になります（`src/kernels/cpu/iq_avx512.cpp:653-665,759-769`）。既定値の 18, 21, 22 は IQ3_XXS, IQ3_S, IQ2_S に対応します（同ファイル `:9-10`）。

## 有効になる条件

以下をすべて満たす必要があります。

- `STRATA_NATIVE_EXPERTS` を有効にしてビルドされている。無効時は native expert 実装がコンパイル対象にならず、native expert load も拒否されます（`CMakeLists.txt:176,2121-2122,2182-2186,2239`; `src/kernels/cpu/expert_layout.cpp:488-499`）。
- x86 CPU build で AVX-512 kernel が組み込まれている。非 x86 build は `portable.cpp` の stub が `iq512f_supported()` を常に false にします（`CMakeLists.txt:62-67,2059-2065,2184-2194`; `src/kernels/cpu/portable.cpp:127,132-134`）。
- 呼び出しが native expert pool の mode 5 に入り、`native_gu_rows()` が実行される（`src/kernels/cpu/pool.cpp:1219-1237`）。
- `STRATA_IQ512_FUSED_MAX` の parse 結果が 2 以上で、実際の token 数 `nt` が 2 以上かつその値以下。上限は `std::atoi` で読み、未設定時は 0、空文字や数値として読めない値も 0 です（`src/kernels/cpu/native_expert.cpp:528-529`）。この対象変数はこの上限を設定しません。
- CPU probe により `avx512` が true。これは `cpu_vnni_ok()` が true で、かつ `STRATA_NO_IQ512` が unset の場合です（同ファイル `:463`）。VNNI probe は AVX-512 F/DQ/BW/VL と VNNI を要求し、VBMI がない CPU では `STRATA_VNNI_TIER` の先頭文字が `1` の場合に限り許可します（`src/kernels/cpu/expert_layout.cpp:188-203`）。
- `f.tail_off == 0`、gate/up type が 1..31 の範囲で、かつその type が環境値の bitset に含まれる（`src/kernels/cpu/native_expert.cpp:529-544`）。
- `iq512f_supported(type)` と `iq512f_ok(type)` が true。後者は linked ggml-cpu の Q8_K activation quantizer / dot が使えることを確認し、3 token・24 row の合成データで融合結果と ggml-cpu の gate/up + SwiGLU 結果を bit 単位で比較します（同ファイル `:153-193`）。

条件を満たさない場合、この変数による融合は行われず、関数は後続の通常 native row dispatch に進みます（`src/kernels/cpu/native_expert.cpp:548-596`）。この経路に CLI 引数や別の型リスト設定による上書きはありません。`STRATA_IQ512_FUSED_MAX` は独立した有効化・token 上限条件であり、`STRATA_NO_IQ512` と `STRATA_VNNI_TIER` は AVX-512 利用可否に関係します。

## 実行時の詳細

`native_gu_rows_impl()` は `STRATA_IQ512_FUSED_MAX` を関数の初回実行時に `static const int` として読み、以後プロセス内で cache します。対象の `STRATA_IQ512_FUSED_TYPES` はその後の条件ブロック内にある `static const unsigned` で、初めて上限・CPU・token 数・tail・type 範囲の条件を満たした時に読み、以後 cache します。したがって、対象変数は起動時に必ず読むわけではなく、該当する最初の native expert group までに設定されていなければなりません。その初回評価後の環境変更は反映されません（`src/kernels/cpu/native_expert.cpp:528-544`）。

選択された場合、`iq512_fused_gu_rows()` が gate と up の行を融合計算し、token ごとの SwiGLU 結果を `ff` に書き込み、その場で戻ります（`src/kernels/cpu/native_expert.cpp:544-546`; `src/kernels/cpu/iq_avx512.cpp:761-770`）。Strata はこの環境変数の parse エラーに対する警告を出しません。型が非対応、または fused の結果が現在の ggml-cpu と bitwise 一致しない場合は fused kernel を使わず、後続の通常 dispatch に進みます。不一致時に限り stderr に `strata: the fused 512-bit gate/up rows of type %d differ from this ggml-cpu's dot: not used` を出します（`src/kernels/cpu/native_expert.cpp:189-193,544-549`）。対象変数そのものを示す起動ログ、成功ログ、無効値エラー、プロセス終了経路はありません。

## 根拠

- 環境値読み取り、既定値、区切り、数値化、bitset 化: `src/kernels/cpu/native_expert.cpp:530-543`。
- 上限、実行条件、fallback: `src/kernels/cpu/native_expert.cpp:528-549`。
- VNNI/AVX-512 と VPOPCNTDQ 条件: `src/kernels/cpu/native_expert.cpp:463`; `src/kernels/cpu/expert_layout.cpp:188-203`; `src/kernels/cpu/iq_avx512.cpp:653-665,759-769`。
- fused parity guard と観測される不一致ログ: `src/kernels/cpu/native_expert.cpp:153-193,544-549`。
- pool の native CPU dispatch: `src/kernels/cpu/pool.cpp:1219-1237`。
- Strata の調査資料 `docs/DETAILS.md` には、この環境変数固有の追加仕様・測定条件は見つかりませんでした。
