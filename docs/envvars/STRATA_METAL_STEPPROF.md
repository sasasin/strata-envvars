# `STRATA_METAL_STEPPROF`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal engine の cached decode window が指定 token 数に一致したとき、head を含む cached window の GPU dispatch を barrier group ごとの prefix として実行し、処理区分ごとの時間・weight byte 数・算出 GB/s を診断出力する計測フックです。通常の生成設定を切り替える値ではなく、条件を満たした一回の計測を起動します。実装と宣言は `metal/src/engine/window.cpp:470-475,1816-1954` にあります。

## 値と判定

| 設定値 | 判定と結果 |
|---|---|
| 未設定 | `st` は `0`。通常の decode window の token 数とは一致しないため計測を起動しません。 |
| 空文字 | `getenv` は非 null ですが `atoi("")` は `0` となり、未設定時と同様に通常は起動しません。 |
| 整数文字列 | `atoi` の結果と window の `Tn` が一致すれば候補になります。例: `4` は `Tn == 4` の cached head window を対象にします。 |
| 数字の後ろに文字がある値 | `atoi` が先頭の整数部分を変換します。例: `4x` は `4` として扱われます。先頭が整数として読めない文字列は `0` になります。 |
| `0`、負数 | `Tn` と一致した場合に限り候補になります。通常の生成 token 数は正数のため、`0` や負数で起動する通常経路はありません。 |

実装は `STRATA_METAL_STEPPROF` を `static const int` に保持し、値を文字列全体として検証しません。CLI 引数や別設定による上書きはありません。判定箇所: `metal/src/engine/window.cpp:1468-1471`。

## 有効になる条件

次の条件がそろった cached window 経路でのみ計測されます。

- Metal engine の `Window` が実行されている。
- window が既に `wcache_` にあり、cache hit の分岐に入る。
- `Tn` が `STRATA_METAL_STEPPROF` の `atoi` 結果と一致する。
- window に `head` がある。
- 同じ `Tn` の cached head window の通過回数が `STRATA_METAL_STEPPROF_AT` の値に達する。
- `stream_` が false である。

計数値 `_AT` も `static const int` として初期化され、未設定時は `20`、設定時は `atoi` の結果です。`_AT=1` なら最初の一致 window で起動します。0 以下では正の通過回数が等しくならず、通常は起動しません。`seen2` は static カウンタで、`st == Tn && head` の条件を満たすたびに増えます。streaming window でもカウンタは増えますが、`!stream_` が偽の間は計測しません。根拠: `metal/src/engine/window.cpp:1462-1475`。

このコード経路には OS/backend 切替、CLI 優先順位、別の build macro による値判定はありません。Metal window の未キャッシュ経路ではこの環境変数を評価せず、キャッシュ済みになった後も head なし、token 数不一致、または streaming なら実行しません。

## 実行時の詳細

環境変数の整数値と `_AT` は、この cache hit 分岐が初めて評価されたときに static 初期化されます。同じプロセスでは以後の環境変更は再評価されません。条件に達すると `stepprof()` を呼び、dispatch を barrier group 単位の prefix で繰り返し実行します。全 window の基準時間、空 dispatch list の時間、prefix chain の中央値を取り、dispatch の区分と weight byte 数を集計します。これは計測のため GPU graph を多数回実行する経路で、同じ cached dispatch を用います。根拠: `metal/src/engine/window.cpp:1468-1471,1816-1893`。

計測時の関連環境変数は次のとおりです。

- `STRATA_METAL_STEPPROF_REPS`: 未設定なら `5`。設定時は `max(1, atoi(value))` で反復回数を決めます。空文字や非数値は 1、0 や負数も 1 に clamp されます。文字列全体は検証しません。`metal/src/engine/window.cpp:1878-1893`。
- `STRATA_METAL_STEPPROF_OUT`: 設定されている場合、その値をパスとして `fopen(path, "w")` し、barrier group ごとの行を書きます。空文字も設定扱いとなり、空パスでの open を試みます。open 失敗は明示的なエラー出力なしでファイル出力を省略します。成功時は計測終了後に close します。`metal/src/engine/window.cpp:1915-1936`。

stderr には `strata metal stepprof:` で始まる開始行、各 pass の時間、whole-window 集計、区分ごとの時間・割合・dispatch/group 数・MiB・GB/s、distinct experts per layer が出力され、最後に stderr が flush されます。明示的な終了コード変更や失敗処理はこの関数にありません。`_OUT` のファイルには group index、dispatch 数、区分名、時間、byte 数、最初の dispatch 名をタブ区切りで書きます。根拠: `metal/src/engine/window.cpp:1879-1890,1934-1953`。

## 根拠

- 全参照と trigger: `metal/src/engine/window.cpp:470-475,1462-1475`。
- 計測処理、反復回数、出力ファイル: `metal/src/engine/window.cpp:1816-1954`。
- 候補一覧: `docs/envvars/000_envvers.md:1489-1492`。同ファイルの候補名に加えて Strata checkout 全体を `rg` で検索し、実際の主変数読み取りは上記 cache hit 分岐の一箇所と確認しました。`docs/DETAILS.md` にはこの計測フックの追加説明を確認できませんでした。
