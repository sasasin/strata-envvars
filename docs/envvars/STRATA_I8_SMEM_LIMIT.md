# `STRATA_I8_SMEM_LIMIT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA/HIP 側の prompt expert 用 native int8 カーネルが使える block あたり dynamic shared memory 上限を、デバイスが報告する上限より小さく設定する調査用 override です。未設定・0・負数・デバイス上限以上の値では上限を変えず、正の値がデバイス上限より小さい場合だけ、その値を上限にします。native I8 経路の適格性判定と、実行時に選ぶタイルサイズの両方に影響します。カーネルの計算式や出力値を直接変更する分岐ではありません。実装は `i8_smem_limit()` と `native_expert_i8_supported()`、呼び出しは prompt 経路の選択および `native_expert_i8()` にあります（`src/kernels/cuda/i8_expert.cuh:1191-1196`, `src/kernels/cuda/iq_kernels.cu:6330-6334`, `src/kernels/cuda/iq_kernels.cu:6368-6370`）。

## 値と判定

`i8_smem_limit()` が `i8_env_int("STRATA_I8_SMEM_LIMIT", 0)` を呼び、helper は `getenv` で取得した値が未設定または空文字なら既定値 `0`、それ以外なら `std::atoi` の結果を返します。全体の数値妥当性検査はなく、`atoi` が読む先頭の整数部分が使われます。したがって、先頭の空白と符号は `atoi` の規則に従い、数値の後ろの文字は判定されません。数値に変換できない文字列は `atoi` により `0` になります（`src/kernels/cuda/i8_expert.cuh:1208-1211`）。

| 条件 | unset / 空文字 | 上限を下げる値 | 上限を下げない値 |
|---|---|---|---|
| native I8 実装を含む CUDA/HIP カーネル経路 | 既定 override `0`。デバイス上限をそのまま使う | `atoi` の結果が正で、かつデバイス上限より小さい値。例: `1`, `40960`, `" 40960bytes"` | `0`, `-1`, `true`, `false`, `0anything`, または `atoi` の結果がデバイス上限以上の値。例: デバイス上限が 98304 bytes のとき `98304`, `100000` |

文字列全体の比較、範囲 clamp、末尾文字の拒否、大文字小文字の判定はありません。空文字は未設定と同じ既定値です。`atoi` の `int` で表せない値に対する範囲検査もありません。override が有効な場合の実効上限は `min(override, device_limit)` です。デバイス上限は初期値 48 KiB で、現在デバイスの `cudaDevAttrMaxSharedMemoryPerBlockOptin` を問い合わせて成功し、正の値が返ればその値に置き換わります（`src/kernels/cuda/i8_expert.cuh:1191-1196`）。

## 有効になる条件

- この native I8 実装を含む CUDA/HIP カーネル経路が使われること。別 backend の実装がこの環境変数を読む参照は確認できません（`src/kernels/cuda/iq_kernels.cu:6237-6240`）。
- prompt の経路選択で native I8 が許可されること。`STRATA_EXPERT_I8=0` なら無効、`STRATA_EXPERT_I8=1` なら要求されます。未設定時は HIP の gfx1030/gfx1031/gfx1032、または MMQ を含まない build で既定経路になりますが、どの場合も対応形式・サイズ・shared-memory 判定は残ります（`include/strata/kernels/i8_expert_rule.hpp:28-39`, `include/strata/kernels/i8_expert_rule.hpp:52-57`）。
- fused または staged の先行経路がその layer を取らず、expert group の平均 entry 数が 256 以上であること（`include/strata/kernels/i8_expert_rule.hpp:20-21`, `include/strata/kernels/i8_expert_rule.hpp:41-56`; 呼び出し側 `src/prefill/prefill.cpp:5992-6010`）。
- layout が native I8 の対応形式・形状であること。コードでは gate/up と down の型、nibble/tail/Hadamard 条件、埋め込み幅・FF 幅の倍数、expert blob サイズに加え、最小 tile の必要量が実効 shared-memory 上限以下であることを検査します（`src/kernels/cuda/iq_kernels.cu:6330-6334`）。
- 正の override が最小 tile の必要量より小さいと `native_expert_i8_supported()` が false になり、prompt 選択は native I8 を採りません。`STRATA_EXPERT_I8=1` でもこの supported 判定を飛び越しません（`include/strata/kernels/i8_expert_rule.hpp:54-56`, `src/kernels/cuda/iq_kernels.cu:6330-6334`）。
- 適格な場合でも、現在選ばれた tile が上限を超えると、tile 8 は 4 へ、tile 4/3 は一段ずつ小さくなり、必要量が上限以下になるまで縮小します（`src/kernels/cuda/iq_kernels.cu:6363-6370`）。

この変数を同名で上書きする CLI 引数・設定ファイル・別 helper は見つかりませんでした。別の環境変数 `STRATA_EXPERT_I8` は経路の要求・無効化を制御しますが、shared-memory 上限を上書きしません（`src/kernels/cuda/iq_kernels.cu:6242-6246`; `include/strata/kernels/i8_expert_rule.hpp:28-57`）。

## 実行時の詳細

`i8_smem_limit()` は static cache を持たず、呼び出されるたびにデバイス上限を問い合わせ、`getenv` と `atoi` を評価します。prompt の各対象 layer/chunk の supported 判定から呼ばれ、native I8 の各呼び出しでも上限を再評価して tile を選びます。そのため、同一プロセス内で環境値が変更された場合、以後の評価には新しい値が使われます（`src/kernels/cuda/i8_expert.cuh:1191-1211`, `src/kernels/cuda/iq_kernels.cu:6285-6289`, `src/kernels/cuda/iq_kernels.cu:6330-6334`, `src/kernels/cuda/iq_kernels.cu:6368-6370`）。

エンジン経路では、上限が最小 tile より小さい場合に route 判定が native I8 を外し、通常の prompt 経路選択へ戻します。内部 API が unsupported layout のまま直接 `native_expert_i8()` を呼んだ場合は stderr に `native_expert_i8: gate/up type %d, down type %d at %lld x %lld is not covered` を出して `exit(1)` します（`src/kernels/cuda/iq_kernels.cu:6344-6352`）。

## ログと測定値

通常の prompt engine はこの変数の値や実効上限を表示しません。native I8 経路の選択ログはありますが、上限値を示すログではありません（`src/prefill/prefill.cpp:6042-6051`）。`docs/DETAILS.md` にこの変数の個別説明や、この override の測定値は見つかりませんでした。

## 根拠

- `src/kernels/cuda/i8_expert.cuh:1191-1211` — デバイス上限、override の比較、`getenv`・`atoi` の処理。
- `src/kernels/cuda/iq_kernels.cu:6285-6289` — prompt 経路の supported 判定。
- `src/kernels/cuda/iq_kernels.cu:6330-6370` — layout 判定、unsupported 時の終了、tile 選択と縮小。
- `include/strata/kernels/i8_expert_rule.hpp:20-57` — 256 entry の floor、`STRATA_EXPERT_I8` と supported 条件。
- `src/prefill/prefill.cpp:5992-6010`, `src/prefill/prefill.cpp:6042-6051` — prompt layer の経路選択と native I8 選択ログ。
- `docs/DETAILS.md:1105-1125` — CUDA opt-in kernels の概要。この範囲に本変数の説明はありません。
