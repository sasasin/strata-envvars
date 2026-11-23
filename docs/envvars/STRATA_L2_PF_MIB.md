# `STRATA_L2_PF_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_L2_PF_MIB` は、verify window の L2 prefetch 対象にする各レイヤーの重み範囲を MiB 単位で制限する。正値なら、レイヤー内で読み取り順に並べた重み範囲の先頭から最大その値までを `L2PrefetchSet` に加える。0 以下なら上限を設けず、対象範囲を最後まで加える。これは prefetch 範囲の長さだけを変え、verify window の計算値を変える処理ではない（`engine/src/core/verify.cpp:1553-1557,1569-1601`、`engine/include/strata/kernels/verify_kernels.hpp:82-100`）。

この変数だけでは機能を有効にしない。CUDA の verify window で `STRATA_L2_PF` が非ゼロの場合に限り読み取られ、CPU expert の行を待つ間に次レイヤーの重みを prefetch する経路で使われる（`engine/src/core/verify.cpp:1558-1566,2833-2845,2893-2906`）。

## 値と判定

値は `std::getenv` で読み、設定されていれば `std::atol` で `long` に変換する。文字列全体の妥当性検査や明示的な上限・下限 clamp はない。`atol` の数値変換後の値が正の場合だけ上限として使う。正値 `n` は `n << 20` バイトの上限（1 MiB = 1,048,576 bytes）となり、最後の重み範囲は残り byte 数で切り詰められる。0 以下は上限なしである（`engine/src/core/verify.cpp:1566,1594-1599`）。

| 条件 | unset | 上限として有効 | 上限として無効（上限なし） |
|---|---|---|---|
| CUDA verify window で後述の有効条件を満たす | `0` 相当。全対象範囲を加える | `1`, `8`, `+2` はそれぞれ 1, 8, 2 MiB。先頭の範囲から指定 byte 数までを加える | 空文字、`0`, `-1`, `true`, `abc`, `2x` は変換値が 0 以下となり上限なし。`2x` のように数字の後ろに文字があっても先頭の数値部分 `2` を変換し、2 MiB 上限になる |
| `STRATA_L2_PF` が未設定または変換値 0、HIP build、または window 条件外 | MIB は参照されない | 効果なし | 効果なし |

未設定時のコード既定値は `0L`。空文字は未設定とは区別されますが、`atol("")` の結果は 0 のため、いずれも上限なしです。先頭の空白と符号は数値変換で扱われ、英字の大小を比較する判定はありません。`2.5` は整数部の `2` として変換されます。数値範囲外の文字列に対する安全な clamp や個別エラー処理は実装されていません（`engine/src/core/verify.cpp:1566,1594-1599`）。

## 有効になる条件

- `STRATA_L2_PF` が設定され、`std::atoi` の結果が 0 以外であること。未設定時は 0。空文字や非数値は 0 となる（`engine/src/core/verify.cpp:1558,1565`）。
- HIP build では `l2pf_cuda` が `false` なので機能は無効で、`STRATA_L2_PF_MIB` の読み取りにも到達しない。非 HIP の経路では `l2pf_cuda` は `true` と定義される（`engine/src/core/verify.cpp:1560-1566`）。
- window が単一 group（`G == 1`）、非 batch、非 profile、非 all-resident であること。split window や長い window の 2 group、batch、`STRATA_VERIFY_PROFILE` が設定された window、全重み resident の経路では範囲を構築しない（`engine/src/core/verify.cpp:1262,1486,1565`）。
- 発行時には、現在のレイヤーの次が同じ stage 範囲内にあり、そのレイヤーの prefetch set に 1 範囲以上あり、shared stream と fork/join event が利用できることが必要。`sh_stream_on()` が false なら発行されない。CUDA では `STRATA_SH_STREAM` 未設定時に true、設定時は先頭文字が `'0'` 以外なら true。HIP では既定 false だが、HIP は前段の条件で無効（`engine/src/core/verify.cpp:415-424,2838-2845,2897-2906`）。
- 数値範囲を作る際、`wt.all()` の `blk.<layer>` 重みのうち、`hc_q8`、`native_data`、または resident な `data` を持つものだけを採る。ポインタが null または byte 数が 0 の重みは除外される（`engine/src/core/verify.cpp:1569-1581`）。
- 直接値を上書きする CLI 引数や設定ファイルはこのコードにない。`STRATA_L2_PF_MIB` は上記の親フラグが有効なときにのみ上限として働く（`engine/src/core/verify.cpp:1558-1566`）。

## 実行時の詳細

関数ローカル `static` の `l2pf_env` は `record_window` がこの初期化箇所に初めて到達した時に読み取られ、その後同じプロセスではキャッシュされる。`STRATA_L2_PF_MIB` の `static` 初期化はさらに内側の条件分岐にあるため、CUDA、親フラグ非ゼロ、window 条件を初めて満たしたときに読み取られる。いったん初期化された後にプロセス環境を変えても反映されない（`engine/src/core/verify.cpp:1468,1558-1567`）。

対象重みを layer ごとに集め、`hc_attn_`、attention / SSM / indexer、`hc_ffn_`、`gate_inp`、その他の順で stable sort する。正の上限では各 layer について累積 byte 数を上限で止め、必要なら最後の範囲を切り詰める。`L2PrefetchSet::add` は 16 byte 未満の範囲と 33 件目以降を無視する（最大 32 件）。実際の発行は CPU expert の行待ちの間に次レイヤーの set を shared stream に渡す箇所で行われる。`device_hits` 経路と通常の CPU expert 経路に発行箇所があるが、通常経路側は `device_plan_` でないことも条件にする（`engine/src/core/verify.cpp:1578-1601,2833-2845,2893-2906`、`engine/include/strata/kernels/verify_kernels.hpp:85-100`）。

## ログと測定値

範囲を構築する分岐に入ると stderr に一度だけ次の形式で出力する。`l2pf_mib > 0` の場合だけ末尾に `, capped` が付く。親フラグが無効、HIP、または window 条件外ではこのログも出ない。`STRATA_L2_PF_MIB` の無効値に対する警告や独自エラーはない（`engine/src/core/verify.cpp:1603-1608`）。

```text
strata: STRATA_L2_PF=<値>: next-layer dense-weight L2 prefetch while the window waits for CPU experts (largest layer <数値> MiB[, capped])
```

この checkout の `docs/DETAILS.md` と関連する Markdown 資料には、この変数の測定値や条件付き性能結果を確認できなかったため、性能値は記載しない。コードコメント上も、この設定値による結果測定の記載はない（`engine/src/core/verify.cpp:1553-1557`）。

## 根拠

- `engine/src/core/verify.cpp:1553-1567` — L2 prefetch の説明、親フラグ、backend 分岐、MIB の読み取り。
- `engine/src/core/verify.cpp:1569-1608` — 対象重みの選別、順序と MiB 上限、stderr ログ。
- `engine/src/core/verify.cpp:2833-2845,2893-2906` — CPU expert 待ち中の次レイヤー prefetch 発行条件。
- `engine/src/core/verify.cpp:415-424` — shared stream の backend 既定値と `STRATA_SH_STREAM` 判定。
- `engine/include/strata/kernels/verify_kernels.hpp:82-102` — prefetch set の範囲追加と上限件数。
