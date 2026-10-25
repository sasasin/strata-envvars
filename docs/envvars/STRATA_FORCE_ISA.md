# `STRATA_FORCE_ISA`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

Strata 独自の CPU ISA 判定に上限を設け、対応する AVX-512 / AVX2 / AVX のカーネル選択を抑制します。テストと、古い CPU 向けビルドの経路を新しい CPU 上で試す用途です。CPU 機能を実際に無効化するものではなく、`ggml-cpu` のビルド設定やその ISA 判定も変更しません。

## 値と判定

`src/kernels/cpu/expert_layout.cpp:25-39` で文字列全体を大文字小文字を区別して比較します。前後の空白除去や数値変換はありません。

| 値 | 上限 | 判定 |
|---|---:|---|
| 未設定または空文字 | 3 | 上限なし。CPU/OS の実機判定を使う |
| `avx2` | 2 | AVX-512 を使わず、AVX2 までを許す |
| `avx` | 1 | AVX2 / AVX-512 を使わず、AVX までを許す |
| `sse`、`sse4.2`、`none` | 0 | AVX / AVX2 / AVX-512 を使わない |
| その他 | 3 | stderr に `strata: STRATA_FORCE_ISA=<値> is not avx2, avx or sse; ignored` を出し、上限なしとして扱う |

したがって `AVX`、` sse`、`0` は有効値ではありません。値が `sse4.2` または `none` の場合もログ上の値はそれぞれ受け取った文字列のままですが、上限値は `sse` と同じです。

## 有効になる条件

値を読むのは `src/kernels/cpu/expert_layout.cpp` の CPU ISA 判定を使う実行経路です。値が有効でも、そのレベルの機能を備えた CPU/OS でなければ対応カーネルは選択されません。上限は機能の実在判定に追加される制限であり、機能を追加する設定ではありません。

この上限が適用されるのは Strata 独自の `cpu_avx512_ok()`, `cpu_avx2_ok()`, `cpu_avx1_ok()`、gather-fast 判定、および AVX-VNNI 判定です。`cpu_avx512bw_ok()` はこの上限を参照しませんが、HEAD 内にこの関数の呼び出し箇所はありません。`cpu_features()` による標準 Q2_0 エンジンの AVX-512 必須チェックもこの上限とは独立です。従って `STRATA_FORCE_ISA` は標準 Q2_0 エンジンの CPU 要件を回避しません（`src/kernels/cpu/expert_layout.cpp:76-108,260-273,322-353`、`src/program/generate.cpp:2898-2900`）。

## 実行時の詳細

最初の `cpu_isa_cap()` 呼び出しで環境変数を読み、その結果を関数内の `static const int` に保存します。同一プロセスで環境を後から変更しても再評価されません。`cpu_avx512_ok()` は上限が `3` 未満なら false、`cpu_avx2_ok()` は `2` 未満なら false、`cpu_avx1_ok()` は `1` 未満なら false を返します。gather-fast と AVX-VNNI の判定も、上限が `3` 未満なら false になります。実際の CPUID と OS の状態チェックは各判定に残るため、上限以下の命令セットを CPU がサポートしないときはそのカーネルも使われません（`src/kernels/cpu/expert_layout.cpp:41-73,110-185,219-272`）。

CPU の expert 計算では、これらの判定を使って AVX-512、AVX2、AVX1 の実装を選びます。native expert の経路では AVX-512/AVX2/AVX1 カーネルを選べない場合に ggml の `vec_dot` へフォールバックします。一方、canonical Q2_0 の `q2_rows_any()` と `act_quant_any()` は AVX-512/AVX2 の probe が false なら AVX1 実装を選ぶため、`STRATA_FORCE_ISA=sse` でもこの経路だけは AVX1 を選び得ます。標準 Q2_0 engine は実 CPU の AVX-512 要件を別途確認しますが、この環境変数は完全な CPU 命令セット・エミュレーターではありません（`src/kernels/cpu/expert_layout.cpp:356-373`、`src/kernels/cpu/native_expert.cpp:143-230`、`src/program/generate.cpp:2898-2900`）。`STRATA_FORCE_ISA=avx` を使った旧 CPU 経路の動作確認について、`docs/INSTALL.md` は通常ビルドの ggml-cpu と AVX/AVX-512 カーネルでは丸めが異なるため、生成 token が通常ビルドと一致しないことがあると説明しています（`docs/INSTALL.md:154-167`）。

## 根拠

- 値の読み取り、文字列比較、無効値ログ、static cache: `src/kernels/cpu/expert_layout.cpp:25-39`
- AVX-512 / AVX2 / AVX / SSE4.2 判定と上限の反映: `src/kernels/cpu/expert_layout.cpp:41-185`
- 上限を使う gather-fast / AVX-VNNI 判定: `src/kernels/cpu/expert_layout.cpp:219-272`
- CPU expert のカーネル選択: `src/kernels/cpu/expert_layout.cpp:356-373`、`src/kernels/cpu/native_expert.cpp:143-230`
- 標準 Q2_0 経路での独立した CPU 要件チェック: `src/kernels/cpu/expert_layout.cpp:322-353`、`src/program/generate.cpp:2898-2900`
- `STRATA_FORCE_ISA` をテスト用に設定する例と旧 CPU 経路の注意: `CMakeLists.txt:1377,1403`、`docs/INSTALL.md:154-167`
