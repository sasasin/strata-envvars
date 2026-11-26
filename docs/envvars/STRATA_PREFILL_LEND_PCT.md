# `STRATA_PREFILL_LEND_PCT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

自動 prefill chunk の選定と自動 layer split の開始可能性判定で、prompt 用バッファを確保するため expert cache から借りる slot 数の割合上限を指定する。上限を超える借用が必要な chunk は自動選定から外れ、条件によっては prompt 用の独立バッファやより小さい chunk が使われる。借用した slot の expert は prompt 中に cache 外から読み込まれ、prompt 後に補充される。これは貸出量の計画値であり、生成結果を選ぶ設定ではない（CUDA 実装 `engine/src/program/generate.cpp:11229-11242,11333-11415`、SYCL 実装 `engine/sycl/src/program/generate.cpp:6665-6678`）。

環境変数は `engine/src/program/generate.cpp` に 3 箇所、`engine/sycl/src/program/generate.cpp` に 1 箇所あり、全て `std::getenv` で直接読み取る。CUDA 側では自動 layer split の候補評価と開始可能性 probe、および通常の prefill chunk 計画に使い、SYCL 側では prefill chunk 計画に使う（同 CUDA ファイル `7063-7068,10070-10104,11229-11243`、SYCL ファイル `6665-6678`）。

`--prefill auto` などで自動選定に入らなければ、この割合上限は通常の固定 chunk の貸出判定には使われない。CLI の `--prefill` は自動選定を選ぶ別の条件であり、この環境変数だけでは `o.prefill_auto` は有効にならない（`engine/src/program/generate.cpp:4000-4008,11333-11350,11411-11415`）。自動 layer split の探索・probe は別途この割合を使う（同ファイル `7182-7204,10070-10104`）。

## 値と判定

読み取り値が未設定でなければ `std::atoi` の結果を割合として使う。文字列全体の検証はなく、`atoi` が数値として認識する先頭部分だけが変換される。従って空文字、数値で始まらない文字列、`0` は `0`。`1` は 1%、`100` は 100%、`-1` は負の割合、`101` は 101% として扱われる。` 25tail` は 25 になる。大文字小文字の規則はなく、真偽値文字列 `true` / `false` は数値に変換できず 0 になる。コードに範囲 clamp はない（CUDA `engine/src/program/generate.cpp:7063-7068,10081-10086,11238-11243`、SYCL `engine/sycl/src/program/generate.cpp:6674-6678`）。

| 条件 | unset | 有効になる値（例） | 値としての判定・境界 |
|---|---|---|---|
| CUDA の `engine/src/program/generate.cpp` | `g_lend_keep != 128` なら 100。そうでなければ `Prefill::pinned_share() >= 0.9` で 90、未満なら 85 | 数値接頭辞を持つ整数。例: `1`, `85`, `100` | 設定値は `atoi`。空文字、`true`、`abc`、`0anything` は 0。負値もそのまま使われ、100 超も clamp されない |
| SYCL の `engine/sycl/src/program/generate.cpp` | `Prefill::pinned_share() >= 0.9` なら 90、未満なら 85 | 数値接頭辞を持つ整数。例: `1`, `85`, `100` | 設定値は `atoi`。空文字、`true`、`abc`、`0anything` は 0。負値もそのまま使われ、100 超も clamp されない |

CUDA の未設定時だけ `g_lend_keep` による例外がある。設定値を指定すると、この既定分岐ではなく `atoi` の値が使われる。SYCL にはこの `g_lend_keep != 128` 分岐はない（上記各読み取り箇所）。`atoi` の認識範囲を超える文字列の動作は文書化しない。

## 有効になる条件

- 一般の chunk 計画では prompt の借用経路が有効であること。`--no-prefill-borrow` や他の条件で借用が無効なら、この割合で slot を貸し出さない。CUDA の Linux HIP には別の貸出可否ルールもある（`engine/src/program/generate.cpp:9533-9544`）。
- 通常の割合制限は `--prefill auto` の選定で使われる。CUDA は候補 chunk の必要 slot 数 `k` が `k * 100 <= kAutoLendPct * cache_slots` を満たすか確認し、さらに `g_lend_keep` 分を残せることを要求する（`engine/src/program/generate.cpp:11333-11350,11361-11397`）。SYCL も自動 scan の `fits` 判定に割合を渡す（`engine/sycl/src/program/generate.cpp:7297-7333`）。
- 固定 `--prefill N` の通常 chunk 選定は、割合ではなく `k + g_lend_keep <= cache_slots` を確認する。したがって値を設定しても固定 chunk の貸出量をこの割合に制限するものではない（`engine/src/program/generate.cpp:11411-11415`）。ただし CUDA の自動 layer split は prompt が固定 chunk でも 512-token の開始可能性判定に割合を使う（`engine/src/program/generate.cpp:7130-7134,7182-7204,10070-10104`）。
- CUDA の自動 layer split の placement 探索は、各 stage が割合上限内で借りられる chunk があるかを候補評価に使う。最後の 512-token probe では各 stage が上限内で借りられない場合、512 MiB の余裕を加えた独立バッファを確保できるかを調べる（`engine/src/program/generate.cpp:7130-7134,7182-7232,10070-10119`）。
- CLI / server のどちらかだけに限定する条件は、この値の読み取り箇所にはない。server の per-stage loan 計画にも同じ割合が渡される（CUDA `engine/src/program/generate.cpp:11967-12041`、SYCL `engine/sycl/src/program/generate.cpp:7297-7333`）。
- CUDA と SYCL で未設定時の既定値が異なる条件は上表の通り。ソース上の読み取り箇所に OS や GPU 世代による値判定はない。CUDA/HIP 共通の `engine/src/program/generate.cpp` 実装と SYCL 実装の外へは一般化しない。

## 実行時の詳細

CUDA の値は自動 layer split の配置候補評価で lambda を実行したとき（`engine/src/program/generate.cpp:7063-7068`）、split が決まった後の startability probe でそのブロックに入ったとき（`10070-10086`）、および prefill chunk 計画の初期化時（`11229-11243`）に、それぞれ読み取られる。SYCL は prefill chunk 計画時に読む（`engine/sycl/src/program/generate.cpp:6665-6678`）。読み取り結果は各 lambda / 計画の値として保持され、その計画中に環境変数を再読込するコードはない。関数内の `static` cache ではないため、別の生成処理では再評価され得る。

自動 chunk 選定では、必要な貸出 slot 数が割合上限と cache の保持 slot 数の両方に収まる最大 chunk を探す。CUDA の ring byte budget を使う経路では、割合に基づく slot 予算を ring の予算にも使い、候補 chunk を 256-token 単位で探索する。ring-byte 機能が無効な経路は旧 chunk 候補列を使う（`engine/src/program/generate.cpp:11333-11409`）。SYCL も 256-token 単位の scan を行い、stage ごとに貸出可能か判定する（`engine/sycl/src/program/generate.cpp:7311-7333`）。上限に収まる chunk がないとき、CUDA の server 計画は auto chunk を 1024 にする経路があり、独立バッファを使う経路もある（`engine/src/program/generate.cpp:12797-12814`）。

この変数の値を CLI 引数や別の環境変数で上書きするコードは読み取り箇所にはない。未設定時の割合だけは CUDA で `g_lend_keep`、両 backend で pinned share の状態から決まる。環境を変えた後の挙動は、次の計画または生成処理が環境を読む時点で評価される。

## ログと測定値

自動 chunk の選定結果は stderr に `strata generate: prompt chunk auto: %lld tokens` の形式で出る（`engine/src/program/generate.cpp:24061-24064`）。自動 layer split の probe が 512-token chunk の借用も独立バッファも確保できないと判定した場合、stderr に `strata generate: layer split auto: L2 probe: CUDA%d cannot start the prompt path: ...` と理由を出し、次行で `to make room` の提案を出す（`engine/src/program/generate.cpp:10102-10119`）。SYCL の serve では stage により大きい chunk が使えず縮小した場合、`strata serve: WARNING: prompt chunk ...` に、auto のとき `lend at most N%` を含めて出す（`engine/sycl/src/program/generate.cpp:7349-7378`）。割合単独を表示する起動ログは確認できない。

`docs/DETAILS.md:1569-1571` は `--prefill auto` の chunk / ring の一般動作を記述しているが、この環境変数の具体的な値判定や既定値は記載していない。数値例はコメント中の測定条件が限られるため、この変数による性能効果としては記載しない。

## 根拠

- CUDA 値の変換と unset fallback: `engine/src/program/generate.cpp:7063-7068,10081-10086,11238-11243`
- CUDA auto split slot 判定と probe: `engine/src/program/generate.cpp:7130-7232,10070-10119`
- CUDA auto chunk / ring 予算: `engine/src/program/generate.cpp:11333-11415`
- CUDA CLI が `--prefill auto` を選ぶ判定: `engine/src/program/generate.cpp:4000-4008`
- CUDA serve の chunk 計画と fallback: `engine/src/program/generate.cpp:11967-12041,12797-12814`
- SYCL 値の変換と unset fallback: `engine/sycl/src/program/generate.cpp:6665-6678`
- SYCL auto chunk scan と警告: `engine/sycl/src/program/generate.cpp:7297-7378`
- 既存の一般説明: `docs/DETAILS.md:1569-1571`
