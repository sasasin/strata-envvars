# `STRATA_IQ512_FUSED_MAX`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CPU の native expert 処理で、AVX-512 の fused IQ gate/up kernel を何 token まで使うかを指定します。対象の gate/up 行を一度に処理し、各 token の activation を gate と up の両方に使います。値は有効化フラグではなく、処理対象にする token group の上限です。

この経路は native expert の CPU pool が gate/up 行を計算するときに呼ばれます（`src/kernels/cpu/pool.cpp:1231-1237`）。GPU 側の expert kernel や通常の単一 token 処理を直接切り替える変数ではありません。

## 値と判定

読み取りは `std::getenv()` の後に `std::atoi()` を使い、未設定なら `0` です（`src/kernels/cpu/native_expert.cpp:528`）。文字列全体の妥当性検査や clamp はありません。`atoi` が読む先頭の符号付き十進数部分が判定値になり、先頭の空白は読み飛ばされ、数字以降の文字は無視されます。たとえば `3tail` は 3、空文字や数値で始まらない文字列は 0 になります。

| `atoi` の結果 | この変数による選択 |
|---|---|
| 未設定、空文字、変換結果が 0、負数、1 | 無効。fused kernel に入らない |
| 2 以上 | 有効化候補。`nt` が 2 以上かつこの値以下の group で候補になる |

値の上限そのものは検査されません。`atoi` の `int` 範囲を超える入力について、Strata はエラーや fallback を定義していません。

この値は関数テンプレート `native_gu_rows_impl` 内の `static const int` に保存されます。したがって各算術モードのテンプレート実体で最初に実行された時点に一度読み、その後の環境変更はその実体では再評価されません（`src/kernels/cpu/native_expert.cpp:454-455,528-529,707-724`）。

## 有効になる条件

値が 2 以上でも、次の条件をすべて満たす必要があります（`src/kernels/cpu/native_expert.cpp:463,528-547`）。

- `STRATA_NATIVE_EXPERTS` を有効にしたビルドで native expert CPU 経路が使われる。無効ビルドは `native_expert.cpp` を組み込まず、native expert pack の読み込みも拒否します（`CMakeLists.txt:176,2182-2185,2238-2239`; `src/kernels/cpu/expert_layout.cpp:488-498,512-514`）。
- CPU が `cpu_vnni_ok()` を満たし、`STRATA_NO_IQ512` が未設定である（空文字を含め、設定されていれば無効）。これが gate/up dispatch の AVX-512 条件です（`src/kernels/cpu/native_expert.cpp:459-463`）。さらに fused kernel 側は VPOPCNTDQ 対応を要求します（`src/kernels/cpu/iq_avx512.cpp:653-665,759`）。
- `nt` が `2 <= nt <= fused_max` で、`f.tail_off == 0`、`0 < f.gu_type < 32` である（`src/kernels/cpu/native_expert.cpp:529`）。
- `STRATA_IQ512_FUSED_TYPES` の型リストに `f.gu_type` が含まれ、型が fused 実装の対応範囲にある。別変数が未設定または空文字なら既定は `18,21,22`（IQ3_XXS / IQ3_S / IQ2_S）。リストに `16` または `17` を明記すれば IQ2_XS / IQ2_XXS も実装上の対応型に含まれます（`src/kernels/cpu/native_expert.cpp:530-544`; `src/kernels/cpu/iq_avx512.cpp:759-770`）。
- 起動時の実行時照合 `iq512f_ok(type)` が true を返す。Strata は synthetic rows で gate/up の fused 出力を、このビルドにリンクされた ggml-cpu の dot と比較し、型ごとに結果を cache します（`src/kernels/cpu/native_expert.cpp:153-193`）。

CLI 引数による上書きはこの dispatch にありません。`STRATA_IQ512_FUSED_MAX` 自体の値が優先順位で変更されるコードもありません。先行する IQ4_XS 用の AVX-512 分岐は型 23 専用で、この fused 分岐の型とは重なりません（`src/kernels/cpu/native_expert.cpp:518-522,524-547`）。

## 実行時の詳細

条件が揃うと `iq512_fused_gu_rows()` に gate/up の blob、activation、`nt`、行範囲を渡して return します。fused 実装は対応型 16/17/18/21/22 を処理し、token 数を最大 4 件ずつに分けて実行します。したがって上限を超えた group を複数 group に分割する動作ではなく、この環境変数の分岐を通らず後続 dispatch に進みます（`src/kernels/cpu/native_expert.cpp:544-547`; `src/kernels/cpu/iq_avx512.cpp:742-770`）。

照合が不一致の場合、stderr に `strata: the fused 512-bit gate/up rows of type %d differ from this ggml-cpu's dot: not used` を出し、fused 分岐を抜けて既存の native kernel または ggml-cpu の dot に進みます。値が未設定・空・0・1、token 数が範囲外、CPU/型条件が合わない場合、この変数に関するログはありません（`src/kernels/cpu/native_expert.cpp:544-550,620-632`）。

## 根拠

- 値の読み取り、上限条件、型リストと dispatch: `src/kernels/cpu/native_expert.cpp:524-548`
- CPU と他の IQ kernel 選択条件: `src/kernels/cpu/native_expert.cpp:459-463,518-522`
- fused kernel の VPOPCNTDQ/type 条件と token batching: `src/kernels/cpu/iq_avx512.cpp:653-665,742-770`
- ggml-cpu との照合、cache、警告: `src/kernels/cpu/native_expert.cpp:153-193`
- native expert CPU pool からの呼び出し: `src/kernels/cpu/pool.cpp:1231-1237`
- native expert のビルド条件と無効時の stub: `CMakeLists.txt:176,2182-2185,2238-2239`; `src/kernels/cpu/expert_layout.cpp:488-498,512-514`
