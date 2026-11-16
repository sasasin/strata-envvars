# `STRATA_PF_KQ_OCC`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP の fused native MoE prefill 経路で、K-quant の Q4_K / Q5_K gate-up と Q5_1 down も occupancy 型の `native_w11_kernel` launch に参加させる試験用スイッチです。通常の値（未設定または先頭文字が `1` でない値）では、これらの K-quant 型は `occ_gu` / `occ_d` の対象にならず、通常 launch を使います。スイッチが有効な場合、該当 launch の grid 上限は `occ_blocks(...)` が返す WGP あたり 3 block に基づいて計算されます。値の読み取り自体は HIP コンパイル時だけで、CUDA build にはこの分岐がありません（`src/prefill/moe_fused_iq.cu:3149-3167`, `2364-2377`）。

これは K-quant の fused 経路を選ぶスイッチではありません。K-quant layer が native fused prefill に選ばれている必要があり、HIP では `STRATA_PF_FUSED=1` と `STRATA_PF_FUSED_KQ=1` が必要です。ただし Windows gfx1151 では後者を未設定にした場合、`STRATA_GFX1151_DEFAULTS=0` でなければ KQ の既定選択が有効になるコードがあります（`src/prefill/moe_fused_iq.cu:2532-2551`, `2891-2908`, `2954-2957`, `3019-3039`）。

## 値と判定

`experts_native(const Batch&, ...)` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度呼び、環境変数が存在し、かつ値の先頭 byte が文字 `'1'` なら true とします。文字列全体、数値としての妥当性、空白、大文字小文字は検査しません。空文字は設定済みでも先頭が NUL なので false です。たとえば `1`, `1anything`, `10` は true、`0`, `true`, ` 1`, 空文字、未設定は false です（`src/prefill/moe_fused_iq.cu:3152-3158`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| HIP build、`STRATA_W_NO_OCC` 未定義 | false | `1`, `1x`, `10` | 空文字, `0`, `true`, ` 1` |
| `STRATA_W_NO_OCC` 定義 build | 読み取りなし。occupancy variant は常に無効 | なし | すべて（この変数は分岐から除外） |
| CUDA build | 読み取りなし | なし | すべて（HIP 専用分岐の外） |

## 有効になる条件

- HIP build であること。CUDA は `experts_native` の別実装に進み、この変数を読まない（`src/prefill/moe_fused_iq.cu:3131-3159`）。
- `STRATA_W_NO_OCC` が build macro として定義されていないこと。同 macro があると `occ_gu` と `occ_d` はともに false に固定され、環境変数の読み取り行もコンパイルされません（`src/prefill/moe_fused_iq.cu:3149-3159`）。
- 呼び出しが空でない `Batch` であり、device と型が native 経路で有効なこと。空 batch / `n <= 0` は先に戻り、device・型が未対応なら `prefill fused experts (native): types %d / %d are not covered here` を stderr に出して終了します（`src/prefill/moe_fused_iq.cu:3114-3127`）。HIP の device 判定は gfx11 / gfx12 の native WMMA body が実在し、属性取得も通ることを確認して `d.ok` を立てます（`src/prefill/moe_fused_iq.cu:2390-2414`）。
- K-quant layer が native fused 経路に選ばれること。`STRATA_PF_FUSED_NATIVE=0` または fused 全体の実効値が 0 なら `native_supported` は false です。K-quant gate-up は `kq_on()` が true のとき covered となり、down は Q5_1（または別条件を満たす Q8_0）でなければなりません。HIP の一般的な既定形式一覧に K-quant は含まれないため、通常は `STRATA_PF_FUSED=1` の明示が必要です。`STRATA_PF_FUSED_KQ=1` で KQ を要求し、Windows gfx1151 では同変数未設定時に `STRATA_GFX1151_DEFAULTS=0` が既定を無効化します（`src/prefill/moe_fused_iq.cu:2532-2551`, `2564-2590`, `2689-2700`, `2891-2908`, `2954-2957`, `3015-3039`）。
- `STRATA_PF_F16=1` が gfx11 で有効な場合、Q4_K / Q5_K gate-up と Q5_1 down は `moe_f16_kq.cu` の別 kernel に送られ、ここで計算した occupancy grid を使いません。この変数を設定しても、その K-quant work の occupancy launch は有効になりません（`src/prefill/moe_fused_iq.cu:3171-3187`, `3220`; `src/prefill/moe_f16_kq.cu:308-310`）。
- `STRATA_PF_FUSED_NT` / warp-specialized 経路は K-quant pair を native-supported 対象から除外します。`STRATA_W_NO_OCC` は上記の通り occupancy variant 自体を抑止します（`src/prefill/moe_fused_iq.cu:2954-2957`, `3149-3159`, `3348-3358`）。

## 実行時の詳細

`experts_native` は空 batch 判定と device / format coverage の確認後、HIP 分岐内で occupancy 対象を決めます。`kq_occ` は関数ローカル static のため、最初にこの箇所へ到達した時に一度だけ読み込まれ、そのプロセス内では以後の環境変更は反映されません。K-quant 対象は gate-up が Q4_K または Q5_K、down が Q5_1 です（`src/prefill/moe_fused_iq.cu:3114-3159`）。

有効なとき、grid は `min(tiles × work-items-per-tile, d.sms × occ_blocks(...))` で上限付けされます。Q4_K / Q5_K / Q5_1 に対する `occ_blocks` の既定分岐は 3 block / WGP です。occupancy variant は H tile を weight buffer 上に alias する kernel instance を選び、VGPR cap は `nw_capped` の build・architecture 条件に従います。通常 launch との違いは grid と kernel variant であり、環境変数が生成値や token 選択を直接変更する処理はこの箇所にありません（`src/prefill/moe_fused_iq.cu:2364-2377`, `3144-3170`, `3170-3219`）。

K-quant occupancy launch の後は `cudaGetLastError()` を `ck(..., "experts_native")` に渡し、成功時に戻ります。コード上、変数自体に対する警告・ログはありません。HIP の fused path で pair が未対応なら `native_supported` が false となり、この native launch に選ばれません（`src/prefill/moe_fused_iq.cu:3235-3243`, `2891-2908`, `2954-2957`）。

## ログと測定値

変数の値や occupancy 選択を知らせる専用ログはありません。ソースコメントには gfx1201 / Radeon AI PRO R9700、`hip_prefill_fused_iq`、1 layer、8,192 tokens × top 10、512 experts の測定として、Q4_K / Q5_1 の prompt kernel 時間が default 16.57 ms、4 blocks 15.96 ms、3 blocks 15.54 ms、2 blocks 16.52 ms、Q5_K / Q5_1 がそれぞれ 17.25 / 16.69 / 16.20 / 17.18 ms とあります。同コメントは parity と出力が変わらなかったとも記しています。これはソースコメントに記載された条件付き値であり、別環境への一般化はできません（`src/prefill/moe_fused_iq.cu:2372-2375`）。

## 根拠

- 読み取りと K-quant 型への適用: `src/prefill/moe_fused_iq.cu:3149-3159`
- grid と occupancy variant の launch: `src/prefill/moe_fused_iq.cu:2364-2377`, `3160-3170`, `3200-3238`
- HIP device・KQ pair の選択条件: `src/prefill/moe_fused_iq.cu:2390-2414`, `2532-2551`, `2564-2590`, `2689-2700`, `2891-2908`, `2954-2957`, `3015-3039`
- gfx11 F16 K-quant launch: `src/prefill/moe_fused_iq.cu:3171-3187`, `3220`; `src/prefill/moe_f16_kq.cu:308-310`
