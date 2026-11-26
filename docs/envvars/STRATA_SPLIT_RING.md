# `STRATA_SPLIT_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の layer split（複数 GPU）で、prompt path が使う streamed ring の slot 数を指定する。正の値は `Prefill::set_ring_override` に渡され、expert cache の resident 率に応じた自動値または通常の pinned-share ルールより優先される。ring の slot 数は prompt buffer の `bytes_needed` と lend region の sizing にも使われるため、分割 cache から借りる量に影響する。decode の設定ではない。標準 engine は `decide_split_ring`、SYCL engine は split の prefill setup 内で判断する（`engine/src/program/generate.cpp:11828-11844,11964-11966`; `engine/sycl/src/program/generate.cpp:7227-7241`）。

## 値と判定

標準 engine は `std::getenv` の結果を `split_ring_slots` に渡し、SYCL engine は同じ場所で `std::atoi` を使う。どちらも値が `nullptr`（未設定）かどうかを分けた後、正数だけを override にする。文字列全体の検証はなく、`atoi` が先頭から変換できた数値を使う（例: `12tail` は 12、` 12` は 12）。空文字、`true`、`junk`、数値に変換できない先頭、0、負数は 0 扱いとなる。大文字小文字の区別や boolean 文字列の解釈はない。`atoi` が `int` に収まらない値の結果はコードで保証されない（`engine/include/strata/program/split_ring.hpp:17-23`; `engine/sycl/src/program/generate.cpp:7235-7237`）。

| 条件 | 未設定 | 正数の例 | 0 になる例 |
| --- | --- | --- | --- |
| layer split の expert residency 情報があり、読み取り箇所に到達 | 標準 engine は resident `(layer, expert)` pair の割合が 75% 以上なら 96 slots を選び、それ未満なら override を設定しない。SYCL は同じ条件を直接評価する。 | `1`, `96`, `384`, `12tail` は override 候補 | `0`, `-3`, 空文字, `true`, `junk` は override を設定しない |
| 単一 GPU、非 serve、または resident 情報なし | 変数を読まず、この分岐からは何も設定しない | 適用なし | 適用なし |

正の override は後段の ring resolution で最低 16 slots、上限は runtime の `ring_cap()` に丸められる。`ring_cap()` は通常 512、fused Q2_0 経路では 1024 である。prompt chunk が `stream_all_min()` 未満なら ring は `STAGE` になり、positive override があっても大きい ring は使われない（`engine/src/prefill/prefill.cpp:808-810,843-879`; `engine/sycl/src/prefill/prefill.cpp:291-323`）。

未設定時に resident 率が 75% 未満、または設定値が 0/無効値の場合はこの分岐から正数 override を設定せず、後段では通常 pinned-share ルールが使われる。ただし標準/SYCL の初期 split sizing が no-borrow 条件で先に 96 を設定している経路では、この変数の 0/無効値はその既存 override をクリアしない（`engine/src/program/generate.cpp:3850-3860`; `engine/sycl/src/program/generate.cpp:3850-3860`; setter は `engine/src/prefill/prefill.cpp:3555-3556`）。

## 有効になる条件

- `--serve` の layer split で複数 GPU が使われること。標準 engine は `o.serve`、`multi_gpu`、`host_res` 非空のすべてを確認してから読み取る。通常の生成ではこの変数の読み取りに到達しない（`engine/src/program/generate.cpp:11833-11839`）。
- SYCL engine は split の prefill setup で `multi_gpu && !host_res.empty()` のとき読み取る（`engine/sycl/src/program/generate.cpp:7231-7236`）。
- resident 率の自動値は `host_res` のうち値が 0 以上の要素数を全要素数で割って計算し、75% 以上で 96 slots。明示した正数はこの割合に関係なく使う（`engine/src/program/generate.cpp:11836-11843`; `engine/sycl/src/program/generate.cpp:7232-7240`）。
- 実際の streamed ring は chunk が `stream_all_min()` 以上である場合に限り使われる。それ未満は routed-only の `STAGE` に留まる（`engine/src/prefill/prefill.cpp:878`; `engine/sycl/src/prefill/prefill.cpp:319-323`）。
- `STRATA_PREFILL_RING` が設定されていると、後段の ring resolution ではそちらの `atoi` 値が split override より優先される。したがってこの変数が正数でも、`STRATA_PREFILL_RING` が設定されている場合は split ring の指定値が使われない（`engine/src/prefill/prefill.cpp:843-878`; `engine/sycl/src/prefill/prefill.cpp:291-323`）。
- no-borrow sizing では split setup が先に 96 slots を設定する条件がある。そこでは `STRATA_SPLIT_RING` の値が 0 相当でも既存 96 slots を解除しない（`engine/src/program/generate.cpp:3850-3860`; `engine/sycl/src/program/generate.cpp:3850-3860`; `engine/src/prefill/prefill.cpp:3555-3556`）。

## 実行時の詳細

標準 engine は `decide_split_ring` を一度だけ実行し、`split_ring_decided` で重複を防ぐ。値を読むのは serve split の `host_res` 作成後で、値を決めてから `Prefill::bytes_needed` による lend region sizing を行う。resident pair の割合は `host_res` 全体から算出する（`engine/src/program/generate.cpp:11828-11844,11950-11966`）。SYCL も lend-region sizing の前に ring を決定し、`host_res` から割合を算出する（`engine/sycl/src/program/generate.cpp:7227-7241`）。対象変数自体はこの setup 時に読み取られ、読み取った値を後続の呼び出しごとに再評価する static cache はない。決定後の環境変更で既に設定した override が更新されるコードはない。

正数が選ばれると `Prefill::set_ring_override(ring)` が global override を設定し、stderr に次の行を出す。正数が選ばれなければ、この変数によるログは出ない（`engine/src/program/generate.cpp:11839-11844`; `engine/src/prefill/prefill.cpp:3555-3556`; SYCL: `engine/sycl/src/program/generate.cpp:7235-7241`）。

```text
strata serve: layer split: <resident率>% of the experts resident, the prompt path's streamed ring <slots> slots
```

通常の prompt path では ring の buffer sizing にこの値が反映され、split 各 stage の cache lend region と prompt path の streamed ring の大きさに影響する。出力例に対応する失敗・終了経路や、この変数専用の警告は読み取り箇所にはない。なお、`STRATA_PREFILL_RING` の値の変換・範囲規則は同変数側の `ring_slots` が適用するため、ここではその外部設定値自体の挙動としては説明しない。

## ログと測定値

コード上の観測可能な出力は上記の stderr 起動行で、split ring の override が正数の場合に限って出る。`docs/MULTI_GPU.md:152` は startup line を `lend sizing: ...` と記しているが、現行ソースの出力文字列は `strata serve: layer split: ... the prompt path's streamed ring ... slots` である。資料記載の性能測定値はこの変数の現行動作の測定としては扱わない。

## 根拠

- `engine/include/strata/program/split_ring.hpp:17-23` — 未設定時の residency fallback と数値変換。
- `engine/src/program/generate.cpp:11828-11844,11964-11966` — serve/split 条件、読み取り時期、override 設定、ログ。
- `engine/sycl/src/program/generate.cpp:7231-7241` — SYCL 側の対応実装。
- `engine/src/prefill/prefill.cpp:843-879` — `STRATA_PREFILL_RING` との優先順位、clamp、chunk 条件。
- `engine/sycl/src/prefill/prefill.cpp:291-323` — SYCL 側の ring resolution と chunk 条件。
- `engine/src/program/generate.cpp:3850-3860`; `engine/sycl/src/program/generate.cpp:3850-3860` — no-borrow 初期 sizing における 96-slot override。
- `docs/MULTI_GPU.md:152` — ソースとログ説明の照合。
