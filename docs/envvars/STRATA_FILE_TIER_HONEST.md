# `STRATA_FILE_TIER_HONEST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux で file tier の buffered / unbuffered I/O を選ぶとき、page cache に使えるメモリ量の見積もりを保守的にする。既定では `strata::core::sample_host_memory` の `available` も読み、先に得た `available_memory_bytes` の値より小さい場合に限って小さい方を選ぶ。`=0` はこの追加サンプルを無効にする。変わるのは `file_cache_keeps` に渡す空き容量の見積もりであり、モデルの重みや expert の選択内容を変える分岐ではない。実装は `file_tier_unbuffered` にあり、呼び出し元は `FileExpertSource::set_unbuffered` と `FileExpertSource::recheck_unbuffered`（`engine/src/core/expert_source.cpp:959-1039,2842-2858,2867-2889`）。

## 値と判定

Linux 分岐で `std::getenv` の結果を調べ、未設定の場合または先頭文字が `'0'` でない場合に有効となる。文字列全体の parse や真偽値変換はしない。従って空文字は有効、`0` と `0anything` は無効、`1`・`true`・`false`・`anything`・先頭空白のある ` 0` はいずれも有効。無効値エラーや値の clamp はない。Windows と Linux 以外ではこの環境変数を判定しない（`engine/src/core/expert_source.cpp:963-987,1034-1038`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux の file-tier 判定 | サンプルを使う | 空文字、`1`、`true`、`false`、` 0` | 先頭が `0` の任意の文字列（`0`、`0anything`） |
| Windows / その他の OS | この変数を読まない | 該当なし | 該当なし |

## 有効になる条件

- `--mmap-experts` 等で mmap の expert source を使い、かつ `--resident-budget-gib` 相当の resident budget が正か `--ssd-experts` が有効であること。これらの場合に起動時の `set_unbuffered` が呼ばれる。resident budget がなく `--ssd-experts` でもない場合、この判定は行われない（`engine/src/program/generate.cpp:8621-8628,8654-8658`）。
- `--ssd-experts` は `force` 経路で direct open を行うため、この変数の判定を通らない（`engine/src/core/expert_source.cpp:2842-2858`）。
- Linux で `STRATA_UNBUFFERED_LOAD` が空でない値に設定されていると、そちらを先に判定して戻るため、この変数は読まれない。`STRATA_UNBUFFERED_LOAD` の先頭が `'0'` なら buffered、それ以外なら unbuffered を選ぶ（`engine/src/core/expert_source.cpp:963-972`）。
- RAM copy の構築後に再判定されるのは、Linux / Windows で mmap source と正の resident budget を使い、Windows の startup unbuffered 処理が保持されていない場合。Linux では `recheck_unbuffered` も同じ file-tier 判定を呼び、変数を再読する（`engine/src/program/generate.cpp:12219-12229`, `engine/src/core/expert_source.cpp:2867-2889`）。
- `STRATA_FILE_CACHE_OLD_RULE` が有効な場合もメモリ見積もりのサンプル自体は適用され、その後の容量判定方式が切り替わる。`STRATA_FILE_TIER_PROBE` が先頭 `'0'` 以外なら probe を止めず、keepable とされたとき容量条件次第で実測 probe が最終的な buffered / unbuffered 選択に関与する（`engine/src/core/expert_source.cpp:985-1033`）。
- Windows は `experts_unbuffered` 経路、Linux 以外は「no unbuffered reads on this platform」の経路で、この変数によるサンプル補正をしない（`engine/src/core/expert_source.cpp:963-967,1034-1038`）。ソースの設定レジストリでは backend は `cuda-hip` と記載されている（`terminal/data/settings-register.json:9269-9279`）。

## 実行時の詳細

Linux ではまず `available_memory_bytes` を取得し、失敗した場合は理由を `the available RAM is unknown` として buffered 側（戻り値 `false`）に進むため、環境変数の読み取りにも到達しない。取得できた場合、既定 ON の追加サンプルは `sample_host_memory(MemoryProbePaths{}, 0)` を呼ぶ。このサンプルが得られ、かつ `honest->available < avail` の場合だけ `avail` を小さくする。サンプルが得られない、または値が同じか大きい場合は何も変更しない（`engine/src/core/expert_source.cpp:973-987`; サンプル実装 `engine/src/core/conversation_memory.cpp:378-409`）。

調整後の `avail`、RAM copy の予定量 `arena_bytes`、ファイルから読む expert 量 `read_bytes` を `file_cache_keeps` に渡し、file cache が再利用対象を保持できるかを判定する。通常ルールでは 1 GiB の余裕、5% の比率、512 MiB の下限引数を使う。容量判定後も条件を満たす場合、`STRATA_FILE_TIER_PROBE` による drive probe が cached / direct の選択に加わる（`engine/src/core/expert_source.cpp:988-1033`）。

環境変数は関数内 `static` に cache されず、`set_unbuffered` と `recheck_unbuffered` の各呼び出しで評価される。初回判定はモデル起動時、再判定は RAM copy 構築後であり、プロセス実行中に環境を変更すれば後者には反映される。ただし、`STRATA_UNBUFFERED_LOAD` の非空値がある再判定ではそちらが優先する（`engine/src/core/expert_source.cpp:963-987,2842-2889`; 呼び出し箇所 `engine/src/program/generate.cpp:8654-8658,12224-12229`）。

## ログと測定値

この変数専用の警告・エラー・ログはない。起動時に `strata generate: the file tier reads unbuffered (...)` または `strata generate: the file tier reads through the file cache (...)` が判定結果と理由を stderr に出す。RAM copy 後の再判定では `strata generate: the file tier reads ...` の行に、選択変更時は `(changed)` が付く。Linux の容量判定理由には利用可能 GiB、RAM copy の予定量、expert 読み取り量、および cache が再利用対象を保持できるかが含まれ、probe が実行されれば速度の比較も付く（`engine/src/program/generate.cpp:8654-8658,12224-12229`; `engine/src/core/expert_source.cpp:1003-1031`）。

`docs/DETAILS.md` の「Linux file tier」は file tier の prefetch 等を説明しているが、この環境変数についての記載はない（`docs/DETAILS.md:302-351`）。ここではソースから確認できた選択ロジックのみを記載し、性能値は加えていない。

## 根拠

- `engine/src/core/expert_source.cpp:959-1039` — OS 分岐、優先する環境変数、値判定、メモリ補正、容量判定と probe。
- `engine/src/core/expert_source.cpp:2842-2858,2867-2889` — 初回判定と RAM copy 後の再判定。
- `engine/src/core/conversation_memory.cpp:378-409` — 追加サンプルが読む値と取得失敗時の扱い。
- `engine/src/program/generate.cpp:8621-8658,12219-12229` — CLI / 実行経路の条件と観測ログ。
- `terminal/data/settings-register.json:9269-9279` — 設定レジストリ上の backend 分類。
- `docs/DETAILS.md:302-351` — 関連する Linux file-tier 説明との照合。
