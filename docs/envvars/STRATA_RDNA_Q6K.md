# `STRATA_RDNA_Q6K`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP AMD 向けのネイティブ MMVQ 経路で、RDNA 用 Q6_K / K 量子化カーネルと Q8_0 WMMA 経路を試す共通ゲートを有効にします。変数は `rdna_q6k_enabled()` が読み、Q6_K だけでなく Q4_K、Q5_K、IQ4_XS、IQ3_S、Q8_0 の呼び出し側からも参照されます（`engine/src/kernels/cuda/rdna_mmvq.cu:377-385, 391-393, 438-440, 467-475`; `engine/src/kernels/cuda/native_mmvq.cu:3319, 3526, 3567, 3600-3610, 3701-3703, 3813-3815`）。

## 値と判定

`std::getenv` で設定有無を調べ、値全体の parse はせず先頭 1 文字だけを `'1'` と比較します。`STRATA_RDNA_Q6K` が設定されている場合、その判定が優先され、先頭が `1` のときだけ有効です。空文字も「設定あり」なので無効となり、`STRATA_HIP_FAST_DEC` への fallback を止めます（`engine/src/kernels/cuda/rdna_mmvq.cu:377-385`）。

| 条件 | `STRATA_RDNA_Q6K` | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP AMD ビルド（`__HIP_PLATFORM_AMD__`、`STRATA_HIP_GFX906` ではない） | unset | `STRATA_HIP_FAST_DEC` が未設定でなく先頭文字が `1` の場合は、RDNA 3 / 4 のデバイス判定を通ると有効 | `STRATA_HIP_FAST_DEC` が未設定、空、または先頭文字が `1` 以外なら無効 |
| 同上 | 設定あり | 先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `01` など先頭文字が `1` でない値 |
| その他のビルド条件 | 任意 | なし。このファイルの `#else` 実装は常に `false` を返す | 常に無効 |

`STRATA_RDNA_Q6K` が設定されている場合は値が無効でも `STRATA_HIP_FAST_DEC` を確認しません。変数自体に数値範囲・境界値・大文字小文字の概念はありません（同 `rdna_mmvq.cu:377-385`）。

## 有効になる条件

- 実装本体は `__HIP_PLATFORM_AMD__` が定義され、`STRATA_HIP_GFX906` が未定義のときだけコンパイルされます。HIP ビルド設定は wave32 AMD GPU 向けです。その他ではスタブが `false` を返します（`engine/src/kernels/cuda/rdna_mmvq.cu:20-22, 36, 484-493`; `engine/CMakeLists.txt:97-104`）。
- `STRATA_RDNA_Q6K` の先頭が `1` なら `rdna_q6k_enabled()` は GPU 世代を検査せず `true` を返します。したがってこの明示設定に対する RDNA 世代の実行時ガードはありません。先頭が `1` 以外または未設定時に `STRATA_HIP_FAST_DEC` で有効化される場合は、デバイス名が gfx11 WMMA または gfx12 と判定される必要があります（`engine/src/kernels/cuda/rdna_mmvq.cu:352-372, 377-385`）。
- Q6_K カーネルの呼び出しには `n_in` が 256 の倍数で、`ncols` が 1..16 の条件が必要です。二つ目の weight 入力がある場合は `n_out` も 8 の倍数でなければ、この経路は `false` を返して通常経路へ戻ります（`engine/src/kernels/cuda/rdna_mmvq.cu:438-442`）。
- Q6_K の native MMVQ では、先に `q6_packed_mmvq` が成功すると本変数のゲートへ進みません。ゲート後も RDNA 経路が `false` なら通常の Q6K 実装が続きます（`engine/src/kernels/cuda/native_mmvq.cu:3600-3614`）。
- Q8_0 経路は `ncols >= 8` の場合にだけこのゲートを呼び、さらに `STRATA_RDNA_Q80_WMMA` の先頭が `0` なら Q8_0 WMMA を無効にします。その他にも列数 8..16、`n_in` が 32 の倍数、`n_out >= 64` が条件です（`engine/src/kernels/cuda/native_mmvq.cu:3699-3704`; `engine/src/kernels/cuda/rdna_mmvq.cu:467-481`）。
- CLI 引数からこの変数を設定するコードは見つかりませんでした。別の環境変数 `STRATA_HIP_FAST_DEC` は未設定時の代替ゲートです。Strata の gfx1151 Windows 向け既定値が同変数を設定する経路があります（`engine/include/strata/core/gfx11_extra.hpp:94-109`; `engine/src/core/arch_defaults.cpp:302-310, 334-339`; `engine/src/program/generate.cpp:4315`）。ただし対象変数が空文字を含め設定済みなら、そちらが優先されます。

## 実行時の詳細

`rdna_q6k_enabled()` 内の関数ローカル `static const int env` が初回呼び出し時に二つの環境変数を評価して保存します。同一プロセスでは以後の環境変更はこのゲートに反映されません。`STRATA_RDNA_Q6K` の有効値 `1` は `env == 1` として即時許可され、代替変数による有効化 `env == 2` は GPU ごとに静的配列へキャッシュされるアーキテクチャ判定を通します（`engine/src/kernels/cuda/rdna_mmvq.cu:352-385`）。

環境変数が有効でも、該当する量子化形式・shape などの条件に合わない関数は `false` を返します。native MMVQ 呼び出し側は `false` のとき既存の通常カーネルへ続き、専用経路の失敗だけで処理を終了するコードではありません（`engine/src/kernels/cuda/rdna_mmvq.cu:391-429, 438-465`; `engine/src/kernels/cuda/native_mmvq.cu:3319-3324, 3609-3614`）。

## ログと測定値

この変数を直接読み取る箇所から有効・無効のログは出ません。代替となる `STRATA_HIP_FAST_DEC` がアーキテクチャ既定値として設定された場合、gfx11 既定スイッチの集計ログに名前が含まれることがあります（`engine/src/core/arch_defaults.cpp:312-332, 334-339`）。対象変数固有の測定値は、調査対象ソースと関連資料では確認できませんでした。

## 根拠

- `engine/src/kernels/cuda/rdna_mmvq.cu:20-22, 36-37, 352-385, 391-429, 438-493` — build guard、値の判定・cache、デバイス判定、カーネル経路と fallback。
- `engine/src/kernels/cuda/native_mmvq.cu:3319-3324, 3526, 3567-3572, 3600-3614, 3699-3704, 3813-3815` — native MMVQ からの呼び出し。
- `engine/cmake/strata_gpu_engine.cmake:52-53, 97-107`、`engine/CMakeLists.txt:97-104` — HIP/CUDA カーネル build 構成。
- `engine/src/core/arch_defaults.cpp:302-310, 312-339`、`engine/include/strata/core/gfx11_extra.hpp:94-109`、`engine/src/program/generate.cpp:4315` — `STRATA_HIP_FAST_DEC` の既定設定経路。

`docs/SETTINGS.md:291` はこの項目を「NVIDIA and AMD」と記載していますが、上記の実装は AMD HIP platform のコンパイル条件下にあり、非 HIP 側は常に `false` の stub です。実行時動作はソース実装を根拠に記載しました。
