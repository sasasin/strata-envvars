# `STRATA_PF_FUSED_Q50`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP のネイティブ fused prompt-expert 経路において、Q5_0 の down projection を fused kernel で処理できるようにします。対象は gfx12 (RDNA4) の int8 `native_w11_kernel` と、gfx1151 (Strix Halo) の F16 `native_f16_kernel` です。どちらも Q5_0 down 専用の選択で、ほかの形式や CUDA ビルドには作用しません (`src/prefill/moe_fused_iq.cu:1936-1967,2137-2144,2180-2189`)。

この変数だけでは fused prompt 経路全体を有効にしません。native pack の fused 経路を選ぶ `STRATA_PF_FUSED=1` が必要です。モデルの層形式、デバイス、MMQ の対応状況などにより native fused 経路が選ばれない場合も、この変数の指定だけでは経路は切り替わりません (`src/prefill/moe_fused_iq.cu:2041-2085`; `src/prefill/prefill.cpp:1534-1555`)。

## 値と判定

`q50_on()` は `std::getenv()` の結果を文字列全体として parse せず、未設定・空文字かどうかと、設定値の先頭文字だけを判定します。判定値は関数内の `static const int` に保存されます (`src/prefill/moe_fused_iq.cu:1943-1958`)。

| 値 | `q50_on()` の結果 |
|---|---|
| 未設定 | デバイスと OS の既定値に従う |
| 空文字 | 未設定と同じ。明示的な OFF にはならない |
| 空でなく先頭が `1` | ON。`1`, `10`, `1anything` など。以降の文字は見ない |
| それ以外の空でない値 | OFF。`0`, `0anything`, `true`, ` 1` など |

大文字小文字や数値としての妥当性は検査しません。たとえば `true` は ON ではなく OFF です。空文字を除く `1` 以外の値は一律 OFF です。

未設定・空文字の場合の既定値は次のとおりです。

| HIP 実行デバイス | OS / 他の条件 | 既定値 |
|---|---|---|
| gfx12 (RDNA4) | OS を問わない | OFF |
| gfx1151 (Strix Halo) | Windows、かつ `STRATA_GFX1151_DEFAULTS` の先頭が `0` でない | ON |
| gfx1151 (Strix Halo) | Linux、または `STRATA_GFX1151_DEFAULTS` の先頭が `0` | OFF |
| 上記以外 | OS を問わない | OFF |

`STRATA_GFX1151_DEFAULTS` は、この変数が未設定または空文字で gfx1151 の既定値を決める場合にだけ参照されます。先頭文字が `0` なら既定値を OFF にし、それ以外の設定値は既定値を OFF にしません。`STRATA_PF_FUSED_Q50` 自体に有効な非空値がある場合はその判定が先に返るため、明示値が優先します (`src/prefill/moe_fused_iq.cu:1946-1954`)。

## 有効になる条件

実際に Q5_0 fused down kernel が対象層で使われるには、少なくとも次の条件が必要です。

- HIP ビルドであること。`q50_on()` の CUDA 側は常に `false` を返します (`src/prefill/moe_fused_iq.cu:1943-1958`)。
- デバイスが gfx12 WMMA または gfx1151 と認識され、native kernel が利用可能 (`DevInfo::ok`) であること。その他の gfx11 / gfx12 デバイス、HIP の gfx906、対応 kernel が build にない場合は対象外です (`src/prefill/moe_fused_iq.cu:1688-1699,1794-1823`)。
- native pack の gate/up 形式が `gu_covered()` の対象であること。具体的には IQ2_XXS, IQ2_XS, IQ2_S, IQ3_XXS, IQ3_S, IQ4_XS で、HIP では追加で gfx12 の Q2_0、または `kq_on()` が有効な場合の Q4_K / Q5_K です (`src/prefill/moe_fused_iq.cu:1901-1910`)。
- `STRATA_PF_FUSED=1` により native pack の fused prompt 経路が要求されていること。native pack の `native_supported()` は HIP でこの変数が未設定なら gfx12 の一部既定経路だけを認め、Q5_0 down は `q50_on()` が既定 OFF なので対象になりません。gfx1151 の Q5_0 down も `STRATA_PF_FUSED=1` がないと選択されません (`src/prefill/moe_fused_iq.cu:2041-2085`)。
- gfx1151 の場合は `STRATA_PF_F16` が先頭文字 `1` であること。未設定、空文字、`0`、`true` などは F16 経路を無効にし、Q5_0 down は native coverage 外になります。gfx12 はこの F16 条件を使わず int8 kernel を使います (`src/prefill/moe_f16_common.cuh:53-60`; `src/prefill/moe_fused_iq.cu:1960-1967,2137-2144`)。
- fused 経路を使う対象層・prompt であること。prefill の計画では MMQ の両 projection が対応している層は MMQ に割り当てられ、MMQ が対応しない native 層などで `native_supported()` が真なら native fused に割り当てます。したがって、変数を ON にしてもすべての Q5_0 層が必ず fused になるわけではありません (`src/prefill/prefill.cpp:1534-1555`)。

上記条件を満たさなければ、この環境変数に関する専用の警告や fallback ログはありません。上位の計画が native fused を選ばなければ既存の MMQ または dequantize + FP16 GEMM 経路になります (`src/prefill/prefill.cpp:1548-1555`)。native kernel 内部の coverage 検査に到達したにもかかわらず型が対象外なら、stderr に `prefill fused experts (native): types %d / %d are not covered here`（wide batch では `prefill fused experts (native, NT = 256): types %d / %d are not covered here`）を出し `exit(1)` します (`src/prefill/moe_fused_iq.cu:2100-2108,2227-2235`)。

## 実行時の詳細

環境値は `q50_on()` が最初に呼ばれた際に一度読み取られ、プロセス内で cache されます。その後に環境を変更しても `STRATA_PF_FUSED_Q50` の判定は更新されません。gfx1151 の既定値を決める `STRATA_GFX1151_DEFAULTS` は、Q50 の値が未設定扱いの場合に `q50_on()` 内で参照されます。`STRATA_PF_F16` も別の関数内で static cache されます (`src/prefill/moe_fused_iq.cu:1943-1954`; `src/prefill/moe_f16_common.cuh:53-60`)。

Q5_0 down の coverage 判定は、gfx12 なら `q50_on()` の結果、gfx1151 なら同結果と `f16::requested()` の両方を要求します。native fused を選んだ gfx12 は `native_w11_kernel<T_Q5_0, false>` を起動し、gfx1151 は F16 分岐から `native_f16_kernel<T_Q5_0, false>` を起動します (`src/prefill/moe_fused_iq.cu:1960-1967,2137-2144,2180-2189`)。

候補一覧 `docs/envvars/000_envvers.md` に名前はあります。Strata 全体を対象名で検索した結果、実装上の環境読み取りは `src/prefill/moe_fused_iq.cu:1946` のみでした。他の一致は同ファイルの説明コメントと `tests/cuda/prefill_fused_iq_test.cpp:660,698` のテスト専用コードです。名前を動的に渡して読む helper は見つかりませんでした。テストの設定例は、本番動作の根拠には用いていません。

## 根拠

- 読み取り・値判定・既定値: `src/prefill/moe_fused_iq.cu:1936-1958`
- 対応する GPU と HIP build 条件: `src/prefill/moe_fused_iq.cu:1688-1699,1794-1823,1943-1958`
- gate/up と down の coverage 判定: `src/prefill/moe_fused_iq.cu:1901-1918,1960-1967`
- native pack の fused 要求と条件: `src/prefill/moe_fused_iq.cu:2041-2085`
- gfx1151 F16 選択・Q5_0 kernel 起動: `src/prefill/moe_f16_common.cuh:53-60`; `src/prefill/moe_fused_iq.cu:2137-2189`
- prefill の層別選択と通常 fallback: `src/prefill/prefill.cpp:1534-1555`
- 実行時の coverage 失敗と終了: `src/prefill/moe_fused_iq.cu:2100-2108,2227-2235`

実装とコメントの差: `src/prefill/moe_fused_iq.cu:1939-1942` のコメントは `STRATA_GFX1151_DEFAULTS=0` が機能を OFF にするとしていますが、実際の `q50_on()` は明示された非空 `STRATA_PF_FUSED_Q50` を先に処理して返します。そのため `STRATA_PF_FUSED_Q50=1` があれば `STRATA_GFX1151_DEFAULTS=0` はそれを無効化しません。これはコメントと現行コードの差として記録しています。
