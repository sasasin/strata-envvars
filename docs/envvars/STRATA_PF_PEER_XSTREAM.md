# `STRATA_PF_PEER_XSTREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

P2P を使わない peer prefill で、primary GPU から mapped host memory へ送る入力コピーなどを専用の非ブロッキング stream に載せるかを選びます。未設定または `atoi` の結果が非ゼロなら専用 stream を使い、ゼロなら primary の compute stream `m.cs` を使います。変数名の全参照はこの読み取りと、その直前の説明コメントです（`engine/src/prefill/prefill.cpp:3380-3387`）。

## 値と判定

`std::getenv` で値を読み、設定値には `std::atoi` を適用した結果が `0` かどうかだけを見ます。文字列全体の検証や範囲制限はありません。

| peer の経路 | unset | 専用 copy stream を使う値 | compute stream を使う値 |
|---|---|---|---|
| `pp->p2p == false` | 専用 stream（既定） | `atoi` の結果が非ゼロ。例: `1`, `-1`, `1tail` | `atoi` の結果がゼロ。例: `0`, `0anything`, 空文字, `true`, `false`, 数字で始まらない文字列 |
| `pp->p2p == true` | 読み取りなし | 該当なし | この変数による変更なし |

`atoi` は先頭の空白と符号を許し、最初の数字列の後ろは判定に使いません。そのため ` 1x` は非ゼロ、`0x` はゼロです。大文字小文字の比較はありません。整数としての妥当性・範囲を別途検査せず、範囲外の値はこのコードで定義された入力として扱えません（`engine/src/prefill/prefill.cpp:3381-3384`）。

## 有効になる条件

- `--peer-device N` で peer GPU を有効にし、`--peer-prefill-rows` が 0 以外であることが必要です。server の prompt helper 設定が `Prefill::set_peer` を呼びます。`--peer-prefill-rows 0` なら呼び出されず、prompt は primary GPU に残ります（`engine/src/program/generate.cpp:13146-13153`）。
- `set_peer` が有効な peer を受け取り、少なくとも一つのレイヤーが peer の MMQ または int8 prompt path に対応する必要があります。NVFP4 experts の場合は setup が拒否され、Hadamard-folded pack の場合は警告を出して peer path を使わずに戻るため、この変数の読み取りまで進みません（`engine/src/prefill/prefill.cpp:3333-3372`）。
- `PeerExperts` の P2P 判定が false のときだけ読み取ります。P2P が使えない場合のほか、`STRATA_PEER_NO_P2P` による無効化や topology / copy 検証による host route もこの条件に入ります（`engine/src/core/peer_experts.cpp:208-235`; `engine/src/prefill/prefill.cpp:3335-3340,3373-3384`）。
- P2P が true ならこの変数は参照されず、peer transfer は P2P 経路を使います（`engine/src/prefill/prefill.cpp:3375-3384,6636-6647`）。
- `set_stage_helper` が作る layer-split helper も mapped host route を使いますが、この関数ではこの環境変数を読みません。直接の読み取りは `set_peer` の peer-device 経路だけです（`engine/src/prefill/prefill.cpp:3212-3253,3333-3387`）。読み取り箇所には OS や build macro による追加の分岐はありません。

## 実行時の詳細

値は `Prefill::set_peer` の setup 時に読みます。static cache には保存されませんが、作成済みの `PeerPrefill` はその時点で決まった stream を使い続けます。prompt path を作り直して `arm_prompt_helpers` が再実行されれば、その setup で改めて環境を読みます（`engine/src/prefill/prefill.cpp:3333-3387`; `engine/src/program/generate.cpp:13143-13169,19221-19230`）。

専用 stream を使う場合、primary compute stream 上の event を専用 stream が待ってから host route の activation と、必要な routing weight などのコピーを発行します。peer stream はコピー完了 event を待ちます。値がゼロならこれらのコピーを `m.cs` 上に発行するため、コピーと primary 側の後続計算を別 stream に分けません（`engine/src/prefill/prefill.cpp:6611-6633`）。専用 stream と event の作成に失敗すると `set_peer` は `prefill peer: copy stream` を返し、caller は `strata serve: prefill peer: copy stream - the prompt path stays on the primary GPU` を stderr に出して peer prompt 経路を使いません（`engine/src/prefill/prefill.cpp:3381-3386`; `engine/src/program/generate.cpp:13149-13153`）。

## ログと測定値

この環境変数の値に応じた有効・無効ログはありません。専用 stream 作成失敗時の文言と caller の fallback ログは「実行時の詳細」に記載したとおりです。Strata の資料・実装コメントに、この切替単独の測定値は記載されていません。

## 根拠

- `engine/src/prefill/prefill.cpp:3333-3340,3373-3387` — peer setup、P2P 条件、環境変数の読み取りと stream 作成。
- `engine/src/prefill/prefill.cpp:1373-1393,1414-1436` — host route の状態、stream/event の保持と破棄。
- `engine/src/prefill/prefill.cpp:6611-6633,6636-6647` — stream の選択とコピー発行。
- `engine/src/core/peer_experts.cpp:208-235` — P2P 判定から host route になる条件。
- `engine/src/program/generate.cpp:13143-13153,13169,19229` — peer prefill の setup 条件、失敗時の fallback、prompt path 再構築時の再 setup。
