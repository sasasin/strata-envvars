# `STRATA_VERIFY_NODES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

verify の window graph と MTP drafter graph の構成を stderr に出すデバッグ用スイッチです。グラフ捕捉後にノード種別・名前と個数を列挙するだけで、verify や MTP の計算・生成結果を選択する条件には使われません。CUDA/HIP verify、SYCL verify、および CUDA/HIP 系の MTP graph capture に読み取り箇所があります（`engine/src/core/verify.cpp:3291-3358`、`engine/sycl/src/core/verify.cpp:2089-2090,2136-2159`、`engine/src/core/mtp.cpp:1085-1134,1553-1569`）。

## 値と判定

| 経路 | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA verify | 出力なし | 空文字を含む、設定されている値すべて。ノード数・種別を出力 | 該当なし。値の内容は判定しない |
| HIP verify | 出力なし | 設定されている値すべてでノード集計を出力。`atoi(value) >= 2` のときはさらにグラフ順のノード名を出力 | 設定値が `atoi` で 2 未満なら順序付き一覧のみ出ない。設定有無による集計出力は止まらない |
| SYCL verify | 出力なし | 空文字を含む、設定されている値すべて | 該当なし。値の内容は判定しない |
| MTP graph | 出力なし | 空文字を含む、設定されている値すべて（ただし Metal を除く） | 該当なし。値の内容は判定しない |

HIP verify の数値判定は文字列全体の検証ではなく `std::atoi` です。したがって `2`、`02`、`+2`、` 2tail` は 2 以上として順序付き一覧を有効にし、`1`、`0`、`-1`、空文字、`true`、`2tail` のように数字で始まらない値は有効にしません。数値の後ろの文字は無視されます。`atoi` の範囲外入力の結果はコードで制約されていません。ほかの経路は `getenv(...) != nullptr` だけを調べるため、空文字や `0`、`false` も設定済みとして扱います（`engine/src/core/verify.cpp:3292,3320,3331`、`engine/sycl/src/core/verify.cpp:2089,2136`、`engine/src/core/mtp.cpp:1087`）。

## 有効になる条件

- CUDA verify は `engine/src/core/verify.cpp` の HIP でも Metal でもないビルド分岐で動きます。ノード名の取得は `CUDART_VERSION >= 12030` の場合だけ行い、それ未満では kernel node の表示名を `type<番号>` のまま集計します（`engine/src/core/verify.cpp:3330-3349`）。PDL edge の追加情報も `CUDART_VERSION >= 12030` の場合に限られます（同:3359-3385）。
- HIP verify は `STRATA_USE_HIP` 分岐で動き、設定値が空でないかではなく設定済みかをまず見ます。設定済みなら HIP の graph node API で集計し、`atoi` の値が 2 以上なら先頭最大 400 ノードの名前も出します（`engine/src/core/verify.cpp:3291-3328`）。
- SYCL verify では、通常の graph capture が成功した経路でノードを列挙します。`STRATA_VERIFY_EAGER` が設定されていると `capture` は graph を作らず戻るため、ノード一覧は出ません。stepped かつ all-resident でない場合は分割 capture に入り、変数設定時に出るのは segment 数だけで、各 segment の node 一覧は出ません（`engine/sycl/src/core/verify.cpp:2089-2090,2098-2136`）。
- MTP は graph の capture と instantiate が成功した場合に一覧処理を呼びます。Metal ビルドでは helper の Metal 分岐がノード列挙を行わないため、設定しても MTP node 一覧は出ません（`engine/src/core/mtp.cpp:1086-1134,1553-1569`）。
- graph が既にキャッシュされている経路では capture 関数が先に戻るため、この変数を後から設定してもその graph の一覧は出ません（CUDA/HIP verify: `engine/src/core/verify.cpp:3254-3257`、SYCL verify: `engine/sycl/src/core/verify.cpp:2098-2105`、MTP: `engine/src/core/mtp.cpp:1577-1579,1595-1598,1636-1639`）。
- CLI 引数、設定ファイル、別の環境変数による値の上書き・優先順位はありません。コード上、この変数は出力条件にだけ使われます。

## 実行時の詳細

各 capture 経路が graph を作る際に `getenv` を直接呼びます。値を static cache したり起動時に一括評価したりしません。従ってプロセス内で値が変われば、まだ capture されていない graph では新しい設定が参照されますが、キャッシュ済み graph は capture を再実行しないため再表示されません（`engine/src/core/verify.cpp:3254-3257,3291-3331`、`engine/sycl/src/core/verify.cpp:2089-2105,2136`、`engine/src/core/mtp.cpp:1086-1087,1553-1569,1577-1579`）。

CUDA verify は各 window graph の node 種別と、取得可能な kernel 名を個数順に最大 40 種出力します。また CUDA 12.3 以降では graph edge と programmatic (PDL) edge の件数も出力します。HIP verify は node 種別・kernel 名を個数順に最大 80 種出し、値が 2 以上なら graph 順の node 名を最大 400 件、各名最大 110 文字で追記します（`engine/src/core/verify.cpp:3291-3328,3330-3385`）。

SYCL verify は通常 capture で node 種別の個数を最大 40 種出し、kernel 名は取得せず `kernel` と表示します。SYCL の分割 capture 経路は `the %d-token window as %zu graph segments` の segment 数表示です（`engine/sycl/src/core/verify.cpp:2089-2090,2136-2159`）。MTP は成功した prefill / round / step graph の node 種別・名前の件数を stderr に出します。CUDA では kernel node を `kernel` とし、HIP の非 Windows build では取得できた kernel 名を使います（`engine/src/core/mtp.cpp:1085-1134,1553-1569`）。

いずれも診断出力の条件であり、値に応じた fallback や変数固有のエラー・終了経路はありません。graph capture 自体の失敗は通常の verify/MTP capture error として返りますが、この変数が失敗を起こす分岐はありません（`engine/src/core/verify.cpp:3270-3289`、`engine/sycl/src/core/verify.cpp:2082-2095,2106-2134`、`engine/src/core/mtp.cpp:1553-1569`）。

## ログと測定値

出力先は stderr です。CUDA/HIP verify は `strata verify: the %d-token window graph has %zu nodes:`、SYCL verify は同じ window graph 見出し、または分割時に `strata verify: the %d-token window as %zu graph segments` を出します。MTP は `strata mtp: the %s graph has %zu nodes:` を出します（`engine/src/core/verify.cpp:3325-3357`、`engine/sycl/src/core/verify.cpp:2090,2157-2159`、`engine/src/core/mtp.cpp:1131-1133`）。この変数に関する測定値はありません。

## 根拠

- `engine/src/core/verify.cpp:3254-3257,3291-3385` — CUDA/HIP verify の capture cache、設定判定、ノード・edge 診断。
- `engine/sycl/src/core/verify.cpp:2089-2105,2136-2159` — SYCL の分割/eager 条件、通常 graph の node 診断。
- `engine/src/core/mtp.cpp:1085-1134,1553-1569,1577-1657` — MTP の node 診断 helper、成功した graph capture 後の呼び出しと capture cache。
