# `STRATA_PF_DM16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP の prompt fused native expert 経路で、対応する F16 down kernel が expert ごとの down 出力行を FP32 ではなく FP16 で一時バッファ `Dm` に書き、MoE combine も FP16 入力用 kernel に切り替えるスイッチです。書込み・読込みバイト数は半分になりますが、値はFP16へ丸められ、絶対値が65504を超える値は飽和します。decode側や通常のMMQ/FP16 expert経路を切り替えるものではありません。`src/prefill/prefill.cpp:931-935,5540-5554,7091-7099`、`src/prefill/moe_f16_common.cuh:248-255`。

## 値と判定

`pf_dm16()` は最初に呼ばれたとき `std::getenv` の結果を関数内 `static const bool` に保存し、値が未設定でなく先頭文字 `e[0]` が ASCII の `'1'` なら有効にします。文字列全体や数値としての妥当性は検査せず、大文字小文字・空白の正規化もしません。したがって `1`、`10`、`1anything` は有効、`0`、`true`、` 1`、空文字は無効です。未設定も無効です。`src/prefill/prefill.cpp:932-935`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常の実行時判定 | 無効（ただし下記の起動時既定値が設定された場合を除く） | 先頭文字が `1` の文字列（`1`, `10`, `1x`） | 空文字、`0`, `true`, ` 1`, `x1` |
| Windows の統合 gfx1151 で統合GPU prompt set が適用される場合 | 起動時に `1` がセットされる | `0` を含め先頭文字が `1` の値 | 明示的に設定された空文字や `0` など。設定済み値は既定値で置換されない |

値に範囲や数値変換はありません。`STRATA_PF_DM16=10` も `1` と同じ真偽判定です。`pf_dm16()` を一度呼んだ後に環境を変更しても、そのプロセス内のこの判定には反映されません。`src/prefill/prefill.cpp:932-935`。

## 有効になる条件

- 変数が有効であることに加え、prompt が `fused_l` のレイヤーを `fused_nat` として `fused::experts_native` に渡す必要があります。fused path 自体が選ばれないレイヤーには適用されません。`src/prefill/prefill.cpp:5436-5445,5540-5554`。
- この native F16 実装は HIP ビルドかつ gfx1100/1101/1102/1150/1151 向けにコンパイルされたカーネルです。gfx12 は native expert のWMMA配置が異なるためこのF16経路を使わず、CUDAビルドにもこのHIP実装はありません。`src/prefill/moe_f16_common.cuh:38-45`、`src/prefill/moe_fused_iq.cu:3171-3178`。
- down kernel が F16 対応である必要があります。通常は `STRATA_PF_F16=1` で選ばれるF16経路（K-quant down、または `Q2_0` / `IQ4_NL` / `Q8_0` / `Q5_0`）が対象です。gfx1151 の `Q8_0` down は `STRATA_PF_Q8D_F16=0` で無効化されていない既定F16経路でも対象になります。対応しない形式ではFP32 down rowsを使い、`dm_f16_used()` はfalseになります。`src/prefill/moe_fused_iq.cu:2558,2591-2606,3171-3178,3220-3225`。
- prefill caller はこの要求を `rows_cpu == 0`、`peer_now == false`、および `m.shared` と `m.bo` のアドレスがともに16-byte整列している場合に限って fused 層へ渡します。この条件を満たさないときはスイッチが真でもFP16 rows要求を出しません。`src/prefill/prefill.cpp:5540-5544`。
- Windows の統合 gfx1151 で `apply_arch_defaults` の統合GPU prompt set が適用される場合、未設定なら `STRATA_PF_DM16=1` が起動時に補われます。この既定セットは `STRATA_IGPU_DEFAULTS=0`、`STRATA_IGPU_PROMPT_SET=0` で抑止でき、ユーザーが空文字を含む何らかの値を設定していればその値が優先されます。Linux gfx1151、gfx1103/1150、離散GPUにはこの変数の同じ既定値はありません。`src/core/arch_defaults.cpp:123-136,169-177,187-213,358-373`。

## 実行時の詳細

HIP native expert 呼出しごとにスレッドローカルの `g_dm16_want` をcallerが設定します。native expert関数は各呼出しの冒頭で `g_dm16_used` をfalseに戻し、F16 down形式と希望フラグが揃うとD16 kernelを選んでFP16 rowsを書きます。通常のF16 down epilogueは値を `[-65504, 65504]` に制限してhalfへ変換します。`src/prefill/moe_fused_iq.cu:3049-3054,3114-3118,3176-3185,3220-3225`、`src/prefill/moe_f16_common.cuh:248-255`。

fused呼出し後、callerは `dm_f16_used()` を読みます。peer側のsumがない場合、`dm16_used` が真かつCPUが担当したrowsがないと `moe_combine16` を実行し、それ以外は通常のFP32 `moe_combine` へ進みます。`moe_combine16` は読み込んだhalfをfloatに戻して、通常combineと同じFMA順でroute weightを掛けて足し、shared expert項を加えます。出力経路は変わりますが、中間down値がFP16に丸められるため数値はFP32 rowsの場合と一致するとは限りません。`src/prefill/prefill.cpp:5553-5554,7086-7099`、`src/prefill/kernels.cu:2384-2410,3435-3440`。

値は `pf_dm16()` の最初の呼出し時に一度だけキャッシュされます。HIP native kernel側の要求フラグと使用結果はホストスレッドごとの `thread_local` 状態です。子プロセスへの設定・引継ぎをこの変数について行うコードは確認できません。`src/prefill/prefill.cpp:932-935`、`src/prefill/moe_fused_iq.cu:3049-3054`。

## ログと測定値

DM16だけを有効化・無効化したことを示す専用ログや、失敗時のDM16専用エラー経路はありません。既定値が適用されたWindows統合GPU起動では、統合GPU prompt set のログに設定済みスイッチ名が列挙され、その中に `PF_DM16` が含まれます。kernel起動エラーは `ck` による通常のCUDA/HIPエラーチェックへ進みます。`src/core/arch_defaults.cpp:358-373`、`src/prefill/moe_fused_iq.cu:3135-3142,3240-3243`。

ソースコメントのRound 0215測定では、Windows gfx1151の8K interleaved pairsで、IQ3_Sは1.022倍（4組中4組）、UD-IQ4_XSは1.026倍（3組中3組）、UD-Q4_K_XLは1.012倍（4組中3組）と記載されています。同コメントはfirst-token KLを8Kで `1e-4`、agent transcriptで `0.02-0.04` と記しますが、計測条件の詳細はこのソース範囲にありません。これらはコードコメントに記載された値であり、本調査で再測定したものではありません。`src/core/arch_defaults.cpp:204-207`。

## 根拠

- 読取・値判定・キャッシュ: `src/prefill/prefill.cpp:931-935`
- HIP gfx11 F16 down-format選択とDM16要求: `src/prefill/moe_fused_iq.cu:3171-3185,3220-3225`
- 既定値の設定と条件: `src/core/arch_defaults.cpp:123-136,169-177,187-213,358-373`
- FP16書込みとcombine切替: `src/prefill/moe_f16_common.cuh:248-255`, `src/prefill/prefill.cpp:7091-7099`, `src/prefill/kernels.cu:2384-2410`
