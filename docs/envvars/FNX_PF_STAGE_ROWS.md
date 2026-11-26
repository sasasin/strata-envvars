# `FNX_PF_STAGE_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata-split` の prompt prefill で、GPU の ExpertCache に入っていない experts を GPU の一時 stage buffer へコピーするか、RAM 上の元データから読み続けるかを切り替える prompt 長のしきい値です。しきい値以上なら stage を使い、未満なら stage コピーを行わず、各 chunk の処理中に experts を RAM から直接読みます。expert の選択や prompt の分割値そのものを設定する変数ではありません。判定は `Engine::prefill`、値の保存は `Engine::prefill_alloc` が行います（`engine/src/split/src/prefill.cu:1123-1127, 1307-1309, 1452-1495, 1726-1754`）。

## 値と判定

| 条件（build / 状態） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| ExpertCache の slot があるカード | `2048` tokens | `0` から `2147483647` の整数。例: `0`, `1`, `+2048`, `2048` | 負数、`2147483648` 以上は範囲エラー。空文字、`true`、`1x`、前後の空白を含む値は整数 parse エラー |
| `w.ec.n_slots == 0` のカード | 読み取られない | なし | 値にかかわらずこの分岐では無視 |

`fnx::env_int` は `std::getenv` で未設定かを判定し、設定値を符号付き base-10 の `strtoll` で文字列末尾まで parse します。先頭の `+` / `-` は parse 対象ですが、空文字・空白・数値以外の末尾・`long long` の範囲外は `"FNX_PF_STAGE_ROWS: '<値>' is not a whole number"` の例外になります。空文字は未設定扱いではありません。parse 後、この変数固有の範囲は `0..INT32_MAX` で、範囲外は `"FNX_PF_STAGE_ROWS: want tokens >= 0, got <値>"` になります。大文字小文字比較や真偽値変換はありません（`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/prefill.cu:1123-1127`）。

## 有効になる条件

- このコードは `STRATA_BUILD_SPLIT=ON` で追加される `strata-split-N` の実装です。通常の engine、Metal、SYCL ではこの読み取り箇所はありません。CMake の説明は Linux CUDA/HIP build を対象としています。実際の guard は CUDA path から Windows/Apple を除外し、HIP path は `STRATA_ENABLE_HIP=ON`, `STRATA_ENABLE_CUDA=OFF`, `APPLE` 以外で選びます。この CMake ファイルには HIP の Windows を明示的に除外する条件はありません（`engine/CMakeLists.txt:922-927`; `engine/src/split/CMakeLists.txt:1-5, 20-27, 121-153`）。
- `Engine::prefill_alloc` でカードの `ExpertCache` に `n_slots` がある場合にだけ値を読み、`Pf::stage_rows` に保存します。slot がない場合は変数を読まず、負値や不正文字列もこの箇所では検査しません（`engine/src/split/src/prefill.cu:1123-1128`）。
- しきい値に達しても、stage buffer が実際に確保されていなければ staging は有効になりません。`pf_stage_bytes` は slot がない場合に 0 を返し、stage 容量は各層の非 resident experts の量と `FNX_PF_STAGE_MIB`（既定 384 MiB、0 なら容量 0）で制限されます（`engine/src/split/src/prefill.cu:1232-1258`）。
- CLI 引数や設定値による上書きはこの読み取り経路にはありません。`FNX_PF_STAGE_ROWS` 自体を `getenv` で読むため、実行 engine process の環境値が使われます（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/src/prefill.cu:1123-1127`）。

## 実行時の詳細

値は Engine 初期化中、カードごとの `prefill_alloc` で読み取られ、各カードの `Pf::stage_rows` に保持されます。要求ごとには再読しません。Engine 初期化後に process の環境値を変更しても、保持済みのしきい値には反映されません（`engine/src/split/src/prefill.cu:854-864, 1123-1127`; `engine/src/split/src/engine.cu:317-319, 359-391`）。

各 prompt では `stage[0]` が存在し、かつ prompt の token 数が `stage_rows` 以上なら staging が有効です。したがって `0` は空でない prompt を含め、stage buffer がある全 prompt をしきい値判定で通します。stage がなければ、値が 0 でも staging は有効になりません（`engine/src/split/src/prefill.cu:1300-1309`）。

staging 時は層ごとに ExpertCache の slot にある experts、stage buffer に収まる RAM 上の experts、収まらず RAM から直接読む experts の参照表を作ります。stage buffer は2面を層番号の偶奇で使い分け、次の層のデータをコピーします。staging 無効時はこの表作成・stage コピーを通らず、通常の expert source を使います（`engine/src/split/src/prefill.cu:1452-1502, 1513, 1594-1596, 1726-1754`）。

不正値や範囲外値は初期化時の例外になります。`sfnx` の起動時 catch は `ERR <理由>` を出力し、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1097-1103, 1134-1135`）。

## ログと測定値

この変数固有の有効・無効ログはありません。`FNX_PF_TIMING` が有効なら各 prefill pass の stderr ログに、staging 時のカード別「experts copied in」と「read in place」の MiB が含まれます（`engine/src/split/src/prefill.cu:1831-1841`）。この変数による性能測定値は、調査対象ソースからは確認できません。

## 根拠

- 読み取り・既定値・検査: `engine/src/split/src/env.hpp:15-40`; `engine/src/split/src/prefill.cu:1123-1127`
- build と機能の範囲: `engine/CMakeLists.txt:922-927`; `engine/src/split/CMakeLists.txt:1-5, 20-27, 121-153`
- stage buffer の容量・割り当て: `engine/src/split/src/prefill.cu:1232-1258`; `engine/src/split/src/engine.cu:317-319, 359-391`
- prompt 長による分岐と staging 処理: `engine/src/split/src/prefill.cu:1300-1309, 1452-1502, 1513, 1594-1596, 1726-1754`
- 失敗出力と timing ログ: `engine/src/split/tools/sfnx.cpp:1097-1103, 1134-1135`; `engine/src/split/src/prefill.cu:1831-1841`
