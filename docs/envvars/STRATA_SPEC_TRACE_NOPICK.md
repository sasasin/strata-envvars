# `STRATA_SPEC_TRACE_NOPICK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`serve` の通常の prompt/suffix lookup 選択経路で、policy が選んだ lookup draft を候補として記録しつつ、そのラウンドの window には採用しない診断用フラグです。環境変数が設定されているかだけで判定され、設定値自体は解釈されません。

## 値と判定

| 状態 | 判定 | 通常の lookup 選択経路での結果 |
|---|---|---|
| 未設定 | `getenv()` が `nullptr` | `trace_nopick` は false。policy が選んだ lookup を採用可能 |
| 任意の設定値 | `getenv()` が非 `nullptr` | `trace_nopick` は true。空文字、`0`、`false` を含め lookup の採用を抑止 |

文字列比較、数値変換、範囲検査はありません。関数内 `static const bool` なので、この判定が初めて評価された後にプロセス環境を書き換えても反映されません（`src/program/generate.cpp:17380-17382`）。

## 有効になる条件

- 対象コードは `serve` の生成ループです。候補探索・policy 判定に到達するには `--suffix-draft` が正で、かつ初回 window ではない必要があります（`src/program/generate.cpp:18220-18235`）。
- suffix lookup の候補 `k` が正で、MTP が有効な場合は候補先頭が MTP の先頭 draft と一致する場合、または確率的 MTP window の場合に policy 判定へ進みます。MTP がない場合は候補が正なら判定へ進みます（`src/program/generate.cpp:18230-18235`）。
- `STRATA_SPEC_TRACE` が別途設定されていなければ、変数名のコメントにある「logged」は実際のファイル記録を意味しません。serve 側の trace file は `STRATA_SPEC_TRACE` が空でない場合だけ開かれます（`src/program/generate.cpp:17380-17382`）。
- DFlash2 の長い suffix match で draft を延期した経路では、このフラグによる抑止を通りません。延期後の policy が lookup を選ぶと `dfr_lookup` が立ち、後段で lookup window を直接設定します（`src/program/generate.cpp:18138-18144,18183-18190,18245-18252`）。
- `--lookup-chain` による別の chained lookup 経路や CLI の通常生成ループには、このフラグの参照がありません。

## 実行時の詳細

通常経路では suffix history から候補を作り、必要な条件の後に `DraftPolicy::choose()` を呼びます。policy が `pk.lookup` を選んだとき、フラグが未設定なら `T` を lookup の長さにし、`from_sfx` を立てます。フラグが設定済みならこの更新をしないため、既定の MTP window（MTP がなければ通常 1 token）を使います。`--lookup-max-t` による graph-fit 調整も同じ抑止条件の内側にあり、lookup を採らない場合は呼ばれません（`src/program/generate.cpp:18210-18219,18233-18242`）。

serve の `STRATA_SPEC_TRACE` は追跡対象 round の後で、位置・window 長・受理数・`from_sfx`・候補数/一致長・MTP draft・suffix lookup 候補列・確定 token 列をファイルに追記します。trace は非初回 window だけ記録します。ファイルを開けなかった場合も記録されず、ここで専用の警告は出ません（`src/program/generate.cpp:17380-17382,18639-18650`）。この trace とは別に、このフラグ自体が出す stdout/stderr のログやエラー処理はありません。

## 根拠

- 読み取りと process 内 cache: `src/program/generate.cpp:17380-17382`。
- 通常経路の候補条件、policy 判定、lookup 採用の抑止: `src/program/generate.cpp:18220-18242`。
- serve trace の候補列と結果の出力: `src/program/generate.cpp:17380-17382,18639-18650`。
- DFlash2 deferred lookup の条件とフラグを通らない採用経路: `src/program/generate.cpp:18138-18144,18183-18190,18245-18252`。
