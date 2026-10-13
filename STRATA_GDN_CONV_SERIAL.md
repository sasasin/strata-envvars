# `STRATA_GDN_CONV_SERIAL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

GDN（gated-delta-net）の prompt prefill にある因果畳み込みで、旧来の逐次 walk を使うかを切り替えます。CUDA/HIP 共通の `.cu` 実装と SYCL 実装に読み取り箇所があります。設定すると、chunk 内の各 token を順に処理する kernel を選びます。未設定で chunk が 64 token を超えると、token を 64 個ずつ独立 tile として処理する kernel が選ばれます。

## 値と判定

値の内容は parse されず、`std::getenv(...) != nullptr` だけで判定します。

| 環境変数の状態 | `serial` | 結果 |
|---|---:|---|
| 未設定 | false | `T > 64` なら tiled 経路。`T <= 64` なら逐次 walk 経路 |
| 空文字を含む何らかの値を設定 | true | 逐次 walk 経路。`0`、`false` などの文字列も設定扱い |

この分岐は `gdn_conv()` 内で `static const bool` に保存されるため、最初の `gdn_conv()` 呼び出し時に判定され、そのプロセス内では再評価されません。後から環境を書き換えても反映されません。

## 有効になる条件

prefill で GDN 層を処理し `gdn_conv()` が呼び出される場合に参照されます。QSA 層の経路ではこの呼び出しに入りません。`T` はその呼び出しで処理する chunk の token 数です。

`T <= 64` では変数が未設定でも逐次 walk が使われるため、その範囲では設定による kernel 選択の差はありません。`T > 64` で変数を設定すると、別の環境変数 `STRATA_GDN_CONVL2` が有効でも逐次 walk が優先され、融合 kernel の分岐には入りません。

## 実行時の詳細

逐次 walk kernel は、各 channel の thread が chunk の全 token を順番に処理し、過去 3 値の history を更新します。その後、q/k channel の L2 正規化 kernel が実行されます。したがって `STRATA_GDN_CONV_SERIAL` は正規化そのものを無効化しません。

未設定かつ `T > 64` の場合、通常の tiled 経路は 64 token 単位の畳み込み kernel と history 更新 kernel を実行し、その後に L2 正規化を行います。`STRATA_GDN_CONVL2` が `atoi` で非 0 と判定される場合は、畳み込みと正規化を融合した kernel と history 更新 kernel を実行して関数から戻ります。`STRATA_GDN_CONV_SERIAL` の設定はこの経路を先に遮ります。

この変数を読む実装箇所に、専用のログ出力はありません。

## 根拠

- CUDA/HIP: `src/prefill/kernels.cu:1907-1925` が変数を読み、逐次・tiled・融合経路を選択します。逐次畳み込み本体は `src/prefill/kernels.cu:294-307`、tiled 本体は `src/prefill/kernels.cu:308-328`、正規化は `src/prefill/kernels.cu:380-391` にあります。
- SYCL: 同じ値判定と経路選択は `sycl/src/prefill/kernels.dp.cpp:2500-2601`、対応する kernel は `sycl/src/prefill/kernels.dp.cpp:450-492,605-625` にあります。
- 呼び出し条件: `src/prefill/prefill.cpp:2603-2623` および `sycl/src/prefill/prefill.cpp:2886-2906` で、GDN 層の prefill 処理から `gdn_conv()` を呼びます。
- `docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。性能や数値的一致について、この調査では測定・実行確認をしていません。
