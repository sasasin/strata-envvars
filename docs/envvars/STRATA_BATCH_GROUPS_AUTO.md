# `STRATA_BATCH_GROUPS_AUTO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 版 `strata generate` で、特定の Intel Arc B-series 2 GPU レイヤー分割時に `--batch-groups` の既定値を自動で 2 にする選択を止める変数です。バッチ処理そのものを有効化する変数ではありません。`--batch` が有効で、グループ数を指定していない場合にだけ既定値の決定へ関与します。`engine/sycl/src/program/generate.cpp:4402-4422`。

対象となる特定構成は、layer split の stage が 1 個で、device 0 とその stage の device の両方が `IntelGpuGen::Battlemage` と判定され、実際の batch slot 数が 8 以上の偶数である場合です。このとき通常の自動既定値は 2 group です。変数でこれを抑えると 1 group になります（ただし明示した `--batch-groups auto` は後述の別ルールで group 数を選びます）。`engine/sycl/src/program/generate.cpp:4405-4419`。

## 値と判定

値は `std::getenv` で取得し、`std::atoi(ga) == 0` の場合に自動 2-group 選択を無効化します。文字列全体の検証やエラー処理はなく、`atoi` が読む先頭の整数部分で決まります。したがって空文字、整数として読めない文字列、`0`, `00`, `-0`, `0anything` は 0 となり無効化します。先頭空白や符号の後に 0 がある値も同様です。`1`, `-1`, `2`, `1anything` など `atoi` の結果が非 0 なら無効化しません。大小文字は判定対象外です。`engine/sycl/src/program/generate.cpp:4410-4412`。

| 条件 | unset | 無効化する値の例 | 無効化しない値の例 |
|---|---|---|---|
| SYCL `strata generate` の自動 group 数選択 | 特定の Arc B-series 2 GPU 構成では自動既定値 2。その他の暗黙既定値は 1 | `""`, `0`, `00`, `-0`, `0anything`, `abc` | `1`, `-1`, `2`, `1anything` |

`std::atoi` が整数表現の範囲外となる入力について、Strata 側に範囲検査や fallback はありません。未設定は `ga == nullptr` なので無効化しません。明示的な空文字は `atoi` の結果が 0 となり無効化します。`engine/sycl/src/program/generate.cpp:4410-4412`。

## 有効になる条件

- Strata の SYCL `generate.cpp` 経路を含むビルドであること。この読み取りは `engine/sycl/src/program/generate.cpp` にあり、同名の runtime 読み取りは他のソースで見つかりませんでした。`engine/sycl/CMakeLists.txt:375-377`。
- `o.batch > 0` かつ `o.batch_groups <= 0` で、自動的に group 数を決める経路に入ること。正の `--batch-groups N` はこの環境変数より優先され、環境変数は読まれません。`--batch-groups` は `auto` を `-1`、それ以外を `atoi` で数値化します。`engine/sycl/src/program/generate.cpp:2037-2043,4402-4412`。
- 特別な既定値 2 が適用されるには、layer split が存在し、stage が 1 個、device 0 と stage device が Battlemage、batch が 8 以上かつ偶数である必要があります。条件を満たさなければ、この変数は group 数を変えません。`engine/sycl/src/program/generate.cpp:4405-4419`。
- batch 自体が `--serve` なし、2 slot 未満、または同一 GPU に複数 stage がある構成などで無効化された場合、後続の group 数決定には至りません。batch 不成立時は警告を出し、batch を 0 にします。`engine/sycl/src/program/generate.cpp:4388-4400`。
- `--batch-groups auto` を明示すると `given_auto` が真になります。環境変数の値が 0 で特別な既定値 2 を抑えても、後続の auto ループが stage 数と batch を割り切る最大候補を選ぶため、2 GPU・batch 8 なら再び 2 group になります。この環境変数は明示 `auto` の選択を禁止しません。`--batch-groups 1` は正値なので環境変数の判定経路を通らず、1 group を直接指定します。`engine/sycl/src/program/generate.cpp:2040-2043,4402-4421`。
- 選択後も group 数が 1 より大きい場合は layer split があり、group 数が batch slot 数を割り切る必要があります。割り切れない場合は警告して 1 group に戻します。slot session の確保後に実際の slot 数が変わって割り切れなくなった場合も 1 group に戻ります。`engine/sycl/src/program/generate.cpp:4423-4426,4481-4490`。

## 実行時の詳細

CLI 引数解析時点では `batch_groups` は未指定を表す 0 です。`--batch-groups auto` は -1、その他の値は `atoi` 結果になります。batch が有効で group 数が 0 以下のときだけ既定値を解決し、その際に `static const char* ga` として `getenv` の結果ポインターを初回評価時に保存します。`atoi(ga)` 自体はこの解決経路で評価されます。`engine/sycl/src/program/generate.cpp:669-673,2037-2043,4402-4412`。

環境変数が抑制しない場合、Battlemage 2 GPU・8 以上の偶数 slot では group 数を 2 にします。抑制する場合は、暗黙の既定値は 1 です。明示 `auto` の場合は stage 数以下で slot 数を割り切る最大 group 数を選びます。group 数が 2 以上かつ layer split があると、実行ループで `piped` が真となり、batch slot を各 group の `GS` 件に分けて stage 間で順次進めます。group 数 1 ではこの pipelined group 経路に入りません。`engine/sycl/src/program/generate.cpp:4412-4421,10086-10104`。

## ログと測定値

特別な既定値 2 が選択された場合、stderr に次の行を出します（`%d` は batch slot 数）。変数が 0 と判定されて抑制された場合、この分岐のログは出ません。

```text
strata generate: --batch-groups 2 by default: %d slots over a layer split on two Arc B-series cards (--batch-groups 1 or STRATA_BATCH_GROUPS_AUTO=0 turns it off)
```

`engine/sycl/src/program/generate.cpp:4412-4415`。

不正な group 数条件や batch slot の確保失敗には別の `WARNING` が出ますが、これらはこの変数固有の警告ではありません。`engine/sycl/src/program/generate.cpp:4393-4400,4423-4426,4481-4489`。この変数単独の性能測定値は記載していません。

## 根拠

- 環境変数読み取りと Arc B-series 自動既定値: `engine/sycl/src/program/generate.cpp:4402-4422`
- CLI の group 数初期値と解析: `engine/sycl/src/program/generate.cpp:669-673,2037-2043`
- batch 有効化条件・調整: `engine/sycl/src/program/generate.cpp:4388-4400,4423-4426,4481-4490`
- pipelined group の実行条件: `engine/sycl/src/program/generate.cpp:10086-10104`
- SYCL のソース構成: `engine/sycl/CMakeLists.txt:375-377`
