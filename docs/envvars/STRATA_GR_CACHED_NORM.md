# `STRATA_GR_CACHED_NORM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata 側の作業ツリーは `main...origin/main` で変更なし。

## 役割

SYCL backend の fused hyper-connection read で、RMS 正規化済み activation を後段の up projection で再利用する opt-in 制御です。`STRATA_GR_CACHED_NORM` 自体の既定値は OFF です。値を ON にしても、Battlemage と複数の kernel/layout 条件を満たした場合にだけ再利用フラグが立ちます。

## 値と判定

`strata::bm_default_on()` は環境変数が非空なら先頭文字だけを調べ、`'0'` 以外で ON とします。空文字と未設定は helper の既定値に戻ります。この変数の helper 呼び出しでは既定値に `false` を渡すため、どちらも OFF です。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF（既定値へ戻る） |
| `0`, `0anything` | OFF |
| `1`, `10`, `true`, `false`, 空白で始まる文字列など、先頭が `0` 以外の非空値 | ON |

数値変換や文字列全体の比較はありません。したがって `false` も先頭が `f` のため ON です。大文字小文字や後続文字は判定に影響しません。

## 有効になる条件

対象コードは `sycl/src/kernels/cuda/fused_gr.dp.cpp` の SYCL fused hyper-connection 実装です。さらに、すべての条件が必要です。

- `fused_gr_read_multi()` の通常の kernel 経路まで到達する。`STRATA_GR_V3` が有効で device の local memory に合う split が選ばれると、別の二 kernel 経路で先に return するため、この変数はその呼び出しで評価されません。
- `gr_norm_split()` と `gr_down_sliced()` が true。どちらも unset を既定 ON とし、設定時は `atoi(value) != 0` で判定します。
- `gr_more_groups()` と `gr_large_grf()` が false、`gr_up_ilp()` が false。
- `gr_up_cols() == UPM_COLS`（この実装の `UPM_COLS` は 16）。
- 実行 device が Intel Battlemage。
- `gr_reuse_safe()` が true。scratch の `xn` が各 token の入力・出力・weight・その他の領域、および `lo` 領域と重ならないことを確認します。

いずれかの条件を満たさないと `m.cached_norm` は初期値 false のままで、この変数による再利用は起きません。ここで列挙した別設定は独立した条件です。特に norm split と sliced down はこの実装で既定 ON ですが、それぞれの値は当該 helper の規則に従います。

## 実行時の詳細

値は `fused_gr_read_multi()` が上記の通常経路に初めて到達したときに読み込まれ、関数内の `static const bool` に保存されます。プロセス内で後から環境を変更しても再評価されません。helper は Battlemage かどうかも調べますが、この変数では `bm_default=false` のため、未設定・空文字を Battlemage が既定 ON にすることもありません。

条件を通ると `m.cached_norm` に判定結果を設定し、norm split kernel が `R * w_norm` に RMS inverse scale を掛けた値を `xn` scratch に書きます。再利用 kernel は `m.cached_norm` が true の場合、up projection の epilogue で再び `R`・norm weight・scale を読み、正規化値を計算する代わりに `m.xn` を使います。`apply` が必要な token は先に `R` を更新します。コードはこの経路の数値同一性や性能値をこの環境変数の説明として保証していません。

条件を満たし、cached norm または関連する `STRATA_GR_LO_REUSE` が有効になった場合、stderr に一度だけ次の形式のログを出します。

```text
strata: GR reuse enabled: normalized activation 1, low-rank SiLU 0
```

末尾の数値は実際に有効化した二つの再利用フラグです。条件に合わず再利用しない場合、この変数を理由とする警告や無効化ログはありません。fused 経路自体が使われない場合も値の読み取りは行われません。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:159-166` — helper の非空値判定、Battlemage 判定、既定値の適用。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1830-1884,1978-1995` — `fused_gr_read_multi()`、早期 return、対象変数の static cache、全有効条件、状態設定とログ。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:249-290` — cached 状態と scratch alias 安全性の検査。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:382-435,668-696,713-714,891-899` — norm split による `xn` の生成、適用条件に使う別環境設定の判定、`UPM_COLS` の値。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:788-837,901-911` — cached norm を使う epilogue と再利用 kernel の選択。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2151-2174` — 単一 token の fused read が multi-token 実装へ入る条件。
- `sycl/src/core/layer.cpp:1558-1560,1620-1631,1643-1654` — fused hyper-connection 経路の判定と呼び出し。
- `docs/INTEL.md:527-529,541-543` — Intel 向け資料の制御説明（Battlemage 既定値・当変数の既定 OFF）。実際の値判定と条件は上記ソースを根拠とした。
