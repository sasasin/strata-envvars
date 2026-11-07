# `STRATA_GDN_CHUNKED`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

プロンプト中の GDN（gated DeltaNet）再帰計算を chunked scan に切り替える指定です。CUDA と HIP では別実装で、切替値、最小入力長、GPU 条件が異なります。chunked 経路は通常の逐次再帰と演算順序・丸めが異なるため、出力値も変わり得ます。

CUDA では 32 token 単位の FP32 chunked recurrence を選び、通常経路が使える環境でも opt-in で優先します。HIP では gfx11/gfx12 の matrix core を使う 16 token WMMA recurrence を選びます。gfx12 では未設定時に長い prompt chunk だけを自動選択する経路もあります。根拠: `src/prefill/kernels.cu:919-934,1803-1839,2131-2168,2969-2985,3070-3150`。

## 値と判定

値は整数として `atoi()` で読みます（HIP gfx12 の自動閾値は別変数 `STRATA_GDN_CHUNKED_MIN` を `atoll()` で読みます）。数値文字列全体の検証はありません。`atoi()` が読める先頭の整数部分で判定されるため、たとえば `1x` は 1、`2x` は 2、整数に変換できない文字列は 0 相当です。空文字は CUDA では 0 相当で無効、HIP では未設定相当（-1）です。値の大文字小文字は関係しません。

| ビルド・値 | 判定と動作 |
|---|---|
| CUDA、unset | 無効。従来の CUDA recurrence を使う。 |
| CUDA、`atoi(value) == 0` | 無効。`0`、空文字、数値で始まらない文字列など。 |
| CUDA、`atoi(value) != 0` | chunked 経路を候補にする。負数も有効扱い。prompt chunk が 128 token 未満なら使わない。 |
| CUDA、`atoi(value) >= 2` | 上記に加え、128 SM 以上という条件を免除する。2 未満の非ゼロ値はこの条件を免除しない。 |
| HIP gfx11、unset / 空文字 | 未設定扱い（-1）となり、chunked 経路は無効。 |
| HIP gfx11、`atoi(value) == 0` | 無効。 |
| HIP gfx11、`atoi(value) != 0` | WMMA 経路を候補にする。gfx11 対応 arch、64 token 以上、出力 stride が 8 の倍数などを満たすと使用する。2 に CUDA のような特別な意味はない。 |
| HIP gfx12、unset / 空文字 | `STRATA_GFX12_DEFAULTS` が無効でなければ、`STRATA_GDN_CHUNKED_MIN` 以上の長さで自動選択する。 |
| HIP gfx12、`atoi(value) == 0` | 明示的に無効。自動選択もしない。 |
| HIP gfx12、`atoi(value) != 0` | 64 token 以上から明示的に有効候補。長さ自動閾値は適用しない。 |

CUDA の 128 token 最小値と `=2` の SM 条件緩和は `src/prefill/kernels.cu:1231-1252,934,3076-3137`、HIP の値解釈と 64 token・arch 条件は `src/prefill/kernels.cu:1832-1839,2133-2151,2173-2194,2975-2985` にあります。`STRATA_GDN_CHUNKED_MIN` の既定値は 30,000 で、空または未設定なら既定値、整数として変換できない文字列は 0 相当になります。負値にも clamp はありません。`STRATA_GFX12_DEFAULTS` は先頭文字が `0` のときだけ gfx12 自動選択を止め、それ以外（空文字を含む）は許可します。根拠: `src/prefill/kernels.cu:1836-1839`。

## 有効になる条件

### CUDA

- GDN recurrence の通常 dispatch（`src/prefill/kernels.cu:3070-3150`）で、`STRATA_GDN_CHUNKED` が非ゼロとして parse されること。通常の自動選択では、先に有効な `STRATA_GDN_TC` 経路が選ばれると chunked recurrence は呼ばれません。
- 入力長 `T >= 128`。
- GPU compute capability 8 以上、chunk scan に必要な shared memory があり、scratch allocation が成功すること。
- 既定では scan の 128 block が一度に載る SM 数（実装の `HK * (S / GDV)`）を満たすこと。`STRATA_GDN_CHUNKED` の `atoi()` 結果が 2 以上なら SM 数条件だけを省略します。architecture と shared memory の条件は残ります。
- 条件に合わない場合、通常の自動 dispatch は key-head、pipelined columns、または columns recurrence に fallback します。`STRATA_GDN_PIPELINE` は fallback kernel の選択に関係します。

### HIP

- `gdn_recurrence_impl()` の variant 0 または 1 で、`STRATA_GDN_REC_HEADS` が設定されていないこと。state-only recurrence も同じ dispatch を通ります。根拠: `src/prefill/kernels.cu:2971-2985,3194-3199`。
- WMMA 対応の gfx11 または gfx12 device。gfx11 の対象は gfx1100/1101/1102/1103/1150/1151、gfx12 は gfx12 WMMA 判定を満たす device です。実行中に device が変わる layer-split worker では、arch 判定は thread ごとの現在 device に応じて更新されます。根拠: `src/prefill/kernels.cu:1814-1816,2136-2151`。
- `T >= 64`、`ld16` が 8 の倍数。gfx12 ではさらに `T >= 64` を満たし、未設定時は `STRATA_GDN_CHUNKED_MIN` と `STRATA_GFX12_DEFAULTS` の gate も満たすこと。
- HIP gfx12 では `STRATA_GDN_FUSE` が未設定または非ゼロなら、chunked path が選ばれたとき conv と recurrence をまとめる経路も使えます。`STRATA_GDN_FUSE=0` では融合を止め、conv と recurrence を別々に呼びます。融合が使われない場合や GPU / 長さ / stride が条件外の場合、呼び出し元は従来の `gdn_conv()` と `gdn_recurrence()` に戻ります。根拠: `src/prefill/kernels.cu:2170-2210`, `src/prefill/prefill.cpp:4240-4254`。

サーバーの `serve/server.py` は Linux 上の `qwen4exp` HIP 設定で、可視 GPU がすべて gfx12 の場合、子プロセス環境に `STRATA_GDN_CHUNKED=1` を `setdefault` します。従って明示値や config の `env` が優先し、サーバー経由では未設定時の gfx12 長さ自動選択ではなく、64 token 以上の明示 opt-in として動きます。gfx11、CUDA、SYCL、Metal、Vulkan にはこの変数を自動設定しません。`child_env()` は親環境を複製して config の env を反映し、その後この helper を呼びます。根拠: `serve/server.py:4312-4341,4344-4361`。

## 実行時の詳細

CUDA は recurrence dispatch の初回評価時に `STRATA_GDN_CHUNKED` を static bool に保存します。chunked 経路に実際に入った場合、SM 数 bypass の値も別の static bool に保存されます。従って最初の評価後にプロセス環境を変更しても、このプロセスでは再評価されません。chunked recurrence は device ごとの scratch を初回利用時に確保し、以後保持します。根拠: `src/prefill/kernels.cu:1212-1224,1244-1249,3076-3078`。

HIP は `gdn_chunked_env()` の parse 結果を static に保持します。recurrence dispatch の chunked 判定も static で、gfx12 の長さ閾値と `STRATA_GFX12_DEFAULTS` も初回評価後に保持します。HIP の WMMA 経路は 16 token chunk で計算し、gfx11 では FP16 operand と FP32 accumulation を使います。gfx12 は同じ WMMA family の専用 kernel を呼びます。通常の CUDA recurrence は 32 token chunk scan を使い、scan の準備・計算 kernel を起動します。根拠: `src/prefill/kernels.cu:1832-1839,2131-2168,2195-2209,3076-3078`。

CUDA で適格条件を満たさなければ通常 dispatch が fallback するため、利用者向けの「chunked を使えなかった」ログはありません。gfx12 HIP の未設定かつ既定が許可される場合、Strata は起動時に `strata: RDNA4 (gfx12): prompt chunks of 30,000+ tokens use the chunked GDN scan (STRATA_GDN_CHUNKED=0 turns it off)` を stderr に出します。これは `apply_arch_defaults()` の診断で、実際にその長さの prompt が実行された証明ではありません。適用箇所は engine 起動時の `src/program/generate.cpp:3790-3807` です。選択後に kernel launch error があれば `prefill gdn_recurrence (chunked, WMMA): ...` または `prefill gdn_conv_recurrence_fused: ...` 形式を stderr に出し、`exit(1)` します。通常 CUDA の chunked dispatch は条件不足なら fallback し、失敗理由を利用者ログには出しません。根拠: `src/prefill/kernels.cu:102-105,2981-2983,3152-3164,2209`。

## 文書との照合

`docs/DETAILS.md:1079` は CUDA の 128 SM 条件と `=2` の例外、HIP gfx11 対応、chunk 長と丸めの違いを説明しています。`docs/AMD_HIP.md:307-319` は gfx11 を opt-in とし、64 token 条件、出力 stride と `STRATA_GDN_REC_HEADS` による fallback を記載しています。対象 commit のコードには gfx12 の追加経路があり、未設定なら gfx12 で `STRATA_GFX12_DEFAULTS` と `STRATA_GDN_CHUNKED_MIN` に従った長さ gate が有効です（`src/prefill/kernels.cu:1823-1839,2150-2151`; 起動ログは `src/core/arch_defaults.cpp:270-273`）。また gfx12 サーバー設定は値 `1` を子プロセスに追加するため、エンジン単体の未設定時の gate とは異なります（`serve/server.py:4325-4341`）。

## 根拠

- 値 parse、gfx11/gfx12 の閾値・自動選択: `src/prefill/kernels.cu:1814-1839,2131-2168`。
- gfx12 融合と fallback の呼び出し: `src/prefill/kernels.cu:2170-2210`, `src/prefill/prefill.cpp:4240-4254`。
- CUDA parse、GPU eligibility、fallback: `src/prefill/kernels.cu:1212-1252,3070-3164`。
- gfx12 起動ログと arch defaults 呼び出し: `src/core/arch_defaults.cpp:231-273`, `src/program/generate.cpp:3790-3807`。
- server の子環境設定: `serve/server.py:4312-4361`。
