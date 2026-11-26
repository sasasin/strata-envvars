# `STRATA_SPEC_WATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_SPEC_WATCH` は、投機デコードの verify window ループが進捗しなくなったときに、段階名と stall report を stderr に出して engine プロセスを終了させる診断用 watchdog の秒数です。token の選択・draft・window 幅を変える設定ではありません。読み取りは `engine/src/program/generate.cpp` の投機ループ内にあります（`engine/src/program/generate.cpp:24459-24466, 24915-24936`）。

## 値と判定

値は `std::getenv` で取得し、未設定でないことに加えて `std::atoi(sw) > 0` のときだけ watchdog を起動します。起動時に同じ文字列をもう一度 `std::atoi` し、その `int` 値をスレッドに渡します。文字列全体の数値検査、末尾文字の検査、範囲検査はありません（`engine/src/program/generate.cpp:24917-24920`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 投機ループを実行する engine 経路 | watchdog を作らない | `atoi` の結果が 1 以上。例: `1`, `+2`, ` 3`, `5seconds`, `1.5` はそれぞれ正の値として扱われる | 空文字、`0`, `-1`, `true`, `0anything` は結果が 0 以下となり起動しない |

`atoi` のため大文字小文字の概念はなく、先頭の空白・符号は変換規則に従い、数値の後ろは無視されます。したがって `1.5` は 1 秒として扱われます。数字として読めない先頭（例: `true`）は 0 になります。数値範囲外の文字列に対する安全なエラー処理は実装されていません。起動後に読むのは秒数を一度取得するときだけで、その整数値はスレッドへコピーされます。実行中の環境変数変更は既存 watchdog に反映されません（同上）。

## 有効になる条件

- `--spec` が正で、prompt 処理が投機ループの開始位置を設定し、まだ生成可能な token が残り、EOS で終了済みでないことが必要です。通常の token loop はこの条件で投機ループへ移り、`spec_loop_runs` も開始位置・残り token 数・終了状態を判定します（`engine/src/program/generate.cpp:24454-24466`; `engine/include/strata/spec/spec_start.hpp:12-17`）。
- 上記の経路は `engine/src/program/generate.cpp` にある CUDA/HIP 側の実装です。この名前の直接読み取りは Strata 全体でここだけで、`engine/sycl/src/program/generate.cpp` にはありません。Metal/SYCL などこの実装を通らない経路では、この変数を読む Strata の処理は確認できません（`engine/src/program/generate.cpp:24915-24917` および全リポジトリの名前検索）。
- 既定値や CLI 引数との優先順位はなく、CLI 設定を上書きしません。正の値でも投機ループに入らなければ読み取り位置に到達せず、何も起動しません（`engine/src/program/generate.cpp:24466, 24917`）。
- 読み取り値を子プロセスへ転送する処理はこの engine ソースにはありません。環境変数は engine プロセス内で参照されます。

## 実行時の詳細

投機ループに入った後、`STRATA_SPEC_WATCH` が正と判定されると `progress().busy` を `true` にし、秒数を捕捉した detached thread を一つ起動します（`engine/src/program/generate.cpp:24917-24921`）。thread は 1 秒間隔で共有 `Progress.beats` を監視し、値が増えれば最後の heartbeat 時刻を更新します。指定秒数の間 heartbeat が変わらなければ、現在の stage と `ticks` の差を使って報告し、GPU wait を解放する関数を呼んだあと `std::abort()` します（`engine/src/program/generate.cpp:24921-24936`; `engine/include/strata/core/progress.hpp:17-27, 56-75`）。

報告は verify window だけに限定されません。監視対象は共有 heartbeat であり、prompt chunk や他の処理も同じカウンターを進めます（`engine/include/strata/core/progress.hpp:17-27, 69-75`）。また、この detached thread にはループ終了時の停止条件がなく、`busy` 状態も終了判定に使いません。したがって、投機ループ終了後も thread は共有 heartbeat の監視を続け、指定秒数以上 heartbeat がない状態になると同じ報告と abort に進みます（`engine/src/program/generate.cpp:24920-24936`）。

## ログと測定値

閾値に達すると stderr に次の形式で出します（stage 部分はその時点の `where` と `detail`、該当時は prompt chunk 情報です）。

```text
strata generate: no progress for <秒数> s (<stage>)
```

続いて `stall_report` が engine version、stage の継続秒数、最後の完了 step 以降の layer 数、取得できる場合は request 開始時の VRAM 情報などを stderr に書き、GPU wait 解放処理の出力後に stderr を flush して `abort()` します。終了コードを返す graceful timeout ではなく、プロセスの異常終了経路です（`engine/src/program/generate.cpp:1833-1837, 2093-2110, 24929-24935`）。

測定値はありません。この変数は診断用の timeout です。

## 根拠

- `engine/src/program/generate.cpp:24454-24466` — 投機ループ開始位置と実行条件。
- `engine/include/strata/spec/spec_start.hpp:12-17` — 投機ループ開始・終了条件。
- `engine/src/program/generate.cpp:24915-24936` — 環境変数の判定、thread、stall report、abort。
- `engine/include/strata/core/progress.hpp:17-27, 56-75` — 共有進捗情報と heartbeat。
- `engine/src/program/generate.cpp:1833-1837, 2093-2110` — stage 表示と stall report の内容。
