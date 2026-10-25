# `STRATA_DS4_DSPARK_CUM`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

`strata-dsv41` の DSpark speculative decoding で、検証対象に含める drafts の累積信頼度の下限を指定します。draft ごとの信頼度を順に掛けた値がこの下限以上である間だけ、draft を検証対象に残します。後続 draft まで保持される確率が低い長い draft 列をまとめて検証しないための追加条件です。既定値は `0` なので、この累積条件は通常の有限・非負の信頼度積を制限しません。draft ごとの個別下限 `dspark_conf` は別の条件として適用されます。

この変数の読み取りは Strata 同梱の DS4 専用エンジン `src/dsv41/ds4_main.cpp` に1箇所あります。通常の `strata` エンジンで使われる環境変数ではありません。

## 値と判定

| 環境変数の状態 | `dspark_cum_default()` の結果 |
|---|---:|
| 未設定 | `0.0f` |
| 設定あり（空文字を含む） | `std::atof` で変換した値を `float` にした値 |

文字列全体の妥当性検査や値域チェックはありません。`std::atof` の変換規則に従い、数値として読めない先頭（空文字を含む）は `0` になり、数値の後ろにある文字は変換を妨げません。負値、1を超える値、NaN、無限大もコードでは拒否・clamp されません。

round 中、引数 `cum_min` が `< 0` の場合だけ環境変数由来の既定値に置き換えます。したがって環境変数が負値でも、その負値自体は置き換え後に使われます。要求単位の値も `< 0` ならエンジン既定値を使う sentinel です。`-0.0` は `< 0` ではないため、要求値としては明示値扱いになります。

draft を残すループ条件は `cum *= conf[i]` の後に `cum >= cum_min` を評価します。これは draft の個別信頼度 `conf[i] >= conf_min`、draft 数、残り出力枠の条件とすべて同時に満たす必要があります。通常の信頼度が `[0,1]` の場合、正の下限は後続 draft を絞り、`0` は積が0になった後の draft も許し、1を超える下限は有限の積では draft を残しません。負の下限は積が下限未満になりにくくします。NaN は比較を常に false にし、draft を1個も残さない結果になります。

## 有効になる条件

- DSpark draft の実行が有効で、decode round に draft が試行される必要があります。通常の CLI decode では `--dspark off` で draft が無効です。serve mode では要求の `spec=0`、またはエンジン起動時の DSpark 無効化によって draft 試行が止まります。
- モデルが `draft_block() > 0` を返し、round の残り出力枠 `room` が1より大きい必要があります。
- draft ごとの `dspark_conf` 条件も独立して適用されます。累積値が下限を満たさない場合、`m.verify()` は呼ばれず通常の `m.step()` と sampling に進みます。
- serve mode では各 `GEN` / `GENI` 要求に `dspark_cum=F` または別名 `spec_cum=F` を渡せます。非負の値はその要求の下限になり、負値は環境変数で決めるエンジン既定値を使います。要求値は `std::strtof` で読み、末尾文字や変換エラーの検査はありません。
- 通常のコマンドライン decode と `spec_eval` は round の既定引数 `cum_min=-1.0f` を使うため、環境変数の値が使われます。serve mode は要求の `r.cum` を渡し、値が負の場合に環境既定値へフォールバックします。

## 実行時の詳細

環境変数の値は `dspark_cum_default()` 内の関数ローカル `static const float` でキャッシュされます。最初に `cum_min < 0` の round がこの関数を呼んだ時点で読み取られ、その後プロセス内で環境を書き換えても再評価されません。非負の要求値だけで処理している間は、この関数がまだ呼ばれないことがあります。

draft を得た後、`cum` を `1.0f` で初期化し、各 draft の confidence を順に掛けながら keep 数を増やします。最初の不成立でループを止め、keep 数が正ならその範囲だけ `m.verify()` に渡します。keep 数が0なら通常の `m.step()` を実行して次 token を sampling します。環境変数自体によるログ出力はありません。

ソースコメントには、既定はオフ、H100 / owner PC のコード用途では速くならなかったこと、Project Maya の Radeon 8065S では `0.5` で同一 token のまま decode が +6.5% だったとの記載があります。これは実装コメントにある報告であり、この調査で測定条件や性能を再検証したものではありません。`docs/DETAILS.md` と `docs/DEEPSEEK41.md` にはこの変数の追加説明を確認できませんでした。

## 根拠

- `src/dsv41/ds4_main.cpp:152-162`: 変数の役割、既定値、`std::atof`、関数ローカル static cache。
- `src/dsv41/ds4_main.cpp:167-203`: round の既定 sentinel、累積 confidence の計算、verify / plain step の分岐。
- `src/dsv41/ds4_main.cpp:206-217,283-315`: 要求の `cum` 既定値と `dspark_cum` / `spec_cum` の parse。
- `src/dsv41/ds4_main.cpp:892-908,1192-1230,1296-1301,1397-1403`: serve、CLI、spec_eval から round への適用範囲と DSpark の有効化。
- `docs/DEEPSEEK41.md:4,67-68,102-103`: `strata-dsv41` が DS4 用の別エンジンとして扱われること。
