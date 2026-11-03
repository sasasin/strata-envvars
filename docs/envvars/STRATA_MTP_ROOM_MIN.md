# `STRATA_MTP_ROOM_MIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の `strata generate --serve` で `--mtp` を使い、MTP drafter が自分で所有する routed expert weights がある場合に、長い prompt の読み込み中だけその weights の VRAM 領域を prompt path の expert ring に貸します。decode 専用の MTP experts を追加 ring slots として使うことで、prompt の読み込み中に使える ring を増やします。prompt の読み込み後、decode が始まる前に元の expert bytes を戻します。既定は無効です。

## 値と判定

値は `std::strtoll(v, &end, 10)` で 10 進整数に変換され、変換後に文字列の終端まで消費したか、値が負でないかを検査します。`errno` による overflow 検査はありません。

| 値 | 判定と動作 |
| --- | --- |
| 未設定または空文字 | `-1` として扱い無効。既定では room を使わない |
| `0` | しきい値 0。読み込む token 数が 0 以上なら対象になり、すべての request が条件を満たす |
| 正の整数 | request が新たに読む prompt token 数がこの値以上なら対象 |
| 負数 | 無効値。stderr に token count ではない旨を出し、終了コード 2 |
| 整数に変換できない文字列、変換後に余分な文字がある値 | 無効値。同じく stderr に出して終了コード 2 |

`strtoll` は先頭空白と符号を受け付けますが、末尾の空白やその他の文字が残ると無効です。`+12` は有効、`12x` と `12 ` は無効です。オーバーフローの errno は検査せず、負の結果だけを拒否します。

`strtoll` の範囲を超える正の入力は戻り値 `LLONG_MAX` がしきい値として使われ、負方向の範囲超過は負の戻り値として無効扱いになります。

## 有効になる条件

- この処理は CUDA の serve/prefill 経路にあります。Metal 経路では prompt buffers が別管理で、同じ expert-cache slot 貸出を行わないようにしています（`src/program/generate.cpp:10484-10492`）。
- 値を設定した場合、`--serve`、`--mtp`、`o.batch <= 0`（`--batch` slot なし）、かつ drafter が貸し出せる自分所有の experts を持つことが必要です。`o.batch > 0` など条件を満たさないと stderr に `STRATA_MTP_ROOM_MIN is unavailable: ...` を出し、終了コード 2 です（`src/program/generate.cpp:10516-10525`）。共有 weights の drafter は `experts_bytes() == 0` になり貸し出せません（`src/core/mtp.cpp:581-585`）。
- `--batch-mtp` は batch slot の drafter が weights を共有する構成のため対象外です（`src/program/generate.cpp:1116-1118,10518-10522`）。
- 適格な起動でも、drafter と同じ CUDA device 上に prompt path がなければ、その request は通常の ring で読みます。stderr に `prompt room: no prompt path runs on CUDA...` と出ます（`src/program/generate.cpp:10624-10649`）。
- しきい値を満たしても、prompt ring の layout が room を追加できる必要があります。room は通常 ring が `STAGE` より大きく base pointer があり、ring cap と貸出 bytes の範囲内の場合だけ設定されます。小さい chunk などで条件に合わなければ、追加 slots はありません（`src/prefill/prefill.cpp:2017-2035`）。
- `STRATA_PREFILL_RING` など prompt ring の設定が既存 ring のサイズを変えるため、room が追加できる slot 数にも影響します（`src/prefill/prefill.cpp:402-424,2028-2035`）。

## 実行時の詳細

環境変数は serve の prompt path 初期化時に一度読みます。読み取り結果はローカルの `const int64_t mtp_room_min` に保持され、request ごとに環境を読み直しません（`src/program/generate.cpp:10503-10510`）。CLI option によるしきい値の上書きはありません。

room の slot 数は `experts_bytes / expert_layout().max_blob` を最大 4096 で制限して計算します。prompt path のうち drafter と同じ device にあるものへ、drafter の experts base と byte 数を渡して layout します（`src/program/generate.cpp:10527-10534,10624-10644`）。Prefill 側は ring cap と貸出 bytes でも slot 数を制限し、room の bytes を別途 allocate せず、そのまま追加 ring slot の backing として指します（`src/prefill/prefill.cpp:2021-2059`）。

各 request では `read_from` を決めた後、`n - read_from` がしきい値以上か判定します。ここで数えるのは prompt 全体でなく、その request が実際に読む token 数です。適合時は `experts_lend()` で experts を pinned host memory に退避してから ring room を active にします。未適合なら room は使いません（`src/program/generate.cpp:16049-16065`）。

貸出が失敗した場合は stderr に `prompt room: <reason>: this prompt reads as it always did` と出し、その request は通常どおり読み込みを続けます。貸出成功後は prompt の refill が済んでから room を inactive にし、`experts_reclaim()` で元の CUDA block に戻します。これは decode の最初の window より前です（`src/program/generate.cpp:15406-15419,17356-17361`）。貸出中の MTP decode entry は experts を読まないよう拒否し、`mtp: the 512 experts are lent to a prompt (STRATA_MTP_ROOM_MIN)` を error にします（`include/strata/core/mtp.hpp:93-99,233-238`）。

起動時には stderr にしきい値、対象 device、experts の MiB 数、追加 slot 数を出します。room の実利用時にも token 数、貸出時間、追加 slots を記録します（`src/program/generate.cpp:10529-10534,16060-16065`）。

`docs/DETAILS.md` は CUDA、`--serve` + `--mtp`、`--batch` なし、既定 OFF と説明しています。また RTX 2060 SUPER および P100 での prompt 性能測定値を記載していますが、これらは資料記載の測定であり、本調査で再測定した値ではありません（`docs/DETAILS.md:1089`）。

## 根拠

- `src/program/generate.cpp:10484-10534` — Metal 経路との区別、値の読み取りと parse、適用条件、slot 数、ログ。
- `src/program/generate.cpp:10610-10649` — drafter device 上の prompt path への room 設定。
- `src/program/generate.cpp:15380-15419,16049-16065,17356-17361` — request ごとの閾値、貸出、失敗時 fallback、prompt 後の返却。
- `src/core/mtp.cpp:581-627` — MTP experts の所有条件、pinned host への snapshot と reclaim。
- `src/prefill/prefill.cpp:402-424,2017-2059,2115-2120` — ring 条件、room slots の cap と backing、active 切替。
- `include/strata/core/mtp.hpp:83-99,233-238` — MTP experts が decode 専用であること、貸出中の decode 拒否。
- `docs/DETAILS.md:1089` — 適用概要と資料記載の測定値。
