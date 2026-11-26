# `STRATA_SPLIT_SMALL_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_SPLIT_SMALL_OWN` で決まるチャンク幅を S、`STRATA_SPLIT_SMALL_MAX` から決まる閾値を M とすると、serve の複数 GPU レイヤー分割で、lend 処理に渡されたプロンプト区間が M トークン以下の場合に、その区間用のチャンク要求を最大 S トークンへ下げる。S トークン分の prompt buffer 用スロットを各段の cache に確保する `STRATA_SPLIT_SMALL_OWN` と組み合わせて使う変数であり、この変数だけでは機能を有効にしない。読み取りと閾値設定は CUDA 系・SYCL 系の `engine/.../program/generate.cpp` にある serve 初期化中の処理で行う（CUDA: `engine/src/program/generate.cpp:13171-13197`、SYCL: `engine/sycl/src/program/generate.cpp:7629-7655`）。

実際の判定対象は必ずしもリクエスト全体の prompt 長ではなく、serve が `lend()` に渡す個々の非-window 区間の長さ `to - at` である。区間長が M 以下なら `want_full` を `min(want_full, S)` にし、そうでなければ通常の `want_full` を使う（CUDA: `engine/src/program/generate.cpp:20611-20616,21551-21564`、SYCL: `engine/sycl/src/program/generate.cpp:11403-11414,11638-11652`）。この変数は生成 token の選択や decode の値を直接変更する分岐ではなく、prompt path が必要とするチャンクと cache slot の lend / relayout を選ぶ。

## 値と判定

変数自体は `std::getenv` で読み、設定されていれば `std::atoll` に渡す。数値全体の妥当性確認やエラー処理はない。`split_small_max = max(S, atoll(value))` なので、値 M は S 未満にならない。未設定時も M=S となる。S は別変数 `STRATA_SPLIT_SMALL_OWN` の値を `atoll` で読み、`request_chunk(value, o.prefill_chunk)` で正数を 256 の倍数へ切り上げて `--prefill` のチャンク上限以下にした値である（CUDA: `engine/src/program/generate.cpp:11159-11165,13177-13183`、SYCL: `engine/sycl/src/program/generate.cpp:6640-6645,7635-7641`）。

| 条件 | `STRATA_SPLIT_SMALL_MAX` 未設定 | 設定時に有効になる値 | 設定時に閾値へ反映される値 |
|---|---|---|---|
| serve の複数 GPU 分割、lendable な `pf_parts` と非空の `host_res` がある。さらに S > 0 | M=S | `atoll` が返す整数値 | `max(S, atoll(value))`。S より小さい値は S に補正 |
| 上記条件内だが S <= 0 | split-small 機能は無効（M=0） | 読み取り自体は行う | M は 0 のまま。値は機能を有効化しない |
| `multi_gpu`、`pf_parts`、または `host_res` の条件を満たさない | 変数の読み取り箇所に入らない | 該当なし | 影響なし |

空文字は設定ありとして `atoll("")` が 0 を返すため、S>0 なら M=S。`"0"`、`"0anything"`、数値で始まらない文字列（例 `"true"`）も 0 となり M=S。負値（例 `"-1"`）も `max` により M=S。S より大きい数値（例 S=1024、値 `2048`）は M=2048。正の数値接頭部の後ろに文字があっても、その接頭部までが変換される（例 `"2048junk"`）。先頭の空白と符号は `atoll` の変換規則に従う。大文字小文字を比較する処理はない。上限 clamp、変換失敗の警告や終了処理もない。S 自体が 0 以下なら、M の値にかかわらず機能は無効である（CUDA: `engine/src/program/generate.cpp:13177-13183`、SYCL: `engine/sycl/src/program/generate.cpp:7635-7641`）。

## 有効になる条件

- `o.serve` の serve 初期化経路であること。`--layer-split` は `--serve` を必要とする（CUDA: `engine/src/program/generate.cpp:4848-4853,12302-12307`）。通常の一回実行 generate 経路には、この変数の読み取り箇所がない。
- `multi_gpu` が真であること。これは split device が指定され、同一 GPU 扱いではない場合に設定され、`--split-skip-if-fits` が layer split を解消する経路では false になる（CUDA: `engine/src/program/generate.cpp:4856,6479`）。`--split-device 0` による同一 GPU の分割では適用されない。
- lend 対象の `pf_parts` と非空の `host_res` があること。どちらかが空なら `getenv("STRATA_SPLIT_SMALL_MAX")` を含む処理に入らない（CUDA: `engine/src/program/generate.cpp:13177-13183`、SYCL: `engine/sycl/src/program/generate.cpp:7635-7641`）。
- `STRATA_SPLIT_SMALL_OWN` が正の S を作ること。未設定、空文字、非数値、0、負数なら `request_chunk` が S=0 とし、この変数の設定値だけでは有効化されない。正の S は 256 単位へ切り上げられ、`o.prefill_chunk`（CLI `--prefill` が決める prompt chunk）で上限を受ける（CUDA: `engine/src/program/generate.cpp:11159-11165,13179-13183`）。
- 各 `lend()` 呼び出しで `tokens <= M` となる非-window prompt 区間であること。window 区間は CUDA/SYCL とも `lend()` ではなく `read_windows()` に進む。CUDA では `o.prefill_head_alias` が真の場合に `want_seg` を `o.prefill_chunk` にする分岐があり、M 判定を使わない。また、復元した計画区間に `exact > 0` が渡る CUDA 経路では `want_seg` でなく exact 値が優先される（CUDA: `engine/src/program/generate.cpp:20611-20616,21551-21571`）。

## 実行時の詳細

CUDA と SYCL のどちらも、serve の prompt path 初期化後、リクエスト処理ループに入る前に値を読み、`split_small` と `split_small_max` に保持する。環境変数をリクエストごとに再読込する処理や、この値の static cache はないため、実行中にプロセス環境を変えても、この serve インスタンスの保持値には反映されない（CUDA: `engine/src/program/generate.cpp:13169-13183`、SYCL: `engine/sycl/src/program/generate.cpp:7628-7641`）。

区間長が M 以下のとき、要求チャンクは `min(want_full, S)` となる。これにより大きな通常 chunk を使う代わりに S 以下の chunk で段ごとの prompt path を relayout して読み進める。初期化側では S 用の slot 範囲の residency を `kNotResident` に変更し、該当する場合に residency table を各 device へ再 upload する。コードコメントはこの設定で S 以下の prompt は複数 S-token chunk で読まれ、対象 expert を resident 扱いしない構成を説明している（CUDA: `engine/src/program/generate.cpp:13171-13206,20611-20616,20694-20699`、SYCL: `engine/sycl/src/program/generate.cpp:7629-7665,11408-11414,11426-11439`）。

`STRATA_SPLIT_SMALL_MAX` の設定だけでは処理失敗にならない。無効な文字列は `atoll` の結果に従い M=S になる。別途 `lend()` の slot 計算または `Prefill::relayout` が失敗した場合は、serve の標準出力へ `ERR lending the prompt path its slots failed: ...` を出してリクエスト処理を終了する（CUDA: `engine/src/program/generate.cpp:20617-20620,21563-21565`、SYCL: `engine/sycl/src/program/generate.cpp:11412-11414,11647-11649,11659-11664`）。

## ログと測定値

この変数の値 M を表示する専用ログはない。S>0 で対象 cache part がある場合は、初期化時に `strata serve:   CUDA%d keeps %lld slots for %lld-token prompts (%lld experts no longer resident)` を stderr に出すが、この行が表示するのは S と確保・非resident化した数であり、M ではない（CUDA: `engine/src/program/generate.cpp:13185-13197`、SYCL: `engine/sycl/src/program/generate.cpp:7643-7655`）。読み込み時間は trace 有効時に `strata trace: read %lld tokens (%s) in %.1f ms` として出るが、M の判定結果を直接記録するログではない（CUDA: `engine/src/program/generate.cpp:21571-21580`、SYCL: `engine/sycl/src/program/generate.cpp:11651-11657`）。`docs/DETAILS.md` にこの変数名の記載は見つからず、条件付きの測定値を確認できなかったため性能値は記載しない。

## 根拠

- 候補名の全参照を調査した結果、実際の環境読み取りは CUDA 系と SYCL 系の上記2箇所の `std::getenv`。`terminal/data/settings-register.json` にも名前の登録があるが、それ自体は環境値の読み取り処理ではない。
- CUDA の初期化・値判定・slot 状態更新: `engine/src/program/generate.cpp:13171-13206`。
- CUDA の lend 時の M 判定と実際の区間読込: `engine/src/program/generate.cpp:20611-20620,21551-21580`。
- SYCL の初期化・値判定・slot 状態更新: `engine/sycl/src/program/generate.cpp:7629-7665`。
- SYCL の lend 時の M 判定と区間読込: `engine/sycl/src/program/generate.cpp:11400-11439,11638-11664`。
- `request_chunk` の 256-token 丸めと `o.prefill_chunk` 上限: `engine/src/program/generate.cpp:11159-11165`、`engine/sycl/src/program/generate.cpp:6640-6645`。
