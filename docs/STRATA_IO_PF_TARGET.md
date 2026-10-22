# `STRATA_IO_PF_TARGET`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の mapped file tier I/O prefetch で、先読みした byte 数のうち実際に demand された割合を適応的に調整する目標値です。先読み使用率の EWMA がこの値を下回る window では、自動計算する window byte 予算を縮め、目標以上なら回復させます。読み込み worker や先読みそのものを直接 ON/OFF する設定ではありません。

## 値と判定

`FileExpertSource::set_io_prefetch()` が環境変数を読み、`std::atof()` で変換した値を `[0.0, 1.0]` に clamp します。未設定ならメンバーの初期値 `0.5` を使います。空文字や数値として読めない文字列は `atof()` により `0` となり、フィードバックを止めます。数値の後ろに文字があっても `atof()` が読める先頭部分が使われます。

| 入力例 | 読み取られる目標値 |
|---|---:|
| unset | `0.5` |
| `0`, 空文字, `abc`, `-1` | `0` |
| `0.7`, `0.7tail` | `0.7` |
| `2` | `1` |

目標値が `0` 以下なら、window ごとのフィードバック更新条件を満たさず、`io_scale_` は変化しません。`atof()` の数値接頭辞変換なので、文字列全体の厳密な数値検証はありません。

## 有効になる条件

- `strata generate --mmap-experts` の mapped file tier で、`STRATA_IO_PREFETCH` により I/O prefetch が開始されること。Linux では既定有効となる経路がありますが、既定条件はファイル tier と page cache 状態で異なります。
- `STRATA_IO_PF_SCHED` が設定され、`atoi()` の結果が 0 以外であること。未設定、空文字、`atoi()` が 0 を返す値では scheduler が無効で、この目標値は使われません。
- Linux 以外、unbuffered reads、mapped source が開けない場合などで `set_io_prefetch()` が有効にならなければ、値は実処理に影響しません。
- scheduler の固定予算 `STRATA_IO_PF_BUDGET_MB` が正の値を与える場合、`io_budget_now()` は固定予算を返すため、`io_scale_` の更新は予算を変えません。固定予算がない場合に限り、feedback scale が自動予算へ掛けられます。

## 実行時の詳細

値は `set_io_prefetch()` の呼び出し時に `FileExpertSource` インスタンスへ読み込まれます。生成処理では `--mmap-experts` の経路から prefetch を開始し、成功すると worker thread を起動します。設定をプロセス内で後から変えても、このインスタンスに保存された目標値は再読込されません。

decode が layer 0 に戻る新しい window ごとに `begin_layer()` から `io_window_tick()` が呼ばれます。先読み総 byte 数 `dpf` と、そのうち demand された byte 数 `du` の window 差分から `u = min(1, du / dpf)` を計算します。`dpf` が 0 の window は更新しません。最初の有効 sample はそのまま `io_useful_` となり、次からは `0.8 * 前回値 + 0.2 * u` の EWMA です。

EWMA が目標を下回ると `io_scale_ *= 0.7`（下限 `0.05`）、目標以上では `io_scale_ *= 1.1`（上限 `1.0`）です。これは `STRATA_IO_PF_BUDGET_MB` による固定 budget がない場合に、自動予算 `io_bw_ * worker数 * window時間 * STRATA_IO_PF_BUDGET_FRAC * io_scale_` を変えます。先読み job の採否はこの window budget 等で決まり、通常の demand read はこの予算で制限されません。

この変数専用のログ出力はありません。prefetch の診断出力には先読み byte 数、使用 byte 数、遅延・不採用数、window budget が含まれますが、設定された目標値自体は表示されません。

## 根拠

- `include/strata/core/expert_source.hpp:924-928, 1146-1166` — scored prefetch の条件、初期値 `io_target_ = 0.5`、scale/usefulness の初期状態。
- `src/core/expert_source.cpp:1045-1053` — 固定予算優先と自動予算への scale の適用。
- `src/core/expert_source.cpp:1055-1075` — window 時間・byte 差分、使用率 EWMA、scale の減衰・回復。
- `src/core/expert_source.cpp:1114-1161` — Linux 限定処理、mapped file 条件、各環境変数の読み取りと worker 起動。
- `src/core/expert_source.cpp:3276-3291` — layer 0 への window 切替と feedback 呼び出し。
- `src/core/expert_source.cpp:1814-1818, 2094-2110` — 先読み済み blob が demand されたときの使用 byte 計上。
- `src/program/generate.cpp:5610-5624, 5655-5690, 15430-15438` — `--mmap-experts` の起動経路と実行時 I/O 診断表示。
- `docs/DETAILS.md:297-307` — file tier I/O prefetch の適用条件と動作の概要。`STRATA_IO_PF_TARGET` の具体的な値や性能比較は記載されていない。
