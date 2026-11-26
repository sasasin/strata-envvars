# `STRATA_PF_OCC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の fused prompt-expert kernel が使う persistent grid の上限を、WGP あたりの block 数で指定する実験用設定です。値が正なら occupancy API から得た既定 block 数の代わりにその値を使います。変わるのは gate/up と down の grid 上限で、タイル数、kernel の算術処理自体を切り替える設定ではありません。Q2_0 pack の gfx11 kernel と native pack の HIP kernel が読み取り、Qwen3.6 用 native pack copy にも同じ native 実装が含まれます（`engine/src/prefill/moe_fused.cu:635-647,771-789`; `engine/src/prefill/moe_fused_iq.cu:2813-2825,3774-3780`; `engine/src/prefill/moe_fused_iq_q36.cu:1-6,33-37,168-175`）。

## 値と判定

読み取りは `std::getenv` の戻り値を `std::atoi` に渡し、結果が `> 0` かを判定します。文字列全体の数値検証はありません。未設定は `0` 扱い、空文字・数値に変換できない文字列も `atoi` が `0` を返すため既定値に戻ります。先頭の空白と符号は `atoi` の整数変換規則に従い、数値の後ろにある非数字は変換を止めます。大文字小文字の比較はありません（`engine/src/prefill/moe_fused.cu:641-647`; `engine/src/prefill/moe_fused_iq.cu:2819-2825`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 既定値へ戻る値（例） |
|---|---|---|---|
| HIP の `wgp_blocks()` を使う経路 | unset は `env=0`。空文字も `atoi` が `0` | `1`, `2`, `+3`, ` 4`, `5anything` は正の整数として変換され、その数を使用 | `0`, `0anything`, `-1`, `true`, `  ` は `env <= 0` となり既定値を使用 |
| CUDA build | この名前の読み取り箇所なし | 該当なし | 該当なし |

正値は grid の block 上限に使われますが、実際の grid は `min(処理 tile 数, device の multiprocessor 数 × block 数)` です。したがって値を増やしても、処理 tile 数を超える grid にはなりません。`atoi` の整数範囲を超える文字列の結果はこのコードでは検査・規定していません（`engine/src/prefill/moe_fused.cu:778-781`; `engine/src/prefill/moe_fused_iq.cu:3774-3777`）。

## 有効になる条件

- **HIP build であること。** `wgp_blocks()` とその環境読み取りは `#if defined(__HIPCC__)` 内だけにあります。CUDA 側の `experts()` は occupancy API の `d.occ_gu` / `d.occ_d` をそのまま grid に使い、この名前を読みません（`engine/src/prefill/moe_fused.cu:635-648,779-789`; native pack の HIP/CUDA build も同ファイル `:2813-2825,2847-2886`）。HIP build の fused prompt kernel source には両実装と Qwen3.6 copy が含まれます（`engine/cmake/backends/hip.cmake:30-42`）。
- **Q2_0 pack:** gfx11 WMMA 対応 device で `dev_info()` が kernel 属性と occupancy を確認し、`d.cc` が利用可能を示す必要があります。そこで `experts()` に進む場合、gate/up と down の grid にこの値が使われます。HIP の gfx12 ではこの Q2_0 pack kernel の対象条件を満たしません（`engine/src/prefill/moe_fused.cu:660-675,771-783`）。
- **Native pack:** `dev_info()` が gfx11 または gfx12 の WMMA 対応 kernel を確認して `d.ok` を立て、上流が当該層を native fused 経路に選ぶ必要があります。上流の選択には `STRATA_PF_FUSED` / `STRATA_PF_FUSED_NATIVE`、layer format、stream-all、MMQ/fused-only 状態なども関与します。この変数単独で native 経路を有効にはしません（`engine/src/prefill/moe_fused_iq.cu:2858-2885,3415-3432`; `engine/src/prefill/prefill.cpp:5692-5704`）。
- Native pack のうち `occ_gu` / `occ_d` が true の occupancy variant は `occ_blocks()` を使うため、`STRATA_PF_OCC` はその grid に適用されません。通常の variant は `wgp_blocks()` を使います。`STRATA_PF_KQ_OCC=1` は K-quant の対象 kernel を occupancy variant に含めます。`STRATA_W_NO_OCC` build では occupancy variant 自体を止めるため、該当 grid は `wgp_blocks()` 側になります（`engine/src/prefill/moe_fused_iq.cu:2832-2845,3754-3777`）。
- Qwen3.6 native copy は `moe_fused_iq.cu` を別 namespace で include し、同じ native `wgp_blocks()` 判定を持ちます。Qwen3.6 の該当 fused 呼び出しは `experts_native_ext()` 経由です（`engine/src/prefill/moe_fused_iq_q36.cu:33-37,148-175`; caller `engine/src/qwen35/q36_engine.cu:2966`）。

## 実行時の詳細

環境値はプロセス起動時ではなく、各コンパイル済み `wgp_blocks()` の最初の呼び出しで関数内 `static const int` として一度読み、以後そのコピー内で cache します。Q2_0 pack、通常の native pack、Qwen3.6 copy は別 translation unit / include copy なので、それぞれ独立した static cache を持ちます。読み取り後にプロセス環境を書き換えても、その cache の値は更新されません（`engine/src/prefill/moe_fused.cu:641-647`; `engine/src/prefill/moe_fused_iq.cu:2819-2825`; Qwen3.6 の include は `engine/src/prefill/moe_fused_iq_q36.cu:33-37`）。

Q2_0 pack は grid 上限を `d.sms * wgp_blocks(d.occ_gu/occ_d)` とし、native pack は occupancy variant でない gate/up/down に `d.sms * wgp_blocks(d.occ)` を使います。いずれも処理 tile 数との小さい方を launch grid にします（`engine/src/prefill/moe_fused.cu:778-783`; `engine/src/prefill/moe_fused_iq.cu:3774-3780`）。Qwen3.6 copy も同じ式で native grid を作ります（`engine/src/prefill/moe_fused_iq_q36.cu:165-175`）。

コードコメントには gfx1151（20 WGP）、8192 tokens × top 10、IQ3_S / IQ4_NL、1 layer の記録として、1/2/3/4 blocks per WGP でそれぞれ 60.7 / 44.7 / 49.9 / 45.2 ms とあります。また同じ work items と算術で結果は変わらないと記されています。これはソースコメント上の一条件の測定記録であり、今回実測した結果ではありません（`engine/src/prefill/moe_fused.cu:636-640`; native pack の同記述 `engine/src/prefill/moe_fused_iq.cu:2814-2818`）。

## ログと測定値

この変数の読み取り値や grid 上限を出す専用ログ・警告はありません。Q2_0 pack の launch 後に CUDA/HIP runtime error を検出すると、stderr に `prefill fused experts: experts: <error>` の形式で出して終了コード 1 になります（`engine/src/prefill/moe_fused.cu:37-41,791`）。Native pack は同様に `prefill fused experts (native): <処理名>: <error>` を出して終了コード 1 で終了します（`engine/src/prefill/moe_fused_iq.cu:68-72`）。上記の条件付き時間はソースコメントの記録です。`docs/DETAILS.md` にこの変数の追加測定値は見つかりませんでした。

## 根拠

- `engine/src/prefill/moe_fused.cu:635-647,660-675,771-791` — HIP 専用の値読み取り、device 条件、Q2_0 pack の launch grid とエラー処理。
- `engine/src/prefill/moe_fused_iq.cu:2813-2825,2832-2845,2847-2886,3754-3780` — native pack の値読み取り、occupancy variant との分岐、HIP device 条件、launch grid。
- `engine/src/prefill/moe_fused_iq_q36.cu:1-8,33-37,148-175` — Qwen3.6 copy と native launch。
- `engine/src/prefill/prefill.cpp:5692-5704`; `engine/src/qwen35/q36_engine.cu:2966` — 通常 prompt / Qwen3.6 からの呼び出し条件。
- `engine/cmake/backends/hip.cmake:30-42` — HIP build のソース登録。
