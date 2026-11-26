# `FNX_PF_HC_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata-split` の prompt path にある hyper-connection の注入行について、`k_hcb_prep` が作った値と、`k_hcb_mixinj` で再計算した値との差を測り、stderr に表示するデバッグ用スイッチです。通常の読み取り計算を置き換えず、差分があっても値を修正したりエラー判定したりしません。実装は `fnx::pf_hc_read` です（`engine/src/split/src/prefill.cu:623-664`）。

この関数を含む `prefill.cu` は `STRATA_BUILD_SPLIT` が有効なときに追加される `strata-split-N` 実行ファイルのソースです。同オプションは既定 OFF で、split の CMake は CUDA または HIP の対象構成でのみ実行ファイルを作ります（`engine/CMakeLists.txt:922-927`、`engine/src/split/CMakeLists.txt:20-27,76-92,116-146`）。通常の `strata` 実行ファイルに対するスイッチではありません。

## 値と判定

`std::getenv("FNX_PF_HC_CHECK") != nullptr` で設定の有無だけを判定します。文字列を数値や真偽値に変換しません（`engine/src/split/src/prefill.cu:646-648`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| split の CUDA / HIP バイナリで `pf_hc_read` が呼ばれる場合 | 無効 | `1`、`true`、`0`、`false`、`0anything`、空文字を含む、環境に存在する任意の値 | なし（環境変数が存在すれば値の内容にかかわらず有効） |

`0` や空文字も設定済みとして扱われます。大文字小文字、空白、数値としての妥当性、文字列全体は検査しません。設定がなければ追加チェックを行いません。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で、対象プラットフォーム・backend 用の `strata-split-N` がビルドされていること。CMake では split を既定でビルドしません（`engine/CMakeLists.txt:922-927`）。split の追加は CUDA または HIP で行われ、`prefill.cu` は両 backend のソース一覧に入ります（`engine/src/split/CMakeLists.txt:20-27,76-92,120-146`）。
- split engine の prompt path が `pf_hc_read` を呼ぶこと。各層の prompt read から呼ばれます（`engine/src/split/src/prefill.cu:1541-1557,1648-1650,1717-1738`）。
- その呼び出しで `w_inj` が非 null であること。追加チェックの分岐は `check && w_inj` であり、注入重みがない場合は環境変数が設定済みでもスキップされます（`engine/src/split/src/prefill.cu:648-653`）。たとえば draft layer の呼び出しは `w_inj` と `inject` に null を渡すためチェックされません（`engine/src/split/src/prefill.cu:1265-1284`）。
- `FNX_PF_HC_CHECK` 自体に CLI 引数や別の環境変数による優先順位はありません。コード上、値の読み取り後に追加条件となるのは `w_inj` の有無です（`engine/src/split/src/prefill.cu:647-653`）。

## 実行時の詳細

判定値 `check` は関数内の `static const bool` です。プロセスの最初の `pf_hc_read` 呼び出しで一度環境を読み、その後は呼び出しごとに再読込しません。したがって、その初回評価後にプロセス環境を書き換えても判定は変わりません（`engine/src/split/src/prefill.cu:624-625,647`）。

通常経路では先に `k_hcb_prep` が注入行を作り、その後、`k_hcb_mixinj` が混合行を作ります（`engine/src/split/src/prefill.cu:623-627,645`）。チェックが有効で `w_inj` があると、追加の device buffer を確保し、`k_hcb_mixinj` を注入重み付きで再実行して別の注入行 `ref` を計算します。元の `inject` と `ref` を host にコピーして stream を同期し、要素ごとの絶対差の最大値と `ref` の最大絶対値を求めます（`engine/src/split/src/prefill.cu:648-661`）。この追加計算は各該当 `pf_hc_read` 呼び出しで行い、差分結果を保存・キャッシュしません。

比較結果は `hc check: inject largest difference %.3g of largest value %.3g` の形式で stderr に出ます。差分が大きい場合も、その値だけを理由にチェック処理は失敗せず、通常の後続計算へ進みます（`engine/src/split/src/prefill.cu:658-664`）。ただし追加確保・コピー・同期などの CUDA API エラーは `ckc` が `prefill: hc check: <CUDA error>` 形式の `std::runtime_error` にし（`engine/src/split/src/pf_common.cuh:27-29`）、split server の実行中エラー経路では `ERR ...` を stdout、`sfnx: failed: ...` を stderr に出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1102,1160-1166`）。

## ログと測定値

観測できる出力は、該当する read ごとの `hc check: inject largest difference %.3g of largest value %.3g` です（`engine/src/split/src/prefill.cu:658-661`）。通常の設定、または `w_inj == nullptr` の呼び出しではこの行は出ません。性能値は Strata の資料で確認できず、本書では記載しません。

## 根拠

- `engine/src/split/src/prefill.cu:623-664` — 読み取り、追加比較、ログ。
- `engine/src/split/src/prefill.cu:99-100,102-147` — `k_hcb_prep` と注入行生成。
- `engine/src/split/src/prefill.cu:1265-1284,1541-1557,1648-1650,1717-1738` — 呼び出し元とモデル状態による `w_inj` の有無。
- `engine/src/split/CMakeLists.txt:20-27,76-92,116-146`、`engine/CMakeLists.txt:922-927` — ビルド条件と対象実行ファイル。
- `engine/src/split/src/pf_common.cuh:27-29`、`engine/src/split/tools/sfnx.cpp:1094-1102,1160-1166` — GPU API エラーと実行中の失敗出力。
