# `STRATA_ATTN_PRE75_SLOTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_ATTN_PRE75_SLOTS` は、pre-sm_75 CUDA / gfx103x HIP attention が選ばれているときに、複数 slot または複数 row をまとめて処理する attention kernel を許可するスイッチです。`1` にしても pre75 kernel 自体を選択する条件は変わりません。pre75 kernel が有効でない場合は、この変数だけでは通常の batched kernel の選択を変えません。実装は `engine/src/kernels/cuda/qsa_decode_attn.cu` の `pre75_slots_on()` と `qsa_decode_attn_slots()` / `qsa_decode_attn_batch_rows()` です（同ファイル: 978-990, 1150-1173, 1227-1285）。

## 値と判定

初回に `pre75_slots_on()` が呼ばれたとき、関数内 `static const bool` の初期化で一度だけ読みます。変数が設定されていれば `std::atoi(value) != 0` の結果を使い、設定されていない場合に限り `STRATA_BATCH_QSA_STREAM_OPT` を同じ `atoi(...) != 0` で判定します。したがって空文字や数値に変換できない文字列は `0` 扱いとなり、明示された `STRATA_ATTN_PRE75_SLOTS` はその結果が `0` でも fallback を上書きします（同ファイル: 981-989）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / 対象 HIP build で `pre75_slots_on()` に到達 | `STRATA_BATCH_QSA_STREAM_OPT` が未設定または `atoi` 結果 0 なら OFF。fallback の同変数が非 0 なら ON | `atoi` 結果が非 0。例: `1`, `-1`, `2`, `1anything` | `atoi` 結果が 0。例: `0`, `0anything`, 空文字, `true`, `false` |

文字列全体の妥当性検査はなく、`atoi` の数値変換に従います。たとえば先頭の空白や符号の後の整数は変換され、数字以外から始まる値や空文字は 0 になります。値の範囲チェックや clamp はありません。設定済みの対象変数が `0` 相当なら fallback は参照されず OFF です（同ファイル: 981-989）。

## 有効になる条件

- `STRATA_ATTN_PRE75_BUILT` が定義された build が対象です。このファイルでは CUDA なら定義され、HIP では通常 `STRATA_HIP_GFX906` でない buildで定義されます。`STRATA_EXPERIMENTAL_SM60` が定義されていれば gfx906 HIP build でも定義されますが、その場合も `qsa_decode_attn_batch_rows()` は gfx906 で multi-row kernel を使わず row ごとに処理します（同ファイル: 503-505, 1259-1264）。
- `pre75_attn()` が true である必要があります。関連する `STRATA_ATTN_PRE75` は先頭文字だけを見て、`0` なら無効、`1` なら明示値 1、それ以外や未設定なら自動判定です。通常の CUDA build では 0 が無効化し、それ以外は `daily_attn()` の結果に従います。`STRATA_ATTN_DAILY` が正確に文字列 `1` なら有効、未設定なら対応する sm12x device で既定有効、それ以外の設定値なら既定判定を使わず無効です。experimental SM60 CUDA build では sm_75 未満の device、または `STRATA_ATTN_DAILY=1` が条件です。HIP の対象 build では gfx103x device、または `STRATA_ATTN_PRE75=1` が条件です。HIP では `daily_attn()` が常に false を返すため、`STRATA_ATTN_DAILY` による有効化はありません。device 属性の取得失敗時は false になります（同ファイル: 902-923, 926-964）。
- `qsa_decode_attn_slots()` では `STRATA_ATTN_LANECELL` が `'1'` で始まる値だと lane-cell kernel が優先し、pre75 slots 判定を行いません（同ファイル: 993-996, 1166-1173）。
- `qsa_decode_attn_batch_rows()` では、pool の page table 欠落または KV mode の不一致で `per_row` になる場合、pre75 multi-row 経路を使いません。HIP gfx906 は常に `per_row` にし、pre75 multi-row を無効にします（同ファイル: 1245-1264）。
- `qsa_decode_attn_slots()` は `n_q <= 0`、slot 数上限超過、pool の KV mode 不一致などで別の戻り方をします。環境変数が有効でも、呼び出し側の geometry・buffer 条件が満たされる必要があります（同ファイル: 1150-1173）。

## 実行時の詳細

値を読むのは初回の `pre75_slots_on()` 呼び出しであり、読み取り結果はプロセス内に cache されます。関数内 static のため、プロセス起動後に環境を変更しても、その初回評価後は反映されません。`qsa_decode_attn_slots()` は pre75 attention が有効で lane-cell が無効なとき、このスイッチが OFF なら `false` を返して kernel を起動せず、ON なら pre75 slots kernel を選びます。ON の場合は CUDA で `attn_chunk_slots_pre75_kernel`（2 cells）、HIP で同 kernel（8 cells、DPP）を KV mode ごとに起動します（同ファイル: 1150-1173, 1188-1200）。

`qsa_decode_attn_batch_rows()` は pre75 attention が有効な場合、スイッチが ON なら pre75 rows kernel を選び、OFF なら row ごとに `qsa_decode_attn_batch()` を呼びます。pre75 attention が無効なら本変数の判定を使わず、通常の rows kernel を使います（同ファイル: 1227-1285）。これらの経路は verify の batch window から呼ばれます。MTP では `qsa_decode_attn_slots()` を試し、拒否された場合に row ごとの `qsa_decode_attn_batch()` へ fallback します（`engine/src/core/verify.cpp:2435-2447, 2485-2497`; `engine/src/core/mtp.cpp:2481-2499`）。

## ログと測定値

この変数を有効・無効にしたことを示す専用ログはありません。`qsa_decode_attn_slots()` が条件不成立で `false` を返す経路も、その関数内では警告せず、上記呼び出し元などが通常の row ごとの attention に切り替えます。カーネル実行時に geometry や buffer が不正なら `qsa_decode_attn_slots: ...` / `qsa_decode_attn_batch_rows: ...` を stderr に出して終了し、launch error も同様に stderr に出して終了します（同ファイル: 1154-1165, 1219-1223, 1231-1234, 1297-1300）。この変数による速度・正確性の測定値は、対象資料で条件付きに確認できません。

## 根拠

- 変数の読み取り、優先順位、`atoi` 判定、cache: `engine/src/kernels/cuda/qsa_decode_attn.cu:978-990`
- build 条件と pre75 kernel の選択条件: `engine/src/kernels/cuda/qsa_decode_attn.cu:503-505, 926-964`
- slot / row kernel の選択・fallback: `engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1224, 1227-1301`
- verify と MTP からの呼び出し: `engine/src/core/verify.cpp:2435-2447, 2485-2497`; `engine/src/core/mtp.cpp:2481-2499`
