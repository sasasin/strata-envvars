# `STRATA_FOLLOW`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL の serve decode 経路で、リクエスト開始時にファイルから読み込んだ token ID 列を、通常の argmax 出力の代わりに出力・次状態へ渡すテスト用フックです。値を読む実装は `sycl/src/program/generate.cpp` にだけあります。CUDA 側の `src/program/generate.cpp` には同名環境変数の読み取りはありません。同ファイルにある `--spec-follow` は別の CLI オプションです。

## 値と判定

環境変数の文字列全体を解釈せず、ファイル名として `fopen(fp, "r")` に渡します。

| 状態 | 動作 |
|---|---|
| 未設定 | このフックは使わず、通常の argmax decode を行う |
| 設定済みだがファイルを開けない（空文字を含む） | 読み込みを行わず、通常の argmax decode を行う。エラーや警告は出さない |
| ファイルを開ける | `%lld` の `fscanf` を繰り返し、空白区切りで読めた整数を `int32_t` に変換して配列に保存する。最初の変換失敗で読み込みを止め、ファイルを閉じて削除する |

明示的な token ID の範囲・語彙サイズ検証はありません。各 decode window で、配列から対応する値を取り出し、値が `0` 以上の場合にのみ argmax の出力位置を置き換えます。負の値は強制値として使われません。配列が空なら通常 decode と同じです。

## 有効になる条件

- 読み取り箇所は `sycl/src/program/generate.cpp` の serve decode request 内です。ソース中のコメントも test path として説明しており、CUDA の `src/program/generate.cpp` に同じ環境変数の実装はありません。
- ファイルが開け、読み込み後の配列に少なくとも一つ値があると、強制出力処理に入ります。以降の token は `produced_n + window 内の位置` で配列を参照します。
- リクエストの `max_new` や EOS 判定など既存の serve decode 終了条件は別途適用されます。

## 実行時の詳細

環境変数はプロセス起動時にキャッシュせず、各 serve request の decode 開始時に `getenv` します。設定値が指すファイルは、その request の開始時に一度だけ読まれます。正常に open できた場合、読み込み後に `std::remove(fp)` で削除するため、同じファイルは次の request では通常再利用できません。open に失敗した場合は削除しません。

forced token は verifier の window 実行後に `outv` へ反映されます。その後、次の window token と一致する範囲を数えて commit 数を決め、`T <token-id>` 行として出力されます。したがって、この経路は token 列を出力に差し替えるだけでなく、後続 window が使う継続にもその値を渡します。

関連する `STRATA_FOLLOW_LOGPOS` が設定されている場合、別の static 初期化処理がそのパスを append mode で開き、forced token の window log-probability を書きます。top-k 候補数は `STRATA_LOGPOS_TOPK` が別途決めます。これらのログ用変数は `STRATA_FOLLOW` 自体の必須条件ではありません。

## 根拠

- `sycl/src/program/generate.cpp:10729-10745` — test path の説明、request ごとの `getenv`、整数読み込み、close/remove、関連ログファイルの static open。
- `sycl/src/program/generate.cpp:11520-11536` — verifier 実行後の forced token 反映と任意 log-probability 呼び出し。
- `sycl/src/program/generate.cpp:11550-11628` — commit、`T` 出力、EOS・停止条件、次 window への継続。
- `src/program/generate.cpp:962-967,2604` — CUDA 側の `--spec-follow` CLI 定義。これは `STRATA_FOLLOW` の環境変数読み取りではありません。
- `sycl/src/core/verify.cpp:2615-2629` — `STRATA_LOGPOS_TOPK` の値を `atoi` で読み、上限 256 に制限して log-probability 出力へ反映。
