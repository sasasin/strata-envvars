# `STRATA_ADAPT_SIGNAL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリ内部の動作は対象外。

## 役割

`STRATA_ADAPT_OVERLAP` が実際に有効になる場合に、各 GPU layer の adaptive swap copy が到着したことを Verifier に知らせる方式を選びます。`STRATA_ADAPT_SIGNAL` は overlap 自体を有効化せず、コピーや expert の選択も変えません。コードコメントでは `host` を指定すると CUDA stream の host function（host callback）で通知し、既定の方式では pinned host memory への stream-ordered device-to-host copy で通知します。どちらも layer ごとの gate を進めるための信号です。

## 値と判定

値全体の比較や数値 parse はせず、overlap 初期化時の環境変数の先頭文字を大文字小文字を区別して `h` と比較します。

| 環境変数の値 | 選択される処理 |
|---|---|
| 未設定、空文字、先頭文字が `h` 以外 | pinned host memory と device 側の layer 番号配列を確保し、copy stream 上で layer 番号を D2H copy する方式を試す |
| `h` で始まる任意の値（例: `host`, `h`, `hello`） | 上記の確保を行わず、copy stream に host function を enqueue して通知する |

`host` という語との完全一致ではありません。たとえば `HOST` は `h` で始まらないので既定側です。空文字は設定されていても既定側になります。

## 有効になる条件

この選択が実際に使われるには `STRATA_ADAPT_OVERLAP=1` が必要です。同変数は `adapt_overlap()` で先頭文字が `1` のときだけ有効です。さらに adaptive tier が稼働し、layer split / 複数 GPU、`--peer-device`、`--remote-expert-opt`、`--adapt-async`、`--pipeline-windows`、page-locked swap source、`STRATA_DMA_BATCH`、既定でない `STRATA_ADAPT_LAG`、`STRATA_ADAPT_NOWAIT` などとの非対応条件を通る必要があります。resident RAM mode では別変数 `STRATA_ADAPT_OVERLAP_RESIDENT=1` も必要です。device-planned layers が有効な場合も gate の設定が拒否されます。

したがって overlap が無効、または条件を満たさない場合、`STRATA_ADAPT_SIGNAL` は信号方式を変更しません。実行時の条件と理由ログは `STRATA_ADAPT_OVERLAP` の処理です。

## 実行時の詳細

変数は overlap gate の初期化時に読み取られ、各 decode window や各 layer ごとに再読込されません。選んだ信号方式は、その gate の寿命中に使われます。コードにプロセス起動後の環境変更を再評価する処理はありません。

既定側では Strata が layer 番号 `0..n_layers` の device 配列と portable pinned host memory を確保します。成功すると `AdaptGate::hland` と `dvals` を設定し、stderr に `strata serve: adaptive overlap signal: stream-ordered copies (STRATA_ADAPT_SIGNAL=host: a host function)` と出します。この表示は D2H copy 方式を示し、`host` はその方式を切り替える指定値として表示されています。確保に失敗した場合は CUDA error を読み捨て、これらのポインターを設定しないため、`AdaptGate` の既定状態である host function 方式に fallback します。この失敗時 fallback 専用のログはありません。

`h` で始まる値を指定した場合は pinned-memory 用の確保ブロックを飛ばし、layer ごとの swap copy の後に `cudaLaunchHostFunc` を enqueue します。callback は `AdaptGate::landed` を対象 layer まで atomic に進めます。既定の D2H 方式では同じ位置で layer 番号を pinned memory に copy します。Verifier は対象 layer の GPU 計画を公開する前に到着信号を spin wait し、all-resident graph の経路では graph launch 前に全 layer の到着を待ちます。gate wait が20秒を超えると `verify: the adaptive tier's copies for layer ... never landed` のエラーになります。

この変数が選ぶ二つの方式はいずれも通知経路であり、コピー完了前に layer の GPU 計画を進めないための同期に使われます。`docs/DETAILS.md` は host-function 方式について、20-core desktop / RTX 3060 で host callback thread を早期起動しても pool worker が CPU を使う間に window あたり約7 msのコストが残ったと記載しています。これは同資料に記載された環境での観測で、他の環境の性能を示すものではありません。

## 根拠

- `src/program/generate.cpp:1368-1385` — `STRATA_ADAPT_OVERLAP` は先頭文字が `1` の場合だけ有効。
- `src/program/generate.cpp:8350-8403` — overlap gate の条件、環境変数の先頭文字 `h` 判定、既定 D2H 方式の確保とログ、条件不成立時の処理。
- `src/program/generate.cpp:8464-8472,8548-8559` — layer 順の copy と各 layer 完了信号。host function と D2H の分岐、および callback enqueue 失敗時の同期 fallback。
- `include/strata/core/verify.hpp:42-59` — `AdaptGate` の信号フィールドと reached layer の取得。
- `src/core/verify.cpp:2118-2134,2168-2172,2232-2238` — 20秒 wait、all-resident 経路の全 layer wait、通常経路の layer ごとの wait。
- `docs/DETAILS.md:1740-1742` — `host` の説明と記載された host-function cost の観測。
