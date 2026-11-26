# `STRATA_SPEC_TRACE_NOPICK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の生成ループで、suffix prompt lookup が選択された場合にも lookup の候補を検証窓に採用しない診断用スイッチです。候補の記録用配列には候補をコピーできますが、検証窓の幅・入力列を lookup に切り替えません。また、学習モードで候補がない場合に lookup 用の窓幅を試す処理も止めます。値を設定しただけでログファイルを開くわけではなく、候補のログには別途 `STRATA_SPEC_TRACE` が必要です（`engine/src/program/generate.cpp:21658-21664,22714-22755`）。

## 値と判定

`std::getenv(...) != nullptr` の有無だけで判定し、値の文字列や数値は変換しません。未設定なら `false`、空文字を含め設定されていれば `true` です。したがって `0`、`false`、`0anything`、空文字もすべて有効で、大文字小文字・空白・数値としての妥当性の検査はありません（`engine/src/program/generate.cpp:21660`）。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| serve の共通生成ループ | suffix lookup 候補の採用抑止なし | 値を問わず、環境変数が存在すること | なし。空文字も有効 |

## 有効になる条件

- 対象コードは `o.serve` の分岐内にある serve ループです。通常の非 serve CLI 生成経路にはこの読み取り箇所がありません（`engine/src/program/generate.cpp:11884,16397-16410,21660`）。
- suffix lookup 候補の選択処理自体が走るには、`--suffix-draft` が有効（`o.suffix_draft > 0`）で、最初の window ではなく、候補 `k` があり、かつ確率的 MTP、drafter 無効、または候補の先頭と drafter の先頭が一致する条件が必要です。そのうえでポリシーが `pk.lookup` を返す場合に、この変数が候補を採用しないようにします（`engine/src/program/generate.cpp:22714-22742`）。
- 候補がない場合の学習用 lookup 窓の探索も、`dc_learning && draft_on && !probabilistic` の場合に限り通常は行われますが、この変数が設定されていると抑止されます（`engine/src/program/generate.cpp:22742-22755`）。
- `--lookup-chain` による MTP 後段への chain 追加は、このフラグの判定を通らない別処理です。従ってこの変数だけでは lookup-chain を無効化しません（`engine/src/program/generate.cpp:22769-22787`）。
- `STRATA_SPEC_TRACE` は独立した設定です。空でないファイル名を指定し、ファイルを開けたときだけ serve trace を出力します。この変数だけではトレースファイルを作成・指定しません（`engine/src/program/generate.cpp:21658-21660`）。

## 実行時の詳細

この変数は serve リクエストの生成処理に入った際に関数内 `static const bool` として初期化され、プロセス内で一度だけ読み取られます。最初にこの宣言へ到達した後に環境を変更しても反映されません（`engine/src/program/generate.cpp:21660`）。

通常の suffix lookup では `sfx.propose` の候補を `tr_s` に記録した後、ポリシー選択 `policy.choose` を行います。フラグが有効だと、`pk.lookup` が返っても `T` を lookup の幅に変更せず `from_sfx` も立てず、lookup padding や `--lookup-max-t` による lookup 窓の調整も行いません。実行される検証窓は既に選ばれていた窓のままです。候補なしの学習用 lookup 窓の探索も実行しません（`engine/src/program/generate.cpp:22702-22755`）。

`STRATA_SPEC_TRACE` のファイルが開いている場合、lookup 候補は timed round の記録行に含まれます。行には `from_sfx`（採用有無）、`tr_k` / `tr_match`、lookup draft の token ID 列などが出力されます。フラグが有効でも候補は記録され得ますが、`from_sfx` は採用を示さないままです（`engine/src/program/generate.cpp:21658-21664,22714-22721,23195-23205`）。

## ログと測定値

この変数自身による stdout / stderr のログ、警告、エラー文言はありません。候補の記録は `STRATA_SPEC_TRACE=<file>` が設定され、空でないパスを開けた場合に限り、そのファイルへ timed round ごとに行われます。実装上の行形式は `R p T a sfx ms k match | probs | drafts | lookup draft | committed tokens` です（`engine/src/program/generate.cpp:21658-21660,23195-23205`）。

この変数に関する測定値は、調査した Strata ソースおよび `docs/DETAILS.md` では確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:11884` — serve 専用の分岐。
- `engine/src/program/generate.cpp:21658-21664` — trace ファイルと対象環境変数の読み取り、static cache。
- `engine/src/program/generate.cpp:22714-22755` — suffix lookup の候補選択・採用抑止と学習用探索の抑止。
- `engine/src/program/generate.cpp:22769-22787` — 別経路の lookup-chain。
- `engine/src/program/generate.cpp:23195-23205` — timed round trace の出力。
