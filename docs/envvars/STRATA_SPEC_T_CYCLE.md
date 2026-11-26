# `STRATA_SPEC_T_CYCLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の speculative decoding ループで、検証窓の行数 `T` を指定リストから順に選びます。通常の `choose_window` が決める幅を後から置き換えるため、窓幅ごとの測定に使う開発・ベンチ用の制御です。ドラフトの候補 token 自体を作る設定ではありません。ソースコメントも `bench only` としています（`engine/src/program/generate.cpp:24811-24821,25015-25042`）。

## 値と判定

speculative decoding ループに入ったとき、環境変数が未設定または空文字でなければ、カンマ区切りの各要素の先頭を `std::atoi` で整数変換します。変換結果が `1..o.spec` の範囲なら、順序や重複を保ったままリストに追加し、それ以外は黙って捨てます。文字列全体の数値妥当性は検査しません。`atoi` が数値の先頭部分を読むため、例では `2junk` は `2` として受理され、`0anything`、`-1`、`abc` は範囲外として無視されます。空要素も `atoi` の結果が `0` となり無視されます。空白や符号は `atoi` の変換規則に従います（`engine/src/program/generate.cpp:24814-24821`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| speculative decoding loop | サイクルなし。既定の窓選択を使う | 各 comma 要素の `atoi` 結果が `1..o.spec`。例: `1,2,8`（`o.spec >= 8` の場合）、`2junk` | 空文字、`0`、`-1`、`abc`、`o.spec` より大きい値。無効要素だけならサイクルなし |

大文字小文字は関係しません。区切り文字はカンマだけです。値は起動時設定として保存されるのではなく、ループ開始時に読み、その呼び出し中の `t_cycle` ベクターに保持します。値の不正を知らせる専用警告やエラーはありません（同 `24814-21`）。

## 有効になる条件

- `strata generate` で speculative decoding ループが開始される必要があります。生成ループ開始位置が設定され、生成 token が残り、既に EOS で終了していないことが条件です。`--spec 0` ではループ開始位置が設定されません（`engine/src/program/generate.cpp:24455-24466`、`engine/include/strata/spec/spec_start.hpp:14-17`）。
- `o.spec` は CLI の `--spec` 等から最終的に決まる幅の上限です。リスト要素がこの幅を超えると採用されません（`engine/src/program/generate.cpp:4040,24817-24821`）。
- 最初の検証窓はサイクル対象外です。特に native pack では `first_window` が真で始まり、その窓を `T=1` に固定します。以降の窓からリストを適用します（`engine/src/program/generate.cpp:24835,25040-25042`）。
- `--suffix-draft` がそのラウンドで lookup 窓を選ぶと、その幅がサイクル後に `T` を上書きします。遅延 DFlash2 lookup の `dfr_lookup` も幅を上書きします（`engine/src/program/generate.cpp:25042-25059`）。
- 実行時の `win_cap` と残り context `room` の小さい方を超える幅は、その値まで縮められます。さらに `--lookup-chain` が条件を満たす場合は、窓の後ろに追加行を加えます（`engine/src/program/generate.cpp:25060-25080`）。VRAM 不足で窓幅が縮退した場合は `win_cap` も引き下げられます（同 `25129-25141`）。
- `use_mtp && mtp.prob() && spec_gate_pick()` が真で、ほかの gated 条件も満たす場合、有効なサイクルリストは「独自の窓ルール」として gated proposal を無効にし、従来の acceptance rule に戻します。stderr に `STRATA_SPEC_PROB=1 keeps the older acceptance rule in this run (STRATA_SPEC_COST, STRATA_SPEC_T_CYCLE, DFlash2 and --spec-corrupt change the window by their own rule). That rule's output distribution is off when the confidence gate fails; STRATA_SPEC_PROB_GATE=top is exact here.` と出ます（`engine/src/program/generate.cpp:24842-24847,3543-3562`）。
- 対象名の実読み取りは `generate.cpp` の CLI speculative loop 内の 1 箇所です。`--serve` のリクエスト処理にはこの変数の読み取りがなく、サーバーの窓選択には適用されません（同ファイルの実読み取り `24814-21`。server 側の gated 判定 `21427-21430` もこの変数を参照しません）。

## 実行時の詳細

読み取りは speculative loop の初期化時に一度だけ行われ、各ラウンドで `rounds % t_cycle.size()` の要素を選びます。`first_window` では上書きを行いません。native pack で最初の窓がスキップされるため、最初のサイクル選択は `rounds == 1` の要素、すなわち通常はリストの 2 番目からになります。非 native pack で `first_window` が偽なら最初のラウンドから先頭要素です（`engine/src/program/generate.cpp:24835,25015-25042,25199`）。

プロセス内で環境変数を後から変更しても、読み取り済みのリストには反映されません。各幅の最初の timed round は `t_cycle_seen` で計測対象から外し、2 回目以降の round 時間を集計します（同 `24831-24832,25229-25242`）。

## ログと測定値

有効なサイクルがある場合、終了時に stdout へ `window cost (ms/round)` を出し、計測できた幅ごとに `T幅:平均ミリ秒(n=件数)` を表示します。幅の計測サンプルがない場合、その幅は表示されません。無効値だけ、unset、空文字ではこの集計行も出ません（`engine/src/program/generate.cpp:25279-25283`）。

サイクル幅の verifier graph を確保できず、`ver.run` が out-of-memory を返した場合、初回窓でなく gated proposal でもなければ、その窓幅を上限として以降を狭め、stderr に `strata generate: not enough VRAM left for a %d-token verify window: windows are %d tokens at most from here` と出して同じラウンドを再試行します。それ以外の verifier 失敗は `strata generate: %s` を stderr に出して終了コード 1 です（同 `25129-25141`）。

## 根拠

- `engine/src/program/generate.cpp:24811-24821` — コメント、環境読み取り、カンマ分割、`atoi`、受理範囲。
- `engine/src/program/generate.cpp:24831-24847,25015-25080` — ループ内の初期化、窓幅の選択・上書き・clamp・chain。
- `engine/src/program/generate.cpp:25129-25141,25229-25242,25279-25283` — verifier の失敗・縮退、計測除外、stdout 集計。
- `engine/src/program/generate.cpp:24455-24466`、`engine/include/strata/spec/spec_start.hpp:14-17` — speculative loop の開始条件。
- `engine/src/program/generate.cpp:24842-24847,3543-3562` — gated proposal との相互作用と警告。
- `engine/src/program/generate.cpp:21427-21430` — server 側の gated 判定。この判定は対象変数を参照しません。
