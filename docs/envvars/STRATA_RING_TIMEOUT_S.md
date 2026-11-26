# `STRATA_RING_TIMEOUT_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンが GPU の layer doorbell（ring）を待つ時間を秒単位で変える。既定は 20 秒で、正の値を指定するとその秒数を超えるまで待つ。CUDA/HIP 側ではこの名前を読む実装は見つからず、対象は SYCL の `Verifier` である。設定値はモデル計算や token の選択を直接変えるものではなく、doorbell が遅れて届く場合の待ち時間と、届かない場合に timeout として失敗にする時点を変える。`engine/sycl/src/core/verify.cpp:297-307,2673-2684,3756-3759,4028-4031`。

## 値と判定

`strata_ring_timeout()` は `std::getenv` で値を取得し、設定されていれば `std::atol`、未設定なら `20` を使う。変換結果が 1 未満なら 20 に戻し、1 以上なら上限なしで秒数として使う。`atol` は数値全体の厳密な検証ではないため、先頭の空白や符号を含む数値部分を変換し、変換後の文字列は検査しない。数値として読めない先頭なら 0 となり既定値に戻る。正の範囲外で `atol` が扱えない値の結果は、このコードでは別途検証されない。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `Verifier` | 20 秒 | 1 以上に変換される値（例: `1`, `+3`, ` 4`, `3seconds` → 1, 3, 4, 3 秒） | 空文字、`0`, `0anything`, 負数、数値に変換できない文字列は 20 秒に戻る |

変換後の値で比較するため、`1.5` は 1 秒として扱われ、`1abc` は 1 秒として扱われる。`+0` と `-1` は 20 秒に戻る。`atol` の整数オーバーフロー時の挙動は規格上保証されないため、その場合の値は定められない。`engine/sycl/src/core/verify.cpp:300-307`。

## 有効になる条件

- SYCL エンジンの `Verifier` の doorbell wait 経路で使われる。SYCL の engine source list に `src/core/verify.cpp` が含まれる（`engine/sycl/CMakeLists.txt:290-293`）。
- 通常の layer-by-layer wait、同期 batch wait、batch polling で GPU の sequence counter が期待値に届かない場合に timeout 判定を行う（`engine/sycl/src/core/verify.cpp:2637-2684,3726-3759,4006-4034`）。
- ホストが layer ごとの doorbell を待たない経路ではこの変数はその待ちに作用しない。たとえば `STRATA_VERIFY_NO_HOST` が有効な通常 window は `!no_host` の待ちループを通らず、all-resident 経路にも個別のホスト待ちはない（`engine/sycl/src/core/verify.cpp:2615-2620,2623-2637,3998-4005`）。
- 別の環境変数や CLI 引数による timeout の上書きは見つからなかった。SYCL spin kernel 側の読み取り上限は別設定 `STRATA_SPIN_MAX` / `STRATA_SYCL_SPIN_MAX` に関する別機構であり、この変数の秒数とは別である（`engine/sycl/CMakeLists.txt:59-70`）。

## 実行時の詳細

秒数は `strata_ring_timeout()` 内の関数ローカル `static const long` に初回評価時だけ保存される。したがって最初の呼び出し後にプロセス環境を変えても反映されず、そのプロセス内の後続 wait でも同じ秒数を使う（`engine/sycl/src/core/verify.cpp:300-307`）。

通常の window と同期 batch は、GPU の sequence counter が期待値未満の間 spin し、待ち始めから設定秒数より長く経過すると timeout にする。batch polling は前回の doorbell 時刻 `b_last_` から計り、未到着時に 2 ms を超えた polling で timeout を確認する。比較は `>` なので、指定秒数ちょうどではなくそれを超えた後に判定される（`engine/sycl/src/core/verify.cpp:2641-2645,2673-2684,3728-3734,3756-3759,4006-4034`）。

timeout 時は `verify: timed out at layer <番号>` または `verify batch: timed out at layer <番号>` を error 文字列に設定し、GPU wait の解放を最大 5 秒試みる。通常 window では `STRATA_VERIFY_TRACE` 有効時に診断と trace dump を行い、無効時はそれらを行わず解放を試みる（`engine/sycl/src/core/verify.cpp:2673-2684,3756-3759,4028-4031`）。

## ログと測定値

timeout 自体は `stderr` に直接出力せず、`err` に上記の文字列を設定して呼び出し元へ失敗を返す。SYCL generation 呼び出し元は失敗時に `ERR <error>` を stdout に出す（`engine/sycl/src/core/verify.cpp:2673-2684,3756-3759`; `engine/sycl/src/program/generate.cpp:10028-10030`）。`STRATA_VERIFY_TRACE` が有効な通常 window の timeout では診断・trace が stderr に出る。設定値ごとの測定値はソースに示されていない。

## 根拠

- 値の取得・変換・static cache: `engine/sycl/src/core/verify.cpp:297-307`
- 通常 window の待ちと timeout 経路: `engine/sycl/src/core/verify.cpp:2615-2620,2637-2684`
- 同期 batch と batch polling の timeout: `engine/sycl/src/core/verify.cpp:3726-3759,3993-4034`
- SYCL engine への組み込みと別の device spin limit: `engine/sycl/CMakeLists.txt:59-70,290-293`
- generation 呼び出し元での失敗表示: `engine/sycl/src/program/generate.cpp:10028-10030`
