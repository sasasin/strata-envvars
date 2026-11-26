# `STRATA_COMMIT_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の `Verifier::commit` が commit graph を launch するとき、その GPU 実行時間を CUDA event で測り、累積平均を stderr に出す計測用スイッチです。commit graph 自体の選択や引数を切り替える設定ではなく、計測コードが event の記録・同期を追加します。実行経路は `engine/src/core/verify.cpp:4527-4564` です。

## 値と判定

`CommitTiming` の関数内 `static` 初期化時に `std::getenv` し、未設定でないことに加えて `v[0] == '1'` だけを判定します。数値変換や文字列全体の検査はありません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| commit graph 計測コードを通る CUDA/HIP 経路 | 無効 | 先頭 byte が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `01`, `true`, `TRUE`, 先頭が空白の ` 1` など |

値は大文字小文字を変換せず、空白除去もせず、境界値・数値としての妥当性も検査しません。空文字は環境変数として設定済みでも無効です。判定コード: `engine/src/core/verify.cpp:4544-4550`。

## 有効になる条件

- CUDA/HIP GPU engine のビルドであること。共通 GPU engine は `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` の場合に構成され、`verify.cpp` を `strata_engine` に含みます（`engine/cmake/strata_gpu_engine.cmake:6-9,310-316`）。
- `Verifier::commit` が Metal 委譲に入らず、commit graph を launch する分岐に入ること。Metal は `window_commit` に委譲して直ちに戻ります（`engine/src/core/verify.cpp:4527-4530`）。SYCL は別の `engine/sycl/src/core/verify.cpp` をビルドし、候補名のリポジトリ全体検索ではその実装に読み取り箇所はありません（`engine/sycl/CMakeLists.txt:290-299`）。
- 1-token self-commit 条件（`last_t_ == 1 && !always_publish_ && one_token_self_commit() && !g_qfuse()`）に該当しないこと。この経路は commit graph を launch せず、その呼び出しでは `CommitTiming` も初期化されません（`engine/src/core/verify.cpp:4537-4544`）。
- 初回に計測コードへ到達した時点で、値の先頭 byte が `1` であること。CLI 引数や設定ファイルによる上書きはこの読み取り箇所にはありません。`STRATA_COMMIT_SYNC` は async commit の可否を別に決めますが、計測フラグの値は変更しません（`engine/src/core/verify.cpp:4524-4525,4568-4575`）。

## 実行時の詳細

`CommitTiming` は関数内 `static` で、最初に commit graph 分岐へ入った時に一度だけ環境を読み、そのプロセス内の後続 `Verifier` 呼び出しでも同じ `on` 状態を使います。以後にプロセス環境を変更しても再読込されません。self-commit のみの呼び出しでは初期化が遅れます（`engine/src/core/verify.cpp:4537-4550`）。

有効時は event 2 個を作成し、commit stream `cs_` に graph launch の直前・直後で event を記録します。次回の commit graph 分岐で終了 event を同期し、経過時間取得に成功したサンプルだけ `ms` と `n` に加算します。`n` が 300 の倍数になるたび、全成功サンプルを通じた累積平均を出します。従ってログは測定対象の launch と同じ呼び出しではなく、次の commit graph 呼び出しで出ることがあります。終了時に残った pending sample を出力する処理はこの箇所にはありません（`engine/src/core/verify.cpp:4551-4563`）。

event 作成のどちらかが失敗すると計測を無効化し、`cudaGetLastError()` を呼びます。event の record の戻り値は検査しません。同期または経過時間取得に失敗した sample は加算されず、ここから専用のエラー文は出ません。commit graph launch や通常の stream 同期の失敗は計測処理とは別に `verify: commit launch: ...` または `verify: commit: ...` を `err` に設定して失敗を返します（`engine/src/core/verify.cpp:4551-4570`）。呼び出し側では speculative generate が `ERR ...` を stdout に出して終了します（`engine/src/program/generate.cpp:23066-23070`）。

## ログと測定値

成功サンプル数が 300 の倍数になると、stderr に次の形式で出力します。平均値は累積した全成功サンプルに対する GPU 時間で、直近 300 件だけの平均ではありません。

```text
strata verify: commit graph %.3f ms GPU on average over %lld commits
```

出力箇所: `engine/src/core/verify.cpp:4553-4559`。この環境変数について、コード外の測定値や性能向上値は確認できません。

## 根拠

- 全参照検索で、Strata の実行コードの環境読み取りは `engine/src/core/verify.cpp:4549` のみ。`terminal/data/settings-register.json` にも設定登録がありますが、これは環境値を読む実装ではありません。
- CUDA/HIP ビルド条件と engine ソース登録: `engine/cmake/strata_gpu_engine.cmake:6-9,310-316`。
- Metal の委譲、self-commit の分岐、計測・出力・commit エラー処理: `engine/src/core/verify.cpp:4527-4575`。
- caller の失敗表示: `engine/src/program/generate.cpp:23066-23070`。
