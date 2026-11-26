# `STRATA_RAM_ADAPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の decode 中、VRAM に載らない MoE expert のうち、会話中に使われる expert を resident RAM copy に移し、あまり使われない expert の RAM 上の場所と入れ替える opt-in 上限値です。expert の routing、重み、VRAM tier の選択規則そのものは変えません。環境値は `generate.cpp` の serve decode loop が初めてこの処理に到達したときに一度読みます。(`engine/src/program/generate.cpp:12302-12303,22836-22846`)

同じ `STRATA_RAM_ADAPT` 値でも、`STRATA_RAM_ADAPT2` が無効なら従来の同期置換、有効なら I/O thread に読み込みを先行させる staged 置換になります。後者では `STRATA_RAM_ADAPT` は 1 window あたりの staged promotion 数の上限です。(`engine/src/program/generate.cpp:12333-12349,22847-22922`)

## 値と判定

`std::getenv` で取得し、未設定なら `0`、設定されていれば `std::atoi` の結果を `std::max(0, ...)` で負値から `0` にします。文字列全体の妥当性検査はなく、`atoi` が読む先頭の整数部分が使われます。空文字、`true`、`false`、`0anything` はいずれも `0` となり、`3x` は `3`、`+2` は `2` になります。先頭空白は `atoi` の変換規則に従います。整数変換範囲外の値に対する検査や fallback はありません。(`engine/src/program/generate.cpp:22843-22846`)

| 条件 | unset | 有効値の例 | 無効値の例 |
| --- | --- | --- | --- |
| `STRATA_RAM_ADAPT2` が未設定、空、または `atoi` 結果 0 | 0 | 正の整数。例: `1`, `4`, `3x` | 空文字、`0`, `0anything`, `-1`, `true` |
| `STRATA_RAM_ADAPT2` の `atoi` 結果が非 0 | 0 | 正の整数。例: `1`, `4` | 空文字、`0`, `0anything`, `-1`, `true` |

負数は両方の経路で 0 に clamp されます。上限の clamp はありません。`STRATA_RAM_ADAPT2` は serve 初期化時に `atoi(v) != 0` で別に判定されます。(`engine/src/program/generate.cpp:12333-12349,22843-22849`)

CLI 引数がこの環境値を上書きする処理はありません。`--adapt-every` と `--adapt-swaps` は RAM 適応の別の前提であり、指定値が有効でも適応 tier が無効なら RAM 置換は行われません。serve 経路ではこの二つが正で、全 expert が VRAM に resident ではなく、VRAM cache slot がある場合に usage 表が確保されます。(`engine/src/program/generate.cpp:15001-15002`)

## 有効になる条件

- `--serve` 経路であること。非 serve の generate loop にはこの環境値を読むコードがありません。(`engine/src/program/generate.cpp:12302-12303,22843-22849`)
- `STRATA_RAM_ADAPT` が正の数に変換されること。
- adaptive tier が有効で usage 表があること。serve では `--adapt-every > 0`、`--adapt-swaps > 0`、全 expert が resident ではないこと、VRAM cache slot があることが usage 表の確保条件です。(`engine/src/program/generate.cpp:15001-15002`)
- resident RAM copy が利用可能で `src.complement_ready()` が真であること。置換 API も ready な copy、妥当な layer/expert、対象 expert が copy にない/あることなどを再確認し、条件外なら変更しません。(`engine/src/program/generate.cpp:22847-22849,22920-22922`; `engine/src/core/expert_source.cpp:4934-4945,4956-4966`)
- 最初の window の後で、usage 表が空でなく、adaptive round が pending でないこと。`--adapt-async` を使う場合は job state が `Idle` である必要があります。(`engine/src/program/generate.cpp:22847-22849,22920-22922`)
- multi-GPU、peer tier、remote helper、および `--batch` はこの RAM adaptation branch を無効にします。(`engine/src/program/generate.cpp:22847-22849,22920-22922`)
- OS や GPU 世代による追加判定はこの処理にありません。実行可否は `generate.cpp` と `FileExpertSource` を含む build、および上記 runtime 条件に依存します。(`engine/src/program/generate.cpp:22843-22849`; `engine/src/core/expert_source.cpp:4934-4953`)

## 実行時の詳細

値は decode loop の関数内 `static const int` に保持され、最初に RAM 適応の判定へ到達した時点で初期化されます。以後の request/window では再読込しないため、同一プロセス実行中の環境変更は反映されません。(`engine/src/program/generate.cpp:22843-22846`)

`STRATA_RAM_ADAPT2` が 0 の場合、各 layer について VRAM 外の候補から usage が 2 以上の incoming expert と、resident RAM にあり usage が 0.5 未満の outgoing expert をそれぞれ最大 4 件選び、差が大きい組から置換します。incoming expert の blob が直前の demand read の stage buffer に残っていればそこからコピーし、ファイル読み取りは行いません。そうでなければ `n` は `replace_resident` の file-read 経路を試す呼び出し数を制限します。staged buffer からの置換はこの上限を消費しません。RAM copy の大きさは変わりません。(`engine/src/program/generate.cpp:22920-22956`; `engine/src/core/expert_source.cpp:4934-4953,4956-4980`)

`STRATA_RAM_ADAPT2` が非 0 の場合、同じ「`n > 0`」が staged promotion の総数上限となり、読み込みは source の I/O thread に queue されます。window 境界で読み込み済み promotion を install し、次の候補を stage します。こちらの候補条件と順位付けは異なり、`STRATA_RAM_ADAPT_PROMPT_W > 0` の場合は usage に prompt routing seed を加え、page-cache の tier cost も考慮します。関連する `STRATA_RAM_ADAPT_PROMPT_W`（既定 0.25）、`STRATA_RAM_ADAPT_CACHED_W`（既定 0.15）、`STRATA_RAM_ADAPT_PER_LAYER`（既定 2）、`STRATA_RAM_ADAPT_SKIP_TOP`（既定 2）がこの枝の候補計算を調整します。(`engine/src/program/generate.cpp:12334-12348,22847-22918`)

RAM 置換 API の戻り値は caller でエラー終了に使われません。legacy 枝で `replace_resident_staged` が false の場合は file-read 経路を試し、その読み取りに失敗した場合や置換条件が合わない場合は resident copy を変更せず処理を続けます。ADAPT2 枝で `ram_stage` が false を返した候補も上限数に数えず、fatal error にはなりません。adaptive tier 自体の refill failure は別経路で `ERR an adaptive refill failed` を stdout に出し、serve loop が `1` を返します。(`engine/src/program/generate.cpp:22950-22960`; `engine/src/core/expert_source.cpp:4934-4953,4956-4980`)

## ログと測定値

request 終了時、resident RAM adaptation の累積移動数が 1 件以上なら stderr に次の形式で出ます。2つ目の数は stage buffer から移動した件数です。移動がなければこの行は出ません。(`engine/src/program/generate.cpp:23806-23809`)

```text
strata serve: resident RAM: <n> experts moved in in place of unused ones, <n> of them out of a stage buffer (STRATA_RAM_ADAPT)
```

`docs/DETAILS.md:1670-1671` には旧版・特定構成での測定記録がありますが、この checkout の測定ではありません。現行 HEAD の性能値としては扱いません。`docs/DETAILS.md:277-282` の説明は従来の置換枝に対応し、現行コードにある `STRATA_RAM_ADAPT2` staged 枝とその異なる `n` 上限は説明していません。

## 根拠

- `engine/src/program/generate.cpp:12302-12303` — serve 経路。
- `engine/src/program/generate.cpp:12333-12349` — 関連する `STRATA_RAM_ADAPT2` と tuning 値の読み取り。
- `engine/src/program/generate.cpp:15001-15002` — adaptive usage 表の有効条件。
- `engine/src/program/generate.cpp:22836-22960` — 対象値の読み取り、両置換経路、適用条件、adaptive refill failure。
- `engine/src/program/generate.cpp:23806-23809` — 累積移動ログ。
- `engine/src/core/expert_source.cpp:4934-5004` — file-read / stage-buffer の resident copy 置換、失敗時処理。
- `docs/DETAILS.md:277-282,1670-1671` — 現行実装との照合対象および旧版測定記録。
