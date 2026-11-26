# `STRATA_LOOKAHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ルーター予測による expert source の先読みを無効化するスイッチです。既定では、条件を満たすと CPU 側の予測スレッドが次の層のルーターで expert を予測し、ファイル層のページを先に暖めます。Foresight swap が有効な CUDA/HIP 経路では予測を swap space にも渡します。予測結果は先読み対象を決めるだけで、実際に計算する expert や生成結果を変更しません（`engine/src/program/generate.cpp:10292-10303`, `engine/src/core/expert_source.cpp:319-323, 3789-3792`）。

CUDA/HIP の生成経路と SYCL の生成経路がこの名前を直接読みます。CPU 専用経路での読み取りはありません。設定は CLI 引数ではなく、実行プロセスの環境から取得します（`engine/src/program/generate.cpp:10288-10303`, `engine/sycl/src/program/generate.cpp:5788-5793`）。

## 値と判定

両経路とも `std::getenv` の結果を `std::atoi` に渡し、文字列全体の妥当性検証はしません。未設定は有効扱い、設定済みなら `atoi(value) != 0` のときだけ有効です。空文字は `atoi("") == 0` なので無効です。先頭の空白と符号は `atoi` の通常の変換に従い、数値に続く文字列は検査されません（例: `"1junk"` は有効、`"0junk"` は無効）。`true`、`false`、`yes` は先頭が数値でないため 0 となり無効です。値の大文字小文字は関係しません（`engine/src/program/generate.cpp:10288-10303`, `engine/sycl/src/program/generate.cpp:5792`）。

| 経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP | 0（既定で許可） | `1`, `-1`, `1junk`, ` 1` | 空文字, `0`, `0junk`, `true` |
| SYCL | 0（既定で許可） | `1`, `-1`, `1junk`, ` 1` | 空文字, `0`, `0junk`, `true` |

数値として変換できる上限・下限は Strata 側で検証していません。範囲外の文字列を `atoi` に渡した場合の結果は、この実装から保証できません。

## 有効になる条件

- **CUDA/HIP:** `srcp` が存在し、かつ (a) 既定の `src` が `warms()` を返す、(b) `STRATA_FS_SLOTS` が `atoi` で正数かつ `STRATA_FS_AHEAD` が未設定または非 0、(c) `STRATA_LOOKAHEAD_STATS` が非 0、のいずれかが必要です。さらに `STRATA_LOOKAHEAD` 自身が未設定または非 0 でなければ起動しません（`engine/src/program/generate.cpp:10298-10303`）。
- 通常のファイル source が `warms()` を返すのは、マップした role があるか I/O prefetch が有効で、かつ unbuffered direct source ではない場合です（`engine/include/strata/core/expert_source.hpp:992-1001`）。予測器の `start` は source が warm しない場合には通常失敗しますが、Foresight 先読みまたは統計計測が有効な CUDA/HIP 経路は cold source を許可します（`engine/src/core/expert_source.cpp:3534-3544`）。
- CUDA/HIP では `STRATA_IO_PREFETCH` が非空かつ `atoi` 非 0 なら、全 expert が GPU cache にある場合にも予測を接続する意思表示 `la_asked` になります。これは `STRATA_LOOKAHEAD` の無効指定を覆しません。`STRATA_LOOKAHEAD=0` なら予測器は起動しません（`engine/src/program/generate.cpp:10288-10290, 10302-10303`）。
- CUDA/HIP では全 expert が GPU cache にあり、かつ `STRATA_LOOKAHEAD` / `STRATA_IO_PREFETCH` のどちらも有効指定でなく、Foresight と統計計測も使わない場合、予測器が初期化されても `drive.d.lookahead` には接続されません。`STRATA_LOOKAHEAD=1` はその状態でも接続を保ちます（`engine/src/program/generate.cpp:10275-10287, 10327-10333`）。
- `STRATA_LOOKAHEAD_K` は予測する expert 数を指定し、未設定なら 10 です。`RouterLookahead::start` は 1 未満を 1、expert 数超を expert 数に clamp します。`STRATA_IO_PREFETCH_DEPTH` が正数なら先読み層数を設定し、`RouterLookahead::set_depth` が 1〜4 に clamp します。未設定または非正数の場合、CUDA/HIP の I/O prefetch または `--ssd-experts` では深さ 2、それ以外は既定の 1 です。SYCL では `STRATA_LOOKAHEAD_K` を読みますが深さは既定の 1 のままです（`engine/src/program/generate.cpp:10319-10326`, `engine/sycl/src/program/generate.cpp:5806-5809`, `engine/src/core/expert_source.cpp:3543`, `engine/include/strata/core/expert_source.hpp:341-344`）。
- SYCL は `srcp == &src && src.warms()` のときだけこの環境変数を評価して起動します。そこでは `STRATA_IO_PREFETCH`, `STRATA_FS_SLOTS`, `STRATA_FS_AHEAD`, `STRATA_LOOKAHEAD_STATS` による代替起動条件はありません（`engine/sycl/src/program/generate.cpp:5791-5793`）。

## 実行時の詳細

CUDA/HIP 経路はこの生成実行の look-ahead setup 時に環境値を読みます。値を static cache には保存しませんが、同じ `RouterLookahead` の生存中に再読込はしません。予測器を起動すると、各層の BF16 ルーターを GPU からホストへコピーして専用スレッドを開始します。ルーターが BF16 でない、必要なコピーに失敗する、または `RouterLookahead::start` が失敗する場合は予測器を使わず、理由を stderr に出して処理を続けます（`engine/src/program/generate.cpp:10302-10320, 10334-10338`, `engine/src/core/expert_source.cpp:3534-3551`）。

dispatch は層の MoE 入力を予測スレッドに送ります。スレッドは次層のルーターを適用し、GPU resident expert を除外した予測先を `warm` または `warm_scored` に渡します。FileExpertSource は RAM copy にある expert を除外し、条件に応じて I/O thread に先読みを enqueue するか、Windows では `PrefetchVirtualMemory`、それ以外では `madvise(MADV_WILLNEED)` を呼びます。これは Strata が行う先読み要求までの説明であり、OS やストレージの実際の読み込み完了時期は保証しません（`engine/src/core/expert_source.cpp:3467-3506, 3670-3705, 3740-3792`, `engine/src/core/expert_source.cpp:5436-5442`）。

この読み取り値自体は起動後に再読込されません。ただし CUDA/HIP の cache-residency policy は request start や VRAM resize 時に別途 cache 状態を再確認し、全 expert が常駐していたため外した予測器を再接続する場合があります。環境変数の値を変更しても、実行中プロセスに新しい値は反映されません（`engine/src/program/generate.cpp:10255-10257, 10341-10377`）。

## ログと測定値

CUDA/HIP で予測器が接続されると `strata generate: routing-aware prefetch on (the next layer's router, file tier)`、Foresight 使用時は `strata generate: routing-aware prefetch on (the next layer's router, feeding the Foresight swap space)` を stderr に出します。GPU cache が全 expert を保持し、先読みの明示指定がない場合は `strata generate: routing-aware prefetch off (every expert is in the GPU caches; STRATA_LOOKAHEAD=1 runs it)` を出します。router の型が条件に合わない場合は `strata generate: routing-aware prefetch off (the routers are not BF16 in the arena)`、その他の起動失敗時はエラー文字列を括弧内に出します（`engine/src/program/generate.cpp:10327-10338`）。

SYCL の有効ログは `strata generate: routing-aware prefetch of the file tier on (the next layer's router)` です。router 型が違う場合または初期化が失敗した場合は `strata generate: routing-aware prefetch off (...)` を出します（`engine/sycl/src/program/generate.cpp:5806-5819`）。この環境変数に紐づく測定値はここでは記載しません。

## 根拠

- `engine/src/program/generate.cpp:10288-10338` — CUDA/HIP での値判定、起動条件、深さ設定、ログ。
- `engine/sycl/src/program/generate.cpp:5788-5819` — SYCL での値判定、起動条件、ログ。
- `engine/include/strata/core/expert_source.hpp:319-344, 992-1001` — 予測器と source の warm 条件。
- `engine/src/core/expert_source.cpp:3467-3506, 3534-3551, 3670-3792, 5436-5442` — source への先読みと dispatch からの利用。
- `docs/DETAILS.md:302-318` — file tier と cache residency による既定動作の説明。
