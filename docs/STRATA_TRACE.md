# `STRATA_TRACE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の engine が起動時の GPU 空きメモリと serve リクエストの進行状況を stderr に記録する診断用スイッチです。CUDA/HIP 系の `src` 実装と SYCL 実装の両方に読み取り箇所があります。値は計算設定として使われず、ログ出力と GPU メモリ情報の取得を有効にします。

## 値と判定

すべての読み取り箇所で、環境変数が未設定かどうかだけを判定します。設定値の数値変換、文字列比較、先頭文字比較はありません。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |
| `0`、`false` などの文字列 | 有効 |

ただし読み取り時期は箇所ごとに異なります。起動時メモリ記録の判定は `mem_mark()` 内の `static const bool` に保存され、最初の呼び出し後はプロセス中に環境を変えても変わりません。serve の詳細トレースは serve ループの初期化時に一度読み、その engine の全リクエストで同じ値を使います。batched prompt の chunk ログは chunk ごとに `getenv()` を呼ぶため、そのループ中も判定し直します。

## 有効になる条件

各出力がある処理経路に到達する必要があります。起動時の VRAM 記録は `mem_mark()` の呼び出し地点で、モデルや cache などの初期化段階を記録します。詳細なリクエストログは serve 経路で、prompt chunk のログは batched prefill の chunk ループで出ます。これらの条件に当たらない実行経路では、設定しても対応ログは出ません。

`STRATA_TRACE_ADAPT` は adaptive 層の別診断スイッチであり、`STRATA_TRACE` の値では制御されません。文書と設計資料を検索した範囲では、`docs/` に `STRATA_TRACE` の説明は見つかりませんでした。性能向上や出力の正確性を変えるという根拠はありません。

## 実行時の詳細

`mem_mark(where)` は有効時に GPU の空きメモリを取得し、`strata trace: <MiB> MiB free after <where>` の形式で stderr に記録します。CUDA/HIP 系では `cudaMemGetInfo()`、SYCL 系では SYCL device の memory info API を呼びます。ソース中の呼び出し地点は、重み arena・重み・session・expert cache・profile fill・head/prompt path・verifier などの初期化後です。これは状態を記録するもので、空きメモリの量を変更しません。

serve のトレースは各リクエストの開始時に `strata trace: <event> <a> <b>` を記録し、prompt 開始・完了、位置情報の構築と device idle、window の開始などを追います。値を渡さない event では引数の既定値 `-1 -1` が表示されます。追加で lent/refilled slot 数、prompt chunk と decode の所要時間、読んだ token 数などを記録し、条件が合えば message boundary checkpoint の token 数と tail 数も記録します。CUDA/HIP 系と SYCL 系のこの helper は stderr を flush します。

batched prefill は各 prompt chunk の先頭で `strata trace: prompt chunk <c0> of <n>` を stderr に出して flush します。これらの診断ログは結果の生成・request 処理分岐を切り替えません。

## 根拠

- `src/program/generate.cpp:1305-1312` — `mem_mark()` の設定有無判定、CUDA memory info、出力形式。起動中の呼び出し箇所は同ファイルの `3010-3026`, `4271`, `4502`, `4776`, `5118`, `5198`, `5573`, `5695`, `7318`, `7601`, `12792`, `12810`。
- `sycl/src/program/generate.cpp:1251-1263` — SYCL `mem_mark()` の判定、memory info、出力。
- `src/program/generate.cpp:8911-8916` — serve リクエスト用の判定と trace helper。
- `src/program/generate.cpp:10496`, `10715`, `10763-10764`, `10815-10819`, `10971`, `10917-10919`, `11055-11056`, `11089-11090`, `11097`, `11897` — request/prompt/window、slot、chunk、checkpoint のログ呼び出し。
- `sycl/src/program/generate.cpp:8359-8365`, `9812`, `10023-10024`, `10126`, `10220-10222`, `10260`, `10314-10316`, `10348-10350`, `10356`, `11179` — SYCL 側の対応箇所。
- `src/prefill/prefill.cpp:2133-2136` および `sycl/src/prefill/prefill.cpp:2219-2223` — batched prompt の chunk ごとの読み取り、出力、flush。
