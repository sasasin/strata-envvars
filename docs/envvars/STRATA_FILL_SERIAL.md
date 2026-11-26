# `STRATA_FILL_SERIAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

SYCL エンジンが expert-cache をプロファイルから事前充填するとき、GGUF からの pipelined fill を選ばず逐次 fill にするための設定です。通常は `--stream-experts` の GGUF 読み込み、かつ共有（per-layer でない）cache の場合に pipelined fill になります。この変数が設定されていると、各 expert を `srcp->blob(...)` で読み、`fill_slot_blocking(...)` で slot へ順に充填します。cache に入る profile の組と順序は同じで、変わるのは充填の読み込み・コピー経路です。実装は SYCL の `generate.cpp` にあります（`engine/sycl/src/program/generate.cpp:5251-5270,5384-5409`）。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_FILL_SERIAL") == nullptr` かどうかだけを判定します。対象経路で未設定なら pipelined、値が存在すれば逐次です。空文字、`0`、`1`、`true`、`false`、大小文字や前後空白を含む文字列もすべて「設定あり」として逐次を選びます。数値変換、文字列比較、境界値や無効値の fallback はありません（`engine/sycl/src/program/generate.cpp:5265-5271`）。

| 条件 | unset | 有効になる値（逐次を選択） | 無効になる値（pipelined を選択） |
|---|---|---|---|
| `srcp == &gguf_src` かつ per-layer cache でない | pipelined | 空文字、`0`、`1`、`true`、任意の設定値 | なし。環境変数が未設定のときだけ pipelined |
| それ以外の fill 経路 | この変数による差はない。fill は逐次側 | 該当なし | 該当なし |

`docs/INTEL.md:458` は `STRATA_FILL_SERIAL=1` と記載しますが、実装は値が `1` かを検査せず、設定の有無だけで逐次を選びます。

## 有効になる条件

- profile が読み込まれて空でなく、expert source が利用可能であることが必要です。`--expert-profile` の読み込みに失敗した場合は先にエラー終了します（`engine/sycl/src/program/generate.cpp:3780-3785,5251-5257`）。
- pipelined fill を切り替えるのは `--stream-experts` により `srcp` が `gguf_src` を指し、`--mmap-experts` が選ばれておらず、per-layer admission が無効の場合だけです。`--stream-experts` は native pack と `--native SHARD1` も要求します（`engine/sycl/src/program/generate.cpp:2175-2183,4711-4725,5260-5271`）。
- `--expert-cache-per-layer` が有効な場合、または mmap / host arena など `gguf_src` 以外の source の場合は、変数が未設定でも `piped` は false で、逐次経路です（`engine/sycl/src/program/generate.cpp:4711-4758,5260-5271`）。
- この読み取りは SYCL 実装にあります。CUDA/HIP や他のバックエンドでこの名前を読む Strata 所有ソースは、現行 checkout の全参照検索では見つかりません。

## 実行時の詳細

profile の読み込みと cache の準備後、充填処理の開始時に `piped` を一度計算します。関数内 static cache ではありません。逐次経路は profile 順に slot を確保し、expert blob を取得して slot への blocking fill を行い、profile の必要件数まで繰り返します。pipelined 経路は先に slot を確保し、最大 64 件ずつファイル順に複数 worker で GGUF を pinned host buffer へ読み、次 batch の読み込み中に device copy を行います（`engine/sycl/src/program/generate.cpp:5260-5271,5272-5325,5384-5405`）。

profile fill はこの初期化時に一度だけ実行されます。環境変数を後から変更しても進行中の fill の判定は変わりません。CLI 引数が環境変数の値を上書きする処理はありませんが、`--stream-experts`、`--mmap-experts`、`--expert-cache-per-layer` は上記のように切り替え対象経路を決めます（`engine/sycl/src/program/generate.cpp:5251-5271`）。

## ログと測定値

この変数の設定値を示す専用ログはありません。profile fill が終わると両経路とも `strata generate: profile fill: %.2f GiB in %.1f s (%.2f GB/s, %s)` を stderr に出し、最後の `%s` は `pipelined` または `serial` になります。続けて pre-filled slot 数と所要時間を出力します（`engine/sycl/src/program/generate.cpp:5406-5424`）。pipelined 経路では pinned buffer の確保失敗時に `strata generate: the profile fill could not pin %zu MiB`、GGUF 読み込み失敗時に `strata generate: the profile fill could not read an expert from the GGUF` を出して `1` を返します（`engine/sycl/src/program/generate.cpp:5287-5292,5321-5324`）。逐次経路の slot fill 失敗は `strata generate: the profile fill failed at pair %lld: %s` を出して `1` を返します（`engine/sycl/src/program/generate.cpp:5396-5402`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:2175-2183` — profile、source 選択用 CLI 引数。
- `engine/sycl/src/program/generate.cpp:3780-3785` — profile 読み込み。
- `engine/sycl/src/program/generate.cpp:4711-4758` — GGUF streaming、mmap、arena の source 選択。
- `engine/sycl/src/program/generate.cpp:5251-5271,5272-5325,5384-5424` — fill 条件、変数判定、逐次/pipelined 実装、ログと失敗経路。
- `docs/INTEL.md:458` — 概要表記（コードの設定有無判定とは値表記に差がある）。
