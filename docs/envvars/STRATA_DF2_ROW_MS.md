# `STRATA_DF2_ROW_MS`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

DFlash2 の適応 window 選択で、次の verify row を追加するために必要な推定効率の下限（ミリ秒相当）を指定します。値が大きいほど条件を満たす row が少なくなり、小さい値ほど上限まで row を追加しやすくなります。既定値は `3.0` です。

この値を使った window 選択は、サーバー側で `STRATA_DF2_GATE` が有効になり、現在の request が DFlash2 で draft している場合に限られます。CLI 側では row-ms getter の呼び出しも gate 選択もありません。

## 値と判定

| 環境変数の状態 | `df2_gate_row_ms()` の結果 |
|---|---:|
| 未設定 | `3.0` |
| 空文字 | `3.0` |
| 数値文字列 | `std::atof` の変換結果 |
| 数値として変換できない文字列 | `std::atof` の結果 `0.0` |

文字列全体の妥当性検査や範囲制限はありません。`std::atof` のため、数値の前後の空白や数値部分の後ろに続く文字列は拒否されず、数値部分が変換されます（例: `4ms` は `4.0`）。不正文字列はエラーや警告にならず `0.0` になり、空文字と同じ既定値扱いにはなりません。負値やゼロもそのまま使われます。

適応 gate は `survival * ms_per_tok < row_ms` になったところで row 追加を止め、それ以外は `cap` まで追加します。したがって `0` や負値では通常の非負推定値が下限を下回らず、window は上限まで拡張されやすくなります。変換結果の有限性を検査するコードもありません。

## 有効になる条件

- `STRATA_DF2_GATE` が設定され、その先頭文字が `1` であること。値全体の比較ではないため、`1`, `10`, `1anything` は有効で、未設定・空文字・`0`・`true` は無効です。
- サーバー request が DFlash2 を実際の draft source として使い、`req_df2 && draft_on` であること。
- 最初の window ではないこと。最初の window は gate 判定後に `merge_T` または `1` に戻されます。

条件を満たした後続 window では、通常の `choose_window()` が `--draft-conf` などから選んだ値を gate の選択で置き換えます。gate は最大幅 `S_mtp` を超えません。DFlash2 のモデル／backend が利用できず request が DFlash2 draft を使わない場合、この変数は実際の window を変えません。

## 実行時の詳細

`df2_gate_row_ms()` は `static const double` を返します。最初の呼び出し時に環境を読み、その後はプロセス内で値をキャッシュします。サーバー処理では request ごとに作る `AdaptiveGate` にこの値を設定しますが、実行中に環境を変更しても getter の値は再読込されません。

gate の初期 `ms_per_tok` は `0` で、初回 window 選択時は `9.0` ms を使います。timed DFlash2 rounds の結果から、round の実時間を committed token 数で割った値を EMA 更新し、各 round で得た draft 生存率の観測と合わせて次の window を決めます。`row_ms` 自体は観測で更新されません。

この環境変数専用のログ、警告、parse エラー、終了経路はありません。観測可能な影響は gate が選ぶ verify window の幅です。通常の生成・verify に別の失敗が生じた場合のエラー処理はこの変数の値に固有ではありません。

## 根拠

- `include/strata/spec/window_rule.hpp:122-124` — 未設定・空文字時の `3.0`、`std::atof` による変換、static cache。
- `include/strata/spec/window_rule.hpp:73-99` — gate の適応窓判定、初期 timing fallback、`row_ms` と `cap` の使用。
- `include/strata/spec/window_rule.hpp:101-115` — draft の生存観測と committed token あたり時間の EMA 更新。
- `include/strata/spec/window_rule.hpp:118-120` — `STRATA_DF2_GATE` の先頭文字判定。
- `src/program/generate.cpp:18020-18022` — サーバー処理の request-local gate と row-ms 設定。
- `src/program/generate.cpp:18884-18891` — サーバー側で DFlash2 の後続 window に適用し、first window を別途決める分岐。
- `src/program/generate.cpp:19342-19346` — timed DFlash2 rounds の gate 観測更新。
- `src/program/generate.cpp:20904-20914` — CLI 側の window 選択。ここでは DFlash2 gate / row-ms getter を呼ばない。
