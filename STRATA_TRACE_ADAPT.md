# `STRATA_TRACE_ADAPT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応 expert tier の swap を追跡する診断用スイッチです。適応 round の実行状況と、前 round で始めた非同期コピーが次の decode window までに完了したかを stderr に出します。swap の選択、コピー、常駐状態を変える設定ではありません。

読み取り箇所は CUDA 系 `src/program/generate.cpp` と SYCL 系 `sycl/src/program/generate.cpp` のそれぞれ2箇所です。候補一覧にはありますが、セットアップや Python サーバーではなく engine の生成処理が読みます。

## 値と判定

値は parse されず、`std::getenv("STRATA_TRACE_ADAPT") != nullptr` で設定有無だけを判定します。

| 環境変数の状態 | ログ |
|---|---|
| 未設定 | 抑止 |
| `1`、`0`、`false`、その他の文字列 | 有効 |
| 空文字で設定 | 有効 |

各読み取り結果は `static const bool` に保存されます。`apply_pending` 側と `adapt` 側はそれぞれ初回に評価され、その後にプロセス環境を書き換えても、既に評価された側は再判定しません。

## 有効になる条件

適応 tier が有効な生成処理で、該当する `apply_pending` または `adapt` の処理に到達するとログが出ます。適応用 routing usage 配列は `--adapt-every` と `--adapt-swaps` の両方が正の場合に確保されます。従ってこの機能は適応 tier を使わない実行では診断対象となる round がありません。

CUDA と SYCL に同じ環境変数判定およびログ分岐があります。SYCL 側は `apply_pending` を `sycl::exception` で捕捉するラッパー内に置いていますが、環境変数の判定方法とログ内容は同じです。

## 実行時の詳細

`apply_pending` は、未完了の swap があると、待機しない呼び出しではコピー完了イベントを調べます。未完了なら次のログを出して、この window では対象 expert を非 resident のままにします。完了時には pending 数を出してから常駐表を更新します。

- `strata: PENDING not landed, %zu stay non-resident this window`
- `strata: PENDING landed, %zu experts become resident`

`adapt` は round 番号を進めます。前 round の swap がまだ `pending` に残っていれば、その round を skip した理由を出して終了します。そうでなければ検討開始を出し、routing usage と resident 状態を使って候補 swap を決めます。処理後は実際に選んだ swap 数と `--adapt-swaps` の上限を表示し、usage を減衰させます。

- `strata: ADAPT round=%lld SKIPPED, %zu swaps still in flight`
- `strata: ADAPT round=%lld considering`
- `strata: ADAPT round=%lld swapped %zu of %d slots, usage decayed`

ログに `swapped 0` と出る場合もあります。診断ログ自体は swap 選択やデータを変更せず、コピー完了の待ち方も変更しません。ソース内の `=1` コメントは利用例であり、実装上は値が `1` かどうかを検証していません。

## 根拠

- `src/program/generate.cpp:12828-12829` — 適応 routing usage 配列の確保条件。
- `src/program/generate.cpp:12843-12866` — `apply_pending` の環境判定、コピー完了の確認、resident 表更新とログ。
- `src/program/generate.cpp:12870-12960` — `adapt` の環境判定、skip / considering / swapped ログと適応処理。
- `sycl/src/program/generate.cpp:12098-12152` — SYCL 側の usage 配列と `apply_pending`。
- `sycl/src/program/generate.cpp:12156-12249` — SYCL 側の `adapt` 判定と同じログ。
- `docs/DETAILS.md:106-108,168-180` — 適応 tier と関連オプションの説明。`STRATA_TRACE_ADAPT` 自体の説明はなく、ログ文言と値の判定はソースから確認した。
