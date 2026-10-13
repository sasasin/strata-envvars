# `STRATA_VERIFY_PIPE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数の動作は含めない。

## 役割

SYCL verifier の stepped 実行で、CPU expert pool の処理と次の split graph segment の投入を重ねるかを切り替える A/B 用スイッチです。既定では重ねる分岐を許可します。`=0` を指定すると helper thread を使わず、CPU pool の処理を完了してから次 segment を投入します。

この変数だけでは stepped 実行になりません。ソースコメントは `STRATA_VERIFY_STEPPED` を Arc A-series 向け opt-in と説明しています。実装に明示的な GPU 世代判定はなく、実際にこの分岐へ入る条件は以下の「有効になる条件」のとおりです。通常の CUDA/HIP verifier にはこの読み取り箇所はありません。

## 値と判定

文字列全体や数値としての妥当性は検査せず、`getenv()` が返す値の先頭文字だけを調べます。

| `STRATA_VERIFY_PIPE` | `pipe` の値 |
|---|---|
| 未設定 | `true` |
| 空文字 | `true`（値は設定済みだが先頭文字は `\0`） |
| 先頭文字が `0` | `false`（例: `0`, `0abc`） |
| それ以外 | `true`（例: `1`, `true`, `false`, 空白で始まる文字列） |

大文字小文字、後続文字、空白、負号、数値の範囲は判定されません。したがって `false` という値も先頭が `f` のため有効扱いです。

## 有効になる条件

次の条件が揃う経路でだけ効果があります。

- SYCL verifier が使われるビルド。`sycl/CMakeLists.txt` は `src/core/verify.cpp` を SYCL エンジンのソースに含めます。
- `STRATA_VERIFY_STEPPED` が `env_on()` 判定で有効。これは unset、空文字、先頭が `0` の値では無効で、先頭がそれ以外の非 NUL 文字なら有効です。
- all-resident 経路ではなく、`ar_on()` が false。
- `STRATA_VERIFY_EAGER` が未設定。値が空文字でも「設定あり」として stepped graph capture を止めます。
- window 用の segment が作られていて、stepped serve が実行される。
- 次に投入する segment の `seg_kind_` が `0`（split segment）。`STRATA_VERIFY_SPLIT=0` により kind `0` の境界が作られない場合、この変数による並行投入は起きません。`STRATA_VERIFY_SPLIT` も未設定時は split を有効にします。

## 実行時の詳細

`pipe` は stepped serve の中にある関数ローカル `static const bool` です。最初に stepped serve が呼ばれたとき（次 segment の split 判定を行う位置）に環境を読み、そのプロセス内では以後同じ値を使います。その評価後にプロセス環境を書き換えても再評価されません。

`pipe` が true で次 segment が split のとき、実装は helper `std::thread` で `pool(...)` を実行します。ホスト側は `flag A` が pool から公開されるか pool が終わるまで待ち、公開後に次の graph segment を先に投入してから helper thread の終了を join します。その後 `copy_->wait()` を行い、flag B と M を上げて次の segment に進みます。Linux では別設定 `STRATA_PIPE_HELPER_SIBLING` が有効で CPU sibling の取得にも成功した場合に限り、helper thread の affinity をその CPU に設定します。

`pipe` が false、または次 segment が split でない場合は `run_pool()` をその場で同期実行してから続きます。`STRATA_VERIFY_PIPE` 自体の通常ログはありません。helper thread の生成・実行で例外が起きた場合は verifier に `verify: pipelined serve: ...` または `verify: pool: ...` のエラー文字列が設定されます。

`STRATA_VERIFY_STEPPED` が有効でも all-resident 経路では serve を使わず、window 前に flag を上げるため、この変数は関与しません。また stepped 経路では `--remote-expert-opt` をサポートせず、当該設定時は `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` で失敗します。

## 文書との照合

`docs/DETAILS.md` と `docs/INTEL.md` に `STRATA_VERIFY_PIPE` の個別説明や測定値は見つかりませんでした。ソースコメントは `STRATA_VERIFY_PIPE=0` が helper thread なしの serial segments になると説明し、実装も split segment がある場合に pool を同期実行してから graph を投入します。性能効果はこの調査では測定していません。

## 根拠

- 読み取りと先頭文字判定、stepped の位置づけ: `sycl/src/core/verify.cpp:101-103,2090-2093`。
- SYCL build への組み込み: `sycl/CMakeLists.txt:221`。
- split 境界の生成と `STRATA_VERIFY_SPLIT` の既定判定: `sycl/src/core/verify.cpp:1703-1717`。
- stepped segment capture の条件、および all-resident / eager 除外: `sycl/src/core/verify.cpp:1734-1742`。
- stepped run と remote-expert 制約: `sycl/src/core/verify.cpp:2041-2059`。
- helper thread、flag A 待機、graph 投入、serial fallback、pool wait: `sycl/src/core/verify.cpp:2063-2124`。
- segment 種別による serve 呼び出し: `sycl/src/core/verify.cpp:2138-2155`。
