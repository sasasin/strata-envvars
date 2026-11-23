# `STRATA_GRAPH_PRIO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の verify window graph に、capture 時の stream priority を kernel node priority として適用し、priority を指定して graph を instantiate する opt-in 変数です。未設定または整数変換結果が 0 の場合はこの設定を使わず、従来どおり node priority を指定しません。対象は `Verifier` の window graph であり、commit graph にはこの変数による設定を渡しません（`engine/src/core/verify.cpp:240-248, 3388-3409, 3425-3426`）。

CUDA の priority 範囲が複数値を持つ場合、side mixer 用 stream は最高、`cs_` と `side2_` は中間、shared expert 用 `sh_cs_` は最低の priority で作成します。capture 後、stream から node priority が取得できなければ記録した fork/tail をたどって属性を設定し、`cudaGraphInstantiateFlagUseNodePriority` を指定します。これは計算内容や graph の依存関係を書き換える設定ではありません（`engine/src/core/verify.cpp:1295-1309, 1404-1412, 1508-1511, 1897-1903, 2318-2326, 2756-2759, 5155-5210, 3388-3393`）。

## 値と判定

CUDA 対象 build では `std::getenv` の結果を `std::atoi(v) != 0` で判定します。文字列全体の数値検証や範囲検査はありません。`atoi` は先頭の空白と符号を許し、整数として読める先頭部分を変換します。したがって、空文字・整数部分がない文字列・`0anything` は 0、`1`・`-1`・`1anything` は非 0 です。`true` や `false` は 0 になります。変換範囲外の文字列についてコード上の検査・fallback はありません（`engine/src/core/verify.cpp:242-248`）。

| build 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` のいずれも未定義 | 無効 | `1`, `-1`, `1junk` | 空文字、`0`, `0anything`, `true`, `abc` |
| 上記いずれかが定義済み | 常に無効 | なし | すべての値 |

設定値は `graph_prio_on()` の関数内 `static` に初回呼び出し時に保存され、そのプロセス内では再読込されません。起動後に環境を変更しても反映されません（`engine/src/core/verify.cpp:242-248`）。CLI 引数や設定ファイルからこの値を上書きする読み取り箇所は、対象 commit の全参照検索では見つかりません。

## 有効になる条件

- HIP、`STRATA_HIP_GFX906`、Metal build では helper が常に `false` を返し、priority query・node 属性設定・instantiate flag 設定も CUDA 専用の条件付きコード内です（`engine/src/core/verify.cpp:242-248, 1300-1306, 3388-3394`）。
- CUDA では `cudaDeviceGetStreamPriorityRange` が成功し、返された `gp_lo` と `gp_hi` が異なる場合に限り `gprio` が有効になります。失敗または同値なら stream priorities は 0 のままで、設定は適用されません（`engine/src/core/verify.cpp:1300-1309`）。
- `STRATA_SIDE_MIXER` が有効でない場合、side mixer の `side_` / `side2_` stream は作成されません。`STRATA_SIDE_MIXER` が未設定のときの有効化は CUDA compute capability 12.0 の既定に依存します。batch window では mixer branch に `STRATA_BATCH_SIDE_MIXER` も必要です（`engine/src/core/verify.cpp:272-292, 370-372, 1404-1412, 1503-1515`）。
- `STRATA_PIPED_CONCURRENT` が非 0 で、`STRATA_PIPED_CONCURRENT_PRIO` が未設定または非 0 の場合、`make_stream` は先に最高 priority の stream 作成を試みます。成功した stream では `STRATA_GRAPH_PRIO` 用の指定 priority よりこの経路が優先されます。失敗時には `gprio` の priority 作成を試み、さらに失敗すれば通常の non-blocking stream に fallback します（`engine/src/core/verify.cpp:1312-1334`）。
- `Verifier::set_stream` で外部 stream が設定されている場合、`cs_` はその stream を共有し、`make_stream(&cs_, gp_mid)` を通りません。その stream の priority はこの変数では設定されません（`engine/include/strata/core/verify.hpp:346, 560; engine/src/core/verify.cpp:1352-1355`）。
- priority 付き stream の作成に失敗しても `make_stream` は失敗を返さず通常 stream へ fallback します。copy stream 等の最終 fallback 作成が失敗すると `verify: copy stream create failed`、`cs_` / `sh_cs_` の作成が失敗すると `verify: stream create failed` で初期化が失敗します（`engine/src/core/verify.cpp:1326-1356`）。

## 実行時の詳細

`Verifier` の初期化時に `graph_prio_on()` を呼び、priority range を調べて stream を準備します。`side_` は GDN gate / QSA indexer の branch が使う最高 priority、`side2_` と `cs_` は中間、shared expert 用 `sh_cs_` は最低 priority です。外部 stream、`STRATA_PIPED_CONCURRENT` による先行成功、または stream 作成 fallback がある場合、実 stream の priority がこの割当てと異なることがあります（`engine/src/core/verify.cpp:1300-1355, 1897-1903, 2318-2326, 2747-2759`）。

各 window graph の capture 開始時に priority の fork/tail 記録を消去し、対象 branch の fork と priority stream の tail を記録します。graph 完成後に `apply_node_priorities` が node priority を調べ、capture から非 0 の priority が得られない場合は記録した tail から fork まで依存 node をたどって kernel node に属性を設定します。その後、window graph だけを `cudaGraphInstantiateFlagUseNodePriority` 付きで instantiate します（`engine/src/core/verify.cpp:3270-3278, 3388-3409, 5120-5210`）。

priority range query が失敗または全 priority が同値のときは適用を諦め、設定有効を示す priority stream ログも出ません。query 失敗時の CUDA error は `cudaGetLastError()` で消費されます。capture query や node 属性の個々の失敗も同様に error を消費して続行する処理であり、専用の失敗ログはありません（`engine/src/core/verify.cpp:1302-1309, 5123-5152, 5161-5204`）。

## ログと測定値

priority range query が成功し複数の値が得られたとき、stderr に次の形式で stream priority を出します（`gp_hi`, `gp_mid`, `gp_lo` の実値が入ります）。

```text
strata verify: STRATA_GRAPH_PRIO: stream priorities side %d, cs / side2 %d, shared expert %d
```

各 window graph では stderr に kernel node priority の histogram、priority range、capture からの取得有無、fork/tail 記録数、fallback で属性設定した node 数も記録します。`STRATA_GRAPH_PRIO` によるエラー専用メッセージはありません。対象 commit の `docs/DETAILS.md:1788` には `STRATA_QIL=1` とした decode の測定記載がありますが、測定条件がこの調査の品質基準を満たす形で揃っていないため、一般的な性能値としては記載しません。

## 根拠

- 判定・compile guard・cache: `engine/src/core/verify.cpp:240-248`
- priority range、stream 作成、ログ、fallback: `engine/src/core/verify.cpp:1295-1355`
- verify window の capture と instantiate: `engine/src/core/verify.cpp:3270-3289, 3388-3409`
- branch / tail の記録と node 属性設定: `engine/src/core/verify.cpp:1508-1512, 1897-1903, 2318-2326, 5120-5210`
- 外部 stream setter: `engine/include/strata/core/verify.hpp:346, 560`
