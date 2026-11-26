# `STRATA_TEST_CACHE_FAIL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

expert cache の初期化ループで、指定回数だけキャッシュの open が失敗した状態を擬似的に作ります。コメントには out-of-commit の `cudaMalloc` 失敗時の retry を試す用途とあります。該当コードは CUDA/HIP 側の `engine/src/program/generate.cpp` と SYCL 側の `engine/sycl/src/program/generate.cpp` にあります。値が正なら、指定回数の試行では実際の `xcache.open` / `xcache.open_sized` を呼ばず、失敗文字列をセットします（`engine/src/program/generate.cpp:9640-9657`、`engine/sycl/src/program/generate.cpp:5117-5135`）。

この名前はテスト用コメントを伴いますが、読み取りと分岐は通常の `generate.cpp` にあり、テスト用 build macro の条件で囲まれていません。従ってビルドされた該当経路で実行時に有効です。リポジトリ内の全参照検索では Metal 側の読み取りは見つからず、Metal での効果は確認できません。

## 値と判定

両実装とも `getenv` で設定有無を確認し、設定されていれば値を `std::atoi` に渡します。変換後の `fake_fails` が正の場合にだけ擬似失敗します。文字列全体の検証、範囲制限、clamp はありません（`engine/src/program/generate.cpp:9645-9652`、`engine/sycl/src/program/generate.cpp:5122-5129`）。

| 条件 | unset | 擬似失敗を起こす値 | 擬似失敗にならない値 |
|---|---|---|---|
| CUDA/HIP・SYCL の expert cache 初期化 | `0` | `atoi` の結果が正の整数。例: `1`, `3`, `+2`, ` 2`, `2tail` | 結果が 0 以下。例: 空文字, `0`, `0tail`, `true`, `-1` |

`atoi` は先頭の空白と符号を許し、先頭から読める十進数部分を変換します。したがって `2tail` は 2 回、`0tail` は 0 回として扱われ、`true` や空文字は 0 になります。正の値に上限は設けられていません。`int` で表せない数値の扱いをこのコードは検査しません。`getenv` が未設定の場合も 0 です（上記同じ行）。

## 有効になる条件

- `generate.cpp` の該当 backend 実装がビルドされていること。読み取り箇所は CUDA/HIP 側と SYCL 側にあります。Metal 側にはこの名前の参照がありません（全参照検索結果。該当実装は `engine/src/program/generate.cpp:9645-9657`、`engine/sycl/src/program/generate.cpp:5122-5135`）。
- expert cache 初期化時点で `o.expert_cache > 0` であること。この条件の内側でのみ読み取ります。cache が 0 以下なら環境変数は読み取られず、このフックは動きません（`engine/src/program/generate.cpp:9602-9603`、`engine/sycl/src/program/generate.cpp:5068`）。
- `--expert-cache` が cache のサイズと自動縮小の可否に関係します。CUDA/HIP 側では `--expert-cache auto` を内部値 `-1` にし、自動 cache の初期化後に正の slot 数になった場合にこの処理へ進みます。自動 cache なら失敗後に小さくして再試行します。明示サイズでは自動縮小しません（`engine/src/program/generate.cpp:3984-3987, 9050`、`engine/sycl/src/program/generate.cpp:2002-2005`、`engine/src/program/generate.cpp:9671-9683`）。
- OS、サーバーモード、モデル状態、別の環境変数による値の上書きは、この読み取りと擬似失敗分岐にはありません。Windows では最終的な失敗時に追加案内を出す条件分岐がありますが、擬似失敗の発生条件は変わりません（`engine/src/program/generate.cpp:9677-9683`、`engine/sycl/src/program/generate.cpp:5159-5165`）。

## 実行時の詳細

cache 初期化ループに入ると、環境値をローカル変数 `fake_fails` に一度読み込みます。ループの各回で `fake_fails > 0` ならカウンターを 1 減らし、`ok` を false のままにしてエラー文字列 `ExpertCache: cudaMalloc failed: out of memory (STRATA_TEST_CACHE_FAIL)` を設定します。この回は実際の cache open 関数を呼びません。カウンターが 0 になった回から `xcache.open` または `xcache.open_sized` を呼びます（`engine/src/program/generate.cpp:9645-9659`、`engine/sycl/src/program/generate.cpp:5122-5136`）。

読み取りは cache 初期化時の一度だけで、static cache やリクエストごとの再読込ではありません。実行中に環境値を変えても `fake_fails` の残数には反映されません。

擬似失敗後、`--expert-cache auto` の場合は縮小でき、かつ失敗 retry が 8 回未満なら cache サイズを縮めて再試行します。縮小は現在のサイズのおよそ 3/4 です。縮小できない場合、または 8 回の縮小 retry 後も失敗した場合はエラーを stderr に出して `1` を返します。明示 cache サイズでは最初の失敗で同じく `1` を返します。カウンターが尽きて実際の open が成功すれば初期化は続行します（`engine/src/program/generate.cpp:9671-9685`、`engine/sycl/src/program/generate.cpp:5153-5167`）。

## ログと測定値

自動 cache で縮小 retry を行う場合、stderr に `strata generate: ExpertCache: cudaMalloc failed: out of memory (STRATA_TEST_CACHE_FAIL); trying a smaller expert cache: %d slots`（Windows では commit 情報が間に入る場合あり）を出します。retry できない場合は `strata generate: ExpertCache: cudaMalloc failed: out of memory (STRATA_TEST_CACHE_FAIL)` を出し、Windows では続けて page file と `--expert-cache` に関する案内を出して `1` を返します（`engine/src/program/generate.cpp:9671-9683`、`engine/sycl/src/program/generate.cpp:5153-5165`）。

この環境変数に関する測定値は、参照した `docs/DETAILS.md` にありません。

## 根拠

- `engine/src/program/generate.cpp:9044-9051` — CUDA/HIP 側 cache 初期化と auto 判定。
- `engine/src/program/generate.cpp:9640-9685` — 値の読み取り、擬似失敗、縮小 retry、失敗時のログと戻り値。
- `engine/sycl/src/program/generate.cpp:4823-4830` — SYCL 側 cache 初期化と auto 判定。
- `engine/sycl/src/program/generate.cpp:5117-5167` — SYCL 側の読み取り、擬似失敗、縮小 retry、失敗時のログと戻り値。
- `engine/src/program/generate.cpp:3984-3987`、`engine/sycl/src/program/generate.cpp:2002-2005` — `--expert-cache auto` の内部値。
