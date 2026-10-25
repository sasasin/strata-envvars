# `STRATA_GFX906_ATTN_REDUCE12_TRACE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

gfx906 向け QSA batched attention の reduce12 カーネルが選択されたことを、呼び出しスレッドごとに一度 stderr へ記録します。計算を有効化するスイッチではなく、ログだけを制御します。reduce12 の選択そのものは別の `STRATA_GFX906_ATTN_REDUCE12` が担います。

## 値と判定

`qsa_decode_attn_batch()` 内の分岐で `std::getenv()` を呼び、取得文字列がちょうど1文字の `"1"` の場合だけ true とします。数値変換や trim、大文字小文字変換はありません。

| 値 | trace |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `10`, `01`, `true`, `0`, その他 | 無効 |

判定は関数内の `static const bool` にキャッシュされます。ただしこの変数の初期化箇所は reduce12 分岐の内側なので、swizzle と reduce12 の条件を満たしてコードが初めてそこへ到達した時点で読み取ります。その初回判定後にプロセス環境を変えても値は再評価されません。

根拠: `src/kernels/cuda/qsa_decode_attn.cu:660-680`。

## 有効になる条件

この処理は `STRATA_HIP_GFX906` 定義時にだけコンパイルされる gfx906 HIP 互換 backend のコードです。通常の CUDA build や wave32 HIP build には当該読み取り・ログ分岐が含まれません。CMake では `STRATA_HIP_GFX906=ON` が CUDA source 群を HIP としてコンパイルし、同 macro を定義します。

さらにログ分岐に到達するには、次の全条件が必要です。

- `STRATA_GFX906_ATTN_QUERY_SWIZZLE` の先頭文字が `1`。
- lane-cell scoring が無効（`STRATA_ATTN_LANECELL` の先頭文字が `1` ではない）。
- KV pool mode が INT8 の `kv_mode == 1`。
- 呼び出しスレッドの現在の GPU が gfx906 で、wave/warp size が64。
- `STRATA_GFX906_ATTN_REDUCE12` の文字列全体が `"1"`。
- `STRATA_GFX906_ATTN_REDUCE12_TRACE` の文字列全体が `"1"`。

これらを満たさない場合、この変数だけを設定してもログは出ません。特に親の swizzle 条件が偽なら reduce12 用カーネル選択自体がなく、trace の static 初期化にも到達しません。

根拠: `src/kernels/cuda/qsa_decode_attn.cu:637-645,660-687`。build 条件: `CMakeLists.txt:64-70,122-138,1643-1653`。

## 実行時の詳細

親条件が満たされ、reduce12 が選択されると `attn_chunk_kernel<1, false, true, true>` を launch した後に trace 値を確認します。有効なら、そのホスト側呼び出しスレッドで最初の一度だけ次の行を stderr に出します。

```text
strata attn-reduce12: selected=1 query_swizzle=1 kv_mode=1 nq=<n_q> cap=<cap>
```

抑制フラグは `static thread_local bool said` です。そのため一度のプロセス実行で必ず一行という意味ではなく、条件を満たす呼び出しを行った各ホストスレッドにつき一行です。CUDA/HIP stream 上のカーネル完了や正確性、性能値を測るログではありません。エラー時の終了・fallbackをこの trace 変数は変更しません。

`qsa_decode_attn_batch()` は prompt prefill、verification、MTP の batched attention 経路から呼ばれます。通常の単一-query `qsa_decode_attn_step()` は別関数で、この分岐を通りません。prompt では prompt attention tensor 経路が成功すると decode-batch 経路を使わない場合があります。

根拠: `src/kernels/cuda/qsa_decode_attn.cu:674-683,716-750`; 呼び出し例: `src/prefill/prefill.cpp:2843-2850`, `src/core/verify.cpp:1367-1393`, `src/core/mtp.cpp:823-826`。

## 文書との照合

`docs/AMD_HIP.md:465-472` は gfx906 build と、`STRATA_GFX906_ATTN_QUERY_SWIZZLE=1` および `STRATA_GFX906_ATTN_REDUCE12=1` が opt-in で、この build にだけコンパイルされることを説明しています。trace 変数自体の説明や測定値は資料に見当たりません。コード上もこの変数は診断出力にのみ作用するため、速度・数値精度を変える設定とは確認できません。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:660-687` — gfx906 batched attention の条件、reduce12 選択、trace 判定と stderr 文言。
- `src/kernels/cuda/qsa_decode_attn.cu:716-750` — 単一-query step 関数は対象 trace 分岐の外。
- `CMakeLists.txt:64-70,122-138,1643-1653` — gfx906 backend の build option と CUDA source の HIP 化。
- `docs/AMD_HIP.md:465-472` — gfx906 build と関連 opt-in 変数についての説明。
