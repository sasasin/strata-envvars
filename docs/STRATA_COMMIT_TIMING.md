# `STRATA_COMMIT_TIMING`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Verifier が GPU に投入する commit graph の実行時間を CUDA event で測り、累積平均を stderr に出す診断用の環境変数です。生成・検証の計算内容や commit graph の構成は変更しません。計測値は GPU 上の graph 区間であり、CPU 側の `Verifier::commit()` 全体の所要時間ではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| unset | 計測しない（既定） |
| 先頭文字が `1` | 計測する。`1`, `10`, `1anything` などが該当 |
| 空文字、先頭文字が `1` 以外 | 計測しない |

文字列全体の比較や数値変換はなく、`getenv()` が非 null で先頭文字が `'1'` かだけを調べます。判定結果は `commit()` 内の function-local `static` に初回評価時に保存されるため、その後の環境変更は反映されません。初回評価が commit graph を実行する経路に限られるため、graph を実行しない経路では読み取り自体も起きません。

## 有効になる条件

- CUDA/HIP の Verifier commit graph を実際に launch する経路で計測されます。
- `STRATA_GPU_METAL` のビルドでは `Verifier::commit()` が Metal engine の `window_commit()` を呼んで先に return するため、この環境変数の読み取り・計測処理を通りません。
- `last_t_ == 1` かつ `one_token_self_commit()` が真で、`always_publish_` が偽の場合は commit graph 自体を launch しません。この呼び出しでは計測もされません。
- 値が有効でも CUDA event の作成に失敗すると、その `Verifier` 関数内の static 状態で計測を無効化し、`cudaGetLastError()` を読み捨てます。
- `next_` がある場合は各 Verifier に `commit()` が再帰呼び出しされますが、計測 event と集計状態は関数内 static の1組を共有します。ソースには device ごとの計測状態がなく、event record の戻り値も検査しないため、複数 GPU の stage ごとの値として解釈できません。

`STRATA_COMMIT_SYNC` は `set_commit_async()` の非同期設定を止める別の制御です。計測区間の有無を決める変数ではありません。同期設定では commit graph の後に stream 同期し、非同期設定では完了 event を記録しますが、どちらの設定でも commit graph の前後に計測 event を置くコードは同じです。

## 実行時の詳細

計測が有効なとき、最初の graph launch 前に CUDA event を2つ作成します。各 commit graph の前後で同じ stream `cs_` に begin/end event を記録し、次の計測対象 commit に来たとき前回の end event を同期して elapsed time を取得します。取得に成功したサンプルだけを累積し、成功サンプル数が300の倍数のとき、累積平均を次の形式で stderr に出力します。

```text
strata verify: commit graph %.3f ms GPU on average over %lld commits
```

平均は直近300件だけではなく、最初からの累積平均です。CUDA event の同期・経過時間取得に失敗したサンプルは合計時間と件数に加えません。成功件数が300の倍数のまま連続して取得に失敗すると、同じ件数の平均ログが再度出ることがあります。event の record 呼び出し自体の戻り値はこのコードでは検査しません。測定値を1回も取得できない場合、平均ログは出ません。

計測コードは前回の end event を `cudaEventSynchronize()` するため、環境変数なしの場合とホスト側の待ち方が完全に同じとは限りません。性能比較ではこの計測処理自体が走っている条件として扱ってください。

## 根拠

- `src/core/verify.cpp:2645-2649` — Metal 経路は `window_commit()` の結果を返し、以降の CUDA graph 処理を通らない。
- `src/core/verify.cpp:2650-2657` — commit 件数の範囲確認と one-token self-commit の graph 省略条件。
- `src/core/verify.cpp:2659-2681` — 環境変数の判定、static cache、event の生成・同期・時間取得・平均ログ、graph launch。
- `src/core/verify.cpp:2682-2693` — `STRATA_COMMIT_SYNC` による非同期 commit と stream/event 同期の扱い。
- `src/core/verify.cpp:2015-2141` — commit graph の capture と instantiate。
- `src/program/generate.cpp:3491` — generate 経路が `set_commit_async(!multi_gpu)` を設定する箇所。

`docs/DETAILS.md` にこの計測用変数やその測定結果の説明は見当たりません。したがって、この文書では特定の性能値や計測の外部妥当性を述べていません。
