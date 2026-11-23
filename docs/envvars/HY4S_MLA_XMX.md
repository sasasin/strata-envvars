# `HY4S_MLA_XMX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の SYCL 実装で、MLA の prefill 用 XMX カーネルと IndexPool のスコア計算用 XMX カーネルを選べるかを制御する。値が `0` で始まると XMX を抑止し、それ以外では build とデバイスが対応する場合に XMX 経路を許可する。MLA は `mla_use_xmx()`、IndexPool は `idx::score()` でそれぞれ判定する（`engine/src/hy4flash/sycl/sy_mla.cpp:29-42,1654-1680,1717-1775,1794-1829`、`engine/src/hy4flash/sycl/sy_indexer.h:352-394`）。

## 値と判定

文字列の数値変換や真偽値パースは行わず、先頭文字だけを `'0'` と比較する。

| 条件 | unset | XMX を許可する値 | XMX を抑止する値 |
|---|---|---|---|
| SYCL Hy4-Flash の MLA / IndexPool | XMX を許可する。実際に使うかは build・デバイス・処理条件による | 空文字、`1`、`true`、`false`、先頭が空白の ` 0` など。先頭文字が `'0'` でなければ許可 | `0`、`00`、`0anything`、`0.5` など先頭文字が `'0'` の全て |

大文字小文字、後続文字、空白、数値としての妥当性は検査しない。空文字は設定済みだが XMX を抑止しない。MLA 側の判定結果は関数内の `static const bool` に保存される一方、IndexPool 側は `idx::score()` の呼び出しごとに環境を読み直す（`engine/src/hy4flash/sycl/sy_mla.cpp:29-42`、`engine/src/hy4flash/sycl/sy_indexer.h:353-355`）。

## 有効になる条件

- 対象は Hy4-Flash の SYCL 実装。ソース上で同名を読む箇所は `sy_mla.cpp` と `sy_indexer.h` の2箇所（`engine/src/hy4flash/sycl/sy_mla.cpp:29-42`、`engine/src/hy4flash/sycl/sy_indexer.h:353-355`）。
- XMX の実装がビルドに含まれている必要がある。SG8 経路は `HY4S_DISABLE_SG8` が定義されていない場合だけ、SG16 経路は `HY4S_ENABLE_SG16_XMX` が定義された場合だけ選択候補になる。付属ビルドスクリプトの `bmg` は SG8 を無効にして SG16 を有効化し、`fat` と `acm` はその二つの macro を指定しない（`engine/src/hy4flash/sycl/sy_indexer.h:194-196,273-275,352-365`、`engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-35`）。
- デバイス判定で `has_xmx_sg8` または `has_xmx_sg16` が立つ必要がある。`dev_caps()` は sub-group サイズとデバイス名・architecture から判定し、別環境変数 `HY4S_NO_XMX` の先頭が `1` のときは XMX の検出自体を無効にする。`dev_caps()` も初回に得た値を static に保持する（`engine/src/hy4flash/sycl/sy_common.h:198-259`）。
- MLA の XMX prefill は行数 `M >= 16` が必要。`mla_attend_dev()` では加えて `TK == 64` かつ Tree-8 でないことが必要。これらを満たさない場合は通常の MLA カーネルへ進む（`engine/src/hy4flash/sycl/sy_mla.cpp:1654-1680,1717-1775,1794-1829`）。
- IndexPool の XMX スコア計算は `T >= 16` が必要。呼び出し元では `idx::score()` は host parameter の非 tree 経路でだけ呼ばれ、device parameter または tree 経路は `score_dev()` / `score_tree()` を使う。また IndexPool の選択自体が必要な場合に限って呼び出される（`engine/src/hy4flash/sycl/sy_graph.h:921-948`、`engine/src/hy4flash/sycl/sy_indexer.h:352-365,396-449`）。

## 実行時の詳細

MLA の `mla_use_xmx()` は最初に呼ばれた時点で環境値とデバイス能力を評価し、その結果をプロセス内でキャッシュする。値をプロセス起動後に変えても、以後の MLA 判定には反映されない。結果は `mla_choose_splits()` の分割幅選択、host parameter の `mla_prep_q()` / `mla_vup()`、および `mla_attend_dev()` の XMX 分岐で使われる。XMX prefill として分割幅 `TK=64` を選び、`M >= 16` かつ tree でない場合は XMX attend に進み、条件が合わなければ標準 attend に戻る（`engine/src/hy4flash/sycl/sy_mla.cpp:29-42,1654-1680,1717-1775,1794-1829`）。

IndexPool の `idx::score()` は呼び出しごとに `HY4S_MLA_XMX` を調べる。XMX を許可し、`T >= 16` で、build とデバイスに対応する SG8 または SG16 経路があればそのカーネルを起動して戻る。どれかの条件が満たされない場合は、同関数内の SG32 の通常スコア計算を実行する（`engine/src/hy4flash/sycl/sy_indexer.h:352-394`）。

この変数を読むコードによる子プロセスへの転送や、CLI 引数・設定ファイルによる上書きは見つからない。`HY4S_NO_XMX` はデバイス能力検出に作用する別の環境変数であり、この変数で XMX が許可されていても XMX 経路を使えなくする（`engine/src/hy4flash/sycl/sy_common.h:198-259`）。

## ログと測定値

この変数の値や XMX の可否を報告する専用ログ、または値に応じた終了・失敗経路は確認できない。条件不成立時は上記の通常カーネルへ分岐する。Strata の資料に、この変数による測定値は見つからなかった。

## 根拠

- `engine/src/hy4flash/sycl/sy_mla.cpp:29-42` — MLA の値判定、デバイス能力との組み合わせ、static cache。
- `engine/src/hy4flash/sycl/sy_mla.cpp:1654-1680,1717-1775,1794-1829` — MLA の分割幅選択、prefill カーネル選択と fallback。
- `engine/src/hy4flash/sycl/sy_indexer.h:352-394,396-449` — IndexPool の値判定、XMX / 通常経路と device/tree 経路。
- `engine/src/hy4flash/sycl/sy_graph.h:921-948,975-1038` — IndexPool と MLA 関数の呼び出し条件。
- `engine/src/hy4flash/sycl/sy_common.h:198-259` — デバイス能力の判定と `HY4S_NO_XMX` による抑止。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-35` — `fat` / `bmg` / `acm` の build macro。
