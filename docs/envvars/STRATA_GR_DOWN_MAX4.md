# `STRATA_GR_DOWN_MAX4`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

fused GR の multi-token read に含まれる down projection で、1回の launch が4 token 以下のとき、1 thread が保持する token ごとの累積値の配列幅を既定の `kFusedGrMaxT`（8）から4にする opt-in です。CUDA/HIP の `gr_down_multi_kernel` / `gr_down_staged_kernel` と、SYCL 移植版の同等 kernel で使われます。launch の token 数、norm/up projection、重みや計算式そのものはこの変数では変えません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定） |
| 空文字、`0`、`false`、数字で始まらない文字列 | `atoi` の結果が0になり、無効 |
| `1`、`2`、`-1`、` 1x` など、先頭の空白の後に非0の整数を読める文字列 | 有効 |

全体一致ではなく `std::atoi` の結果を使います。したがって `1xyz` は1として有効、`0xyz` は0として無効です。`atoi` が整数として読めない文字列は0になります。整数の表現範囲を超える入力については、この実装から定義された挙動を保証できません。

CUDA/HIP では `gr_down_max4()` の関数内 static に、SYCL では `launch_multi()` の関数内 static に判定結果が保存されます。各プロセスで最初にその判定に到達した後に環境を変更しても、結果は再評価されません。

## 有効になる条件

- fused GR の `fused_gr_read_multi()` が実行され、既定の `launch_multi()` 経路に到達する必要があります。
- CUDA/HIP では、Q8 down/up の読み取り経路は先に別の `launch_q8()` に分岐して戻るため対象外です。また `STRATA_GR_V3` が利用可能な二段読み取りを選んだ場合も対象外です。gfx906 HIP で `STRATA_GR_SPLIT=1` が選ばれた場合も別の split kernel 経路になります。V3 が設定されていても、そのデバイスで V3 が使えず既定経路へ fallback すれば、この変数が判定されます。
- down projection の各 launch の token 数 `ct` が4以下の場合だけ有効です。デバイスの shared-memory / local-memory 容量に応じて `down_chunk()` が batch を分けるため、判定対象は元の batch 数ではなく分割後の `ct` です。`ct` が5以上の launch は従来どおり `kFusedGrMaxT` 幅です。
- CUDA/HIP の staged kernel では、`STRATA_NO_MULTI_GR` が無効（通常の既定）なら `exact_t` kernel の分岐が `max4` より先に選ばれます。この場合 `STRATA_GR_DOWN_MAX4` は staged 経路の kernel 選択に反映されません。`STRATA_NO_MULTI_GR` が有効なら staged 経路でも `ct <= 4` の `max4` kernel を選べます。non-staged CUDA/HIP 経路と SYCL の staged/non-staged 経路では、この `exact_t` 優先分岐はありません。
- ビルド・実行時に fused GR 経路が呼ばれないケースには影響しません。

## 実行時の詳細

CUDA/HIP の `launch_multi()` は `ct <= 4` かつ変数が有効なとき、down projection のテンプレート引数 `MAX_T` を4にした kernel を選びます。non-staged では `TILEV` が1280か2560かに応じた kernel、staged では4 token用 kernelを起動します。CUDA/HIP の staged `exact_t` 分岐が優先される条件は上記のとおりです。SYCL 版は `ct <= 4` かつ有効なら、同様に `MAX_T=4` の staged または non-staged down kernel を submit します。

通常経路では down kernel の `MAX_T` は累積値配列の幅です。実際に加算・出力する token は `T`（実際の launch 数）で制限されます。カーネル内の tile、block size、各 token の加算順序は同じであると実装コメントに記されています。norm/up の後続処理は通常どおり続きます。この変数専用のログ出力はありません。CUDA/HIP の `fused_gr_read_multi()` には kernel launch error を stderr に出す既存処理がありますが、この変数を有効にしたことを示すログではありません。

## 文書・測定資料

`docs/DETAILS.md` にはこの変数の個別説明は見つかりませんでした。`docs/INTEL.md` は SYCL port で opt-in とし、B70 での測定を prompt 2,184 tokens: 793 vs 788 tok/s、decode: 76.2 vs 76.3 tok/s と記しています。これは同資料のその測定条件での数値です。CUDA ソースの注釈は RTX 5070・Q2_0・default config の10組 interleaved decode A/B では改善が見えず（有効側 median が無効側の0.97–0.99）、既定 off としたと説明しています。両者は異なる環境・測定であり、一般的な性能差を示すものではありません。

## 根拠

- `src/kernels/cuda/fused_gr.cu:264-316,810-880` — CUDA/HIP down kernel のテンプレート幅と token ごとの累積・出力。
- `src/kernels/cuda/fused_gr.cu:995-1004,1030-1089` — `atoi` 判定、static cache、`ct <= 4` の kernel 選択と staged の `exact_t` 優先分岐。
- `src/kernels/cuda/fused_gr.cu:903-981,1830-1962` — launch ごとの chunk 数、Q8/V3/gfx906 split の分岐と既定経路への fallback、launch error の報告。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1375-1563,1607-1662,1755-1760` — SYCL での判定、kernel 選択、および V3 分岐。
- `docs/INTEL.md:638-640` — SYCL port の opt-in と B70 測定値。
