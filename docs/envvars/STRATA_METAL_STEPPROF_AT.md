# `STRATA_METAL_STEPPROF_AT`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal engine の step profiler `stepprof()` を、対象 token 数の head 付き cached window の何回目に実行するか指定します。この変数単独では profiler を有効にしません。別変数 `STRATA_METAL_STEPPROF` が window の token 数 `Tn` と一致し、対象回数に達したときに限り実行されます。参照は `metal/src/engine/window.cpp:1468-1471` です。

## 値と判定

値は `std::atoi()` で整数に変換されます。環境変数が未設定なら既定値は `20`、設定されていれば空文字を含め変換結果が使われます。`atoi` は整数として読める先頭部分を変換するため、空文字や数字で始まらない値は `0`、`20tail` は `20`、前後の空白や符号は整数変換規則に従います。全体の形式検証、範囲確認、clamp、無効値の警告や fallback はありません。

判定は `++seen2 == st_at` です。`seen2` は `Window::run()` 内の関数 static カウンターで、同じプロセス内で共有されます。従って正の整数 `N` は、`STRATA_METAL_STEPPROF` が指定する `Tn` と一致し、`head` が真である cache hit の N 回目を数えます。`stream_` の確認はカウンターを増やした後なので、その N 回目が streaming window なら profiler は実行されず、後の呼び出しで再試行もしません。`0` や負数は通常増加するカウンターと一致せず、実行を発火しません。

## 有効になる条件

profiler が実際に実行される条件は次のとおりです。

- Metal engine の `Window::run()` を通ること。
- window dispatch が既に cache されており、cache hit の経路に入ること。
- `STRATA_METAL_STEPPROF` を `atoi` した値が今回の `Tn` と一致すること。
- 呼び出しの `head` が真であること。
- `stream_` が無効であること。
- `STRATA_METAL_STEPPROF_AT` が数える N 回目であること（カウンターは `stream_` 判定より先に増加します）。

したがって、この機能は streaming window では実行されませんが、対象 token 数かつ head 付きの streaming cache hit も回数には含まれます。初回の cache miss では発火判定に到達せず、後続の cache hit で判定されます。CLI やサーバーモード自体による別の優先順位はこの読み取り箇所にはありません。実際に Metal `Window::run()` を使わない実行経路には作用しません。Metal engine は macOS の setup 経路で選ばれます（`setup.py:9941-9948`）。

## 実行時の詳細

`STRATA_METAL_STEPPROF_AT` は `Window::run()` の cache-hit ブロック内で初めて参照され、その値は関数 static `st_at` に保存されます。同じく `STRATA_METAL_STEPPROF` の `st` も static に保存されます。環境をプロセス実行中に変更しても、初回評価後の値は更新されません。読み取り箇所は `metal/src/engine/window.cpp:1447-1472` です。

発火すると `stepprof()` は cached dispatch 群を繰り返し実行します。40 回の warm-up、全 window の GPU 時間測定、barrier group ごとの prefix 実行、route dispatch による expert 数の取得などを行い、計測結果を stderr に出します（`metal/src/engine/window.cpp:1816-1893,1894-1953`）。この追加 GPU 作業により、その呼び出しでは通常の処理に計測時間が加わります。stderr には `strata metal stepprof: T...`、pass 時間、window 集計、part ごとの時間・MiB・GB/s、layer ごとの distinct expert 数が出ます。`STRATA_METAL_STEPPROF_OUT` が設定されている場合のファイル出力は別変数による処理です（同 `window.cpp:1915-1936`）。

この変数自体について、Strata の資料に記載された測定結果や失敗時の専用エラー経路は確認できませんでした。 profiler 内の GPU 実行が失敗した場合の挙動は、調査した呼び出し箇所からは確定できません。

## 根拠

- 値の読み取り、既定値 20、static cache、発火条件: `metal/src/engine/window.cpp:1463-1475`
- cached dispatch の有無と初回 cache miss の分岐: `metal/src/engine/window.cpp:1447-1472`
- profiler の GPU prefix 計測と stderr / optional file 出力: `metal/src/engine/window.cpp:1816-1953`
- Metal engine setup の platform 分岐: `setup.py:9941-9948`
