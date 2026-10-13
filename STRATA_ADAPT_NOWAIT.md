# `STRATA_ADAPT_NOWAIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数と bench の結果・設定ファイルは実装根拠の対象外。

## 役割

adaptive tier が直前の decode window で開始した expert swap の完了を待たずに、次の window を始める診断・実験用スイッチです。CUDA と SYCL の生成経路に実装があります。コピーが間に合ったかどうかで residency table を更新する window が変わり得るため、コメントでは GPU と CPU のどちらで expert を計算するか、および丸め差により結果が timing に依存すると説明されています。通常の待機経路ではコピー完了を待ってから次の window に進みます。

## 値と判定

値は文字列全体や数値として parse せず、環境変数の先頭文字だけを判定します。

| 値 | 結果 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| それ以外（例: `0`, `true`, ` 1`, `01`） | 無効 |

大文字小文字、空白、後続文字、数値としての妥当性は調べません。判定結果は `static const bool` に保存されます。最初の `adapt_nowait()` 呼び出しで評価し、その後プロセス内で環境を書き換えても反映されません。サーバー経路では overlap 条件の判定時にもこの helper が呼ばれ得ます。

## 有効になる条件

値が有効でも、adaptive tier の pending swap がある decode 経路でのみ処理に差が出ます。adaptive tier は `--adapt-every` と `--adapt-swaps` で有効にします。pending swap がなければ `apply_pending(false)` は何もせず、変数による待機差はありません。

`STRATA_ADAPT_OVERLAP` と同時に有効な場合、CUDA のサーバー経路では overlap が `STRATA_ADAPT_NOWAIT` を無効条件として扱い、要求が明示されていれば overlap を無効にした理由を stderr に出します。SYCL 側にはこの overlap 判定の実装がなく、nowait 分岐自体が CUDA と同様にあります。

## 実行時の詳細

次の decode window に入る直前、CUDA のサーバー経路・通常の生成経路、および SYCL のサーバー経路・通常の生成経路で `adapt_nowait()` が真なら `apply_pending(false)` を呼びます。`false` は同期待ちを行わず、CUDA では `cudaEventQuery()`、SYCL では event の execution status を確認します。swap copy がまだ完了していなければその場で戻り、pending list と residency table はそのままなので、window は古い residency table を使って進みます。完了済みなら pin の解除、resident RAM 交換の commit、residency table 更新と device への再 upload を行い、pending 状態を消します。

このため、次の window の開始をコピー完了まで止めませんが、更新される window がコピー所要時間に依存します。コードコメントは、その結果、入れ替え expert が GPU/CPU のどちらで走るかが timing に依存し、両者の丸め差も結果に影響すると記しています。window 内部で swap が完了したかを待つ layer gate はこの変数の分岐にはありません。

## 根拠

- `src/program/generate.cpp:1314-1318`: CUDA の値判定とプロセス内キャッシュ。
- `sycl/src/program/generate.cpp:1265-1269`: SYCL の値判定とプロセス内キャッシュ。
- `src/program/generate.cpp:8315-8337`: CUDA の `apply_pending(false)` が未完了 event で戻る条件、および完了後の table 更新。
- `sycl/src/program/generate.cpp:7781-7807`: SYCL の同等処理。
- `src/program/generate.cpp:8284-8286,8297-8304`: CUDA の overlap が `STRATA_ADAPT_NOWAIT` を除外し、要求時に理由をログする分岐。
- CUDA の呼び出し箇所: `src/program/generate.cpp:11856-11875,13064-13068`。
- SYCL の呼び出し箇所: `sycl/src/program/generate.cpp:11148-11153,12362-12366`。
- `docs/DETAILS.md:1699-1705`: `STRATA_ADAPT_OVERLAP` の適用条件に本変数が挙がる。nowait 自体の値判定や性能測定の説明は同資料にない。
