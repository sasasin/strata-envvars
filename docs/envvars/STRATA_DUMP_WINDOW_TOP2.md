# `STRATA_DUMP_WINDOW_TOP2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 版 `strata generate` の speculative decoding で、検証した window の各 row について、logits の上位 2 ID と値を指定先のテキストファイルへ出力する診断用変数です。変数値はフラグではなく、そのまま出力ファイルのパスになります。出力は検証後の観測用で、後続の token 採用・commit の判定には使われません（`engine/sycl/src/program/generate.cpp:14125-14138`, `14160-14165`, `14190-14205`）。

## 値と判定

`std::getenv` の返り値が null かどうかだけを見ており、値の変換や内容検証はありません。unset なら出力処理を行いません。設定されていれば空文字を含む任意の文字列を `fopen(path, "w")` に渡します。したがって `1`、`true`、`0` も特別なフラグ値ではなく、ファイル名として扱われます。空文字は設定済みとして分岐に入りますが、通常 `fopen` に失敗する空パスになり、警告なしで出力されません（`engine/sycl/src/program/generate.cpp:14125-14128`）。

| 条件 | unset | 設定時の値 | 無効・失敗例 |
| --- | --- | --- | --- |
| SYCL の speculative decode loop | 出力処理なし | `"/tmp/window-top2.txt"` など、書き込み可能な出力パス | `""`、存在しない親ディレクトリ、権限不足などは `fopen` が null になり書き込みなし。コードから値の形式や範囲による拒否は確認できない |

## 有効になる条件

- SYCL 実装の `strata generate` であること。この参照は `engine/sycl/src/program/generate.cpp` にあり、対象名の他のソース参照は見つかりませんでした（完全一致検索では設定登録 JSON の記載もありますが、読み取り箇所ではありません）。
- `o.spec > 0` から始まる speculative decoding の経路に入り、prompt 処理後に生成上限未満かつ EOS 終了でない場合に loop が実行されること（`engine/sycl/src/program/generate.cpp:13712-13719`）。
- 各 window の `ver.run(...)` と expert pool のエラー確認を通過すること。失敗時は先にエラーを stderr に出して終了するため、この dump 箇所には到達しません（`engine/sycl/src/program/generate.cpp:14114-14123`）。
- CLI 引数や別の環境変数による値の上書きは、この名前の読み取り経路にはありません。変数が unset でも通常の speculative decode 自体はこの dump 分岐なしで続きます。

## 実行時の詳細

環境値は各 verify window の実行後に `getenv` で再確認されます。分岐に初めて入ったときだけ、関数内 `static` の `FILE*` 初期化として `fopen(wl, "w")` を行います。そのため最初に分岐へ入った時点のパスでファイルを作成・切り詰め、その後に環境値が変わっても同じ stream を使います。分岐に入る前の環境変更は反映されますが、open 後に unset するとその間は書き込み分岐自体が止まり、再設定時には既存 stream が再利用されます（`engine/sycl/src/program/generate.cpp:14125-14128`）。

各 window で `t = 0..T-1` の logits を `ver.copy_logits` で読み、語彙 ID を走査して最大値の ID と 2 番目の ID を選びます。各行の形式は `pos T row id1 l1 id2 l2`、値は `p+t`, window 幅 `T`, row 番号 `t`, 2 ID, それぞれ小数点以下 5 桁の logits です。行ごとに改行し、window ごとに `fflush` します。ファイルを閉じる処理はこの局所コードにありません（`engine/sycl/src/program/generate.cpp:14127-14138`）。

`fopen` に失敗した場合は `wlf == nullptr` により row loop が実行されず、ログも出ません。`copy_logits` が false を返した場合はその window の残りの row を出さず、こちらも専用エラー表示はありません。`fprintf` / `fflush` の戻り値も確認しません（`engine/sycl/src/program/generate.cpp:14128-14138`）。

## ログと測定値

この変数に関する専用の stdout / stderr ログや測定値はありません。観測結果は指定パスへのテキスト出力です。出力開始・open 失敗・途中失敗を知らせるメッセージは実装されていません（`engine/sycl/src/program/generate.cpp:14125-14138`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:13712-13719` — speculative decoding 経路の開始条件。
- `engine/sycl/src/program/generate.cpp:14114-14138` — verify 後の環境変数読み取り、ファイル open、logits row の選択・出力。
- `engine/sycl/src/program/generate.cpp:14160-14165`, `14190-14205` — dump 処理と token 判定・commit の順序。
- `docs/envvars/000_envvers.md:985` — 候補一覧の記載（候補を裏付ける実装根拠ではない）。
