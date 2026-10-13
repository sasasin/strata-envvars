# `STRATA_PREFILL_GROUP_GATHER`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

ストリーミング中の prompt prefill で、MMQ 用に expert の重みを group buffer へ集める処理を、expert ごとに行うか、複数 expert 分をまとめて行うかを選びます。既定では group gather を使います。対象経路では、group 内の最後のコピーを待ってから gather し、リング slot の解放 event も group 単位で記録します。無効にすると、コピー待ち・gather・slot 解放を expert ごとに行う経路になります。

## 値と判定

CUDA/HIP と SYCL の prefill 実装は、最初にこの判定へ到達したとき `static const bool` として値を読み、プロセス内に保持します。値は `std::atoi()` で変換し、未設定なら `true`、設定されていれば変換結果が 0 以外のとき `true` です。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| `0`、空文字、数値に変換できない文字列 | 無効 |
| `1`、負数など、`atoi()` の結果が 0 以外 | 有効 |

文字列全体の厳密な数値検証はしません。`atoi()` が数値の prefix を読み取るため、たとえば `1abc` は有効、`0abc` と `abc` は無効です。空白や符号も `atoi()` の変換規則に従います。判定後に環境変数を変更しても、同じプロセスでは再評価されません。

## 有効になる条件

環境変数の判定が有効でも、各 layer で次の条件をすべて満たす場合に限り group gather が選ばれます。

- streamed walk (`stream_all`) が有効。実装上はリングが標準 staging 数 `STAGE` より大きく、chunk が `stream_all_min()` 以上で、expert source が存在することが条件です。`STAGE` は 8、`stream_all_min()` は別変数 `STRATA_PREFILL_STREAM_MIN` 等により決まり、他の上書きがない場合の通常値は 1024 tokens です。
- その layer で MMQ plan が有効 (`use_mmq`)。
- layer の expert pack が native format (`lay.native`)。
- `MMQ_GROUP` が backend の `kGatherGroupMax` 以下。現行定義は双方 16 です。

そのため、通常 staging、MMQ を使わない layer、native でない pack では、この変数の設定は gather 経路を変えません。他の環境変数によって `stream_all` が使われない状態なら、同様に効果はありません。

## 実行時の詳細

有効時、streamed walk は `MMQ_GROUP` 個または group の末尾までの expert blob を group buffer に集めます。group に streamed expert があれば、その中で最後のコピー完了 event を compute stream が待ってから gather し、group の最後に当たる ring slot に解放 event を記録して各 slot の解放先をそこへ関連付けます。routing が選ばなかった expert により group が途中で切れる場合は、その時点の group を先に flush します。無効時は各 streamed expert のコピー完了を待ち、その expert の gather 後に個別 slot 解放 event を記録します。

CUDA/HIP では `gather_native_group()` がアラインメント条件を満たせば複数 blob を一つの kernel launch でコピーします。条件を満たさない場合は group gather 呼び出しが失敗し、同じ group の各 expert に `gather_native()` を呼びます。SYCL 側の `gather_native_group()` は現状 `false` を返す stub なので、grouping による待機と slot 解放のまとめは使われますが、blob gather 自体は expert ごとの `gather_native()` fallback になります。

この変数に対応する環境変数専用ログは見当たりません。ソースコメントには WDDM で expert ごとの wait/event record が GPU bubble を生み得るとの記述がありますが、`docs/DETAILS.md` にこの変数固有の測定条件や性能値は見つからなかったため、性能効果の数値は記載しません。

## 根拠

- 読み取り、default、真偽判定、適用条件: `src/prefill/prefill.cpp:3746-3753`; SYCL コピー: `sycl/src/prefill/prefill.cpp:3896-3903`。
- group の待機、gather、slot 解放、および無効時の expert 単位処理: `src/prefill/prefill.cpp:3756-3779,3782-3803,3873-3911`; SYCL: `sycl/src/prefill/prefill.cpp:3906-3938,4017-4043,4159-4224`。
- `stream_all` 条件: `src/prefill/prefill.cpp:149-153,2302-2303`; `STAGE` 定義: `src/prefill/prefill.cpp:107`。
- layer ごとの MMQ 判定: `src/prefill/prefill.cpp:2978-2980`。
- group gather 最大数: `include/strata/prefill/moe_mmq.hpp:71-76`。
- CUDA/HIP の aligned group copy と失敗条件: `src/prefill/moe_mmq.cu:248-264`; SYCL stub: `sycl/src/prefill/prefill.cpp:68-70`。
