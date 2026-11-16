# `STRATA_DRAFT_COSTS_LEARN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`--draft-costs` の学習経路を選ぶ内部用スイッチです。値が有効で、指定されたコスト表を読み込めないとき、通常のリクエストから受動的に表を作る経路ではなく、窓サイズを測る一括学習経路を有効にします。この経路は窓の選択と学習用の filler 窓を変えます。`--draft-costs` がないと機能せず、既存の有効な表や作成途中の表を強制学習へ切り替えません。コードコメントではテスト harness 専用で、server と launcher は設定しないスイッチとされています（`src/program/generate.cpp:15253-15262`）。

## 値と判定

C++ の `std::getenv` で値を取得し、未設定でないことと `v[0] == '1'` だけを調べます。文字列全体の parse や数値検証はしません。最初の 1 バイトが ASCII `1` なら残りは無視されます（`src/program/generate.cpp:15260-15261`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 読み取りブロックに入った場合 | 無効 | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `01` |

空文字は設定済みですが、先頭文字が `1` ではないため無効です。大文字小文字、後続文字、数値としての妥当性、値域は検査しません。値を読むのは `--draft-costs` のパスが空でなく、`DraftPolicy` が固定コスト状態でない場合だけです（`src/program/generate.cpp:15253-15262`）。

## 有効になる条件

- `--draft-costs <path>` が指定されていること。CLI パーサーはこの引数を `o.draft_costs` に入れます（`src/program/generate.cpp:4013-4014`）。
- `DraftPolicy` に固定コストが適用されていないこと。`STRATA_SPEC_FIXED=1` は `DraftPolicy` の固定状態を作り、この場合この変数の読み取りブロックを通りません（`src/spec/draft_policy.cpp:33-54,447-452`）。
- 指定されたコスト表が読み込み可能な通常の表ではないこと。未設定・空文字を含む無効値では、表が読めない場合に受動学習へ進みます。有効値でも表が読めればロード済み表を使い、値が無効でも読めない表なら受動学習になります（`src/program/generate.cpp:15262-15314`）。
- `cf.fresh` の作成途中テーブルが読み込めた場合も受動学習を続けます。有効値はこの分岐を上書きしません（`src/program/generate.cpp:15263-15278`）。
- 実際に一括学習が有効な間は、決定的な提案などの条件を満たす request/decode round で、通常の方策が選ばない窓サイズを測るための filler 窓を試します。確率的 MTP 提案など一部の経路では強制窓を使いません（`src/program/generate.cpp:20363-20391,20426-20433`）。

## 実行時の詳細

値はエンジンの serve 初期化時、コスト表を扱う条件ブロック内で一度読み、`dc_force_learn` に保存されます。以後の request ごとには読み直さず、プロセス実行中の環境変更は反映されません（`src/program/generate.cpp:15253-15262`）。

この変数が有効で表を読めないと `policy.set_learning(true)` と `dc_learning = true` に進みます。学習モードでは各 `GEN` / `GENI` request の到着を新しい busy run として扱い、通常の 0.5 秒 idle 判定を使いません。各 request の開始時点で busy age をリセットし、開始から 6 秒以内の round は fresh として計測されます（`src/program/generate.cpp:17016-17023`; `include/strata/spec/draft_policy.hpp:52-60`）。一括学習は合計 1000 timed rounds と各窓サイズ 20 rounds 以上を基準に完了判定します（`src/program/generate.cpp:15237-15238`; `include/strata/spec/draft_policy.hpp:87-93`）。

完了し、測定が乱れていない場合は窓コストをファイルへ書き、学習を終了して同じエンジンの次 request から固定コストを使います。乱れを検出した場合は学習データをリセットして学び直します。書き込みに失敗しても実行中の表は設定されますが、次回起動で読み込めず再学習になる旨がログに出ます（`src/program/generate.cpp:20869-20924`）。

優先関係は、固定状態ならコスト表処理ごとスキップ、固定でなければ既存表の読み込み結果が環境変数より優先、表がない／無効ならこの環境変数の判定で受動学習か一括学習を選ぶ順です。`--draft-costs-key` や他の CLI 設定は表のキーに反映され、異なる設定の表は読み込み不一致になり得ます（`src/program/generate.cpp:4013-4014,15253-15314`; `src/spec/draft_policy.cpp:263-271`）。

## ログと測定値

この環境変数専用の有効／無効ログや parse エラーはありません。無効値または unset で表がない場合は、stderr に `strata serve: draft costs: no table for this machine yet (...)` と出て受動学習になります。有効値で表が読めない場合は `strata serve: draft costs: learning this machine's table (...)` と出ます。成功時は `strata serve: draft costs: this machine's table is learned (...)`、学習が乱れた場合は `strata serve: draft costs: the learning stretch looks disturbed (...): it is learned again` が出ます（`src/program/generate.cpp:15270-15313,20871-20875,20921-20924`）。

`docs/DETAILS.md` に本変数の動作や測定値の記載は見つかりませんでした。測定性能値は記載していません。

## 根拠

- `src/program/generate.cpp:15253-15314` — 読み取り条件、値判定、表の状態に応じた分岐、起動ログ。
- `src/program/generate.cpp:17016-17023` — request 到着時の busy run 判定。
- `src/program/generate.cpp:20363-20391,20426-20433` — 一括学習中に試す filler 窓。
- `src/program/generate.cpp:20869-20924` — 学習完了・リセット・保存とログ。
- `src/spec/draft_policy.cpp:33-54,263-271,432-443,447-452` — 固定コスト環境、表のキー確認、学習表の確定、固定状態。
- `include/strata/spec/draft_policy.hpp:52-60,87-93` — busy run の条件と学習完了判定の定数。
- `src/program/generate.cpp:4013-4014` — 関連 CLI 引数。
