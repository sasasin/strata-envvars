# `STRATA_MTP_KEEP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

GPU メモリ不足が見込まれるときに、Strata が MTP draft layer（または特定の分割 GPU 経路の DFlash2 drafter）を外して起動を続ける処理を抑止する。値を読み取っているのは `strata generate` の初期化処理で、`--serve` も同じ `generate.cpp` の経路を使う。環境変数が設定されているだけで抑止され、値の内容は機能選択に使われない（`engine/src/program/generate.cpp:8195-8217,8220-8240`）。

この変数は drafter を有効化するものではなく、GPU に収まらない場合の自動除去を止めるだけである。drafter 自体は `--mtp`、`--spec T` などの指定が別途必要であり、保持した結果の load に失敗すれば起動は失敗し得る（同 `:4040,4055,8243-8265`）。

## 値と判定

両方の読み取り箇所で `std::getenv("STRATA_MTP_KEEP") == nullptr` を判定する。`atoi` や文字列比較はなく、未設定なら除去処理が候補になり、設定済みなら除去処理を通らない。明示的な空文字、`0`、`false`、任意の文字列はいずれも「設定済み」で同じ結果になる。大文字小文字、空白、数値としての妥当性は検査しない（`engine/src/program/generate.cpp:8197,8220`）。

| 条件 | unset | 設定時に除去を抑止する値 | 除去を抑止しない値 |
|---|---|---|---|
| 対象の MTP または分割 DFlash2 経路 | GPU メモリ判定が不足なら drafter を外す | 空文字、`0`、`false`、`1`、その他すべて（`getenv` が非 null） | なし（値を parse しない） |

## 有効になる条件

- MTP の場合、`--mtp DIR` が指定されて `o.mtp` が空でなく、`--spec` が 2 以上であること。`--spec` が 2 未満なら後続処理が MTP を無視して `o.mtp` を clear する（`engine/src/program/generate.cpp:4040,4055,8243-8247`）。
- 自動除去判定は、単一 GPU 経路（`!multi_gpu && stages.empty()`）または `STRATA_SPILL_OFF` が未設定の layer-split 経路（`multi_gpu && !stages.empty()`）で行われる。加えて `spill_discrete_gpu()` が true である必要がある（同 `:327-339,8195-8198`）。
- `spill_discrete_gpu()` は Metal build では false。その他の build では CUDA 互換 runtime から現在デバイスと属性を取得でき、現在デバイスが integrated GPU でない場合だけ true になる。したがって Metal と integrated GPU ではこの自動除去自体が走らず、本変数の効果もない（同 `:327-339`; `engine/include/strata/core/spill_gate.hpp:8-14`）。
- MTP の判定は `use_df2` が false の場合に限る。`--draft dflash2` の単独 fallback（`--draft-fallback none`）では MTP を先に無効化して `df2_solo` にし、DFlash2 側の専用判定へ進む（同 `:6493-6530,8197,8220`）。その専用判定は layer split 時だけで、単一 GPU の DFlash2 solo 経路はこの変数では制御されない（同 `:8220-8240`）。
- `--serve` 専用の条件ではなく、`generate.cpp` の共通初期化で判定される。環境変数に CLI 引数や別の変数の値を代入する優先順位はない。`STRATA_SPILL_OFF` は layer-split の drafter 除去経路を止めるが、単一 GPU 経路の条件には含まれない（同 `:8195-8198`）。
- GPU メモリが不足していない場合、ファイルサイズ取得に失敗した場合、または free memory が 0 と報告された場合は、該当する除去分岐には入らず、この変数による差は出ない（同 `:8199-8217,8221-8240`; `engine/include/strata/program/split_walk.hpp:57-67`）。

## 実行時の詳細

判定は `generate.cpp` の GPU/model 初期化中、drafter の load より前に行われる。プロセス起動時に値を parse して cache する実装ではなく、該当する初期化経路で `getenv` を直接確認する。server モードではこの判定後にリクエスト処理へ進むため、リクエストごとに再評価するコードではない（`engine/src/program/generate.cpp:8195-8243`; `--serve` parser は同 `:4069`）。

未設定の場合、MTP は `dense.bin` と `experts.bin` のサイズ取得が成功し、free memory が正値かつ `layer_bytes + head_bytes + (220 MiB) + (1550 MiB)` 未満なら `o.mtp` を clear する。layer split では drafter を置く stage の free memory を調べる。DFlash2 solo の layer-split 経路では pack と draft head を含む `pack_bytes + 250 MiB + head_bytes + 220 MiB + 1550 MiB` を境界とし、free memory が正値かつ必要量未満なら `df2_solo` を false にして draft 設定を clear する（同 `:8199-8240`; `engine/include/strata/program/split_walk.hpp:57-67`）。

除去が発生すると起動は drafter なしで続行し、ログ上は decode が遅くなる旨が示される。環境変数が設定されていると除去を抑えるため、後続の `mtp.load(...)` などが失敗した場合は `strata generate: <error>...` を stderr に出して終了コード 1 で戻る。設定済みでも起動成功は保証されない（`engine/src/program/generate.cpp:8211-8217,8233-8240,8264-8265`）。

## ログと測定値

メモリ不足で MTP を外す場合の stderr は `strata generate: short of GPU memory: ... this start runs without the draft layer (decode is slower; STRATA_MTP_KEEP=1 keeps it)`。分割 DFlash2 を外す場合は `... this start runs without a drafter (decode is slower; STRATA_MTP_KEEP=1 keeps it)`。どちらも実際に境界を下回り、ファイルサイズが読めた場合にだけ出る。変数を設定したこと自体を知らせるログはない（`engine/src/program/generate.cpp:8211-8216,8233-8236`）。

`docs/SETTINGS.md:183` は値を `on / off` と分類し、`docs/MULTI_GPU.md:226` と実装ログは `STRATA_MTP_KEEP=1` と記すが、実装は設定有無だけを見る。よってコード上は `0` や空文字でも除去を止める。測定値はこの変数の効果を条件付きで示す資料が見当たらないため記載しない。

## 根拠

- `engine/src/program/generate.cpp:8195-8217` — MTP の読み取り、メモリ判定、ログ、`o.mtp` の無効化。
- `engine/src/program/generate.cpp:8220-8240` — layer-split DFlash2 solo の読み取り、メモリ判定と無効化。
- `engine/src/program/generate.cpp:327-339`、`engine/include/strata/core/spill_gate.hpp:8-14` — Metal / integrated GPU を除く spill 判定。
- `engine/include/strata/program/split_walk.hpp:57-67` — メモリ境界式。
- `engine/src/program/generate.cpp:4040,4055,4069,6493-6530,8243-8265` — CLI 条件、server mode、drafter 初期化と失敗経路。
