# `STRATA_PIN_RESERVE_MIB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena が page-locked host memory を登録する前に、engine が後から必要とする pinned buffer 用の余地を確保します。指定値は soft reserve の MiB 数です。soft reserve は arena の配置後に解放されます。hard reserve は必須 buffer の allocation が拒否されたとき、または engine が `READY` になるまで保持し、拒否時には保持分を解放して allocation を一度だけ再試行します。

## 値と判定

値は `std::strtoull(e, nullptr, 10)` で符号なし整数に変換されます。文字列全体の検証はなく、10 進数として読める先頭部分の後ろは無視されます（例: `32MiB` は 32）。先頭の空白や符号も `strtoull` の規則で処理され、`-1` は符号なし整数の最大値になります。数値に変換できない文字列は 0 となり、reserve を無効にします。範囲外の値に対する errno 確認や、後続計算・allocation size の上限 clamp はありません。

| 環境変数の状態 | soft reserve |
|---|---:|
| 未設定または空文字 | Windows CUDA は 640 MiB。その他は通常 0 MiB。ただし `STRATA_TEST_PIN_BUDGET_MIB` が非 0 ならその他でも 640 MiB |
| 非空で変換結果が 0 | 0 MiB（無効） |
| 非空で変換結果が N | N MiB |

hard reserve は `max(floor(N / 4), 64)` MiB です。soft reserve が 0 のときは処理がそこで終了するため、hard reserve も取りません。N が 0 でない場合は hard reserve を先に、soft reserve を後に確保します。それぞれ確保に失敗するとサイズを半分にし、16 MiB 以上の間だけ再試行します。指定値そのものをログに出すのではなく、実際に確保できた量をログに出します。

## 有効になる条件

この実装は CUDA runtime を使う pinned-memory 管理に組み込まれています。既定値は Windows CUDA で有効、Linux では無効です。HIP build は Windows CUDA の既定値分岐から除かれます。コード上は環境変数を明示設定した場合の OS 制限を設けていないため、非 Windows CUDA build でも N を指定すれば reserve を試みます。

無効値または未設定で既定値 0 になる場合、`pin_reserve_take()` は reserve allocation なしで戻ります。確保できない場合も start を失敗させず、縮小を試した後、取得量が要求量より少なければ警告を出します。`STRATA_TEST_PIN_BUDGET_MIB` はテスト用の simulated ceiling で、未設定時の非 Windows 既定値を 640 MiB にする相互作用があります。

## 実行時の詳細

環境変数は `src/program/generate.cpp` が expert arena を開く直前に呼ぶ `pin_reserve_take()` で読みます。状態は `pin_detail::State` の function-local static に保持され、`taken` も最初の呼び出し後に true になります。そのため、この処理での値の読み取りは実質的にプロセス内の初回 reserve 呼び出しに適用され、後から環境を書き換えても再評価されません。

reserve allocation は `cudaHostAlloc` を使います。arena 配置後、成功・失敗にかかわらず soft reserve を解放します。hard reserve は `host_alloc_guarded()` 経由の必須 pinned allocation が最初に拒否された際、soft reserve と合わせて解放して allocation を再試行します。拒否が起きなければ engine の `READY` 出力直前に解放されます。hard reserve が allocation されなかった場合、または既に解放済みの場合は再試行動作は起きません。

観測可能な stderr 出力には、確保済み合計量を示す `strata: pinned-memory headroom: holding ...`、要求量に届かなかった場合の `strata: WARNING: pinned-memory budget is already nearly spent ...`、soft reserve 解放時の `... handed back after the expert arena`、および allocation 拒否時の `... the held headroom is handed back and the allocation retried` があります。後続 allocation も失敗したときのエラー末尾には `[pinned-memory-exhausted]` の案内が使われます。

## 文書との照合

`docs/DETAILS.md` の pinned-memory headroom 説明（同ファイル 217-222 行付近）は、Windows CUDA の既定値 640 MiB、arena 後に soft reserve を返すこと、hard reserve を保持して失敗時に返却・再試行すること、Linux の既定 OFF と整合します。実装では `STRATA_TEST_PIN_BUDGET_MIB` が有効な非 Windows build も既定 640 MiB になるため、その場合は説明上の「Linux は reserve off」の例外です。文書にある測定・特定 PC での失敗例はこの調査で再測定していません。

## 根拠

- 値変換、OS 別既定値、test budget との相互作用: `include/strata/core/pin_budget.hpp:89-97`
- state の初期化と test budget の読み取り: `include/strata/core/pin_budget.hpp:38-58`
- reserve 量、確保縮小ループ、ログ、warning: `include/strata/core/pin_budget.hpp:119-149`
- soft/hard reserve 解放と失敗時再試行: `include/strata/core/pin_budget.hpp:151-170,191-209`
- arena 前の取得、arena 後の soft 解放: `src/program/generate.cpp:5800-5811`
- `READY` 直前の hard 解放: `src/program/generate.cpp:11021-11023`
- guarded allocation の使用例（session staging）: `src/core/session.cpp:545`; （verify staging）: `src/core/verify.cpp:424`
- 既存資料: `docs/DETAILS.md:217-224`
