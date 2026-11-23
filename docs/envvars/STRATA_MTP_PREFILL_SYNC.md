# `STRATA_MTP_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

MTP ドラフターがプロンプトの K/V を埋める際に、入力を `max_t_` 件ずつホスト側で準備して各 group の処理完了を待つ旧方式を使うか、入力記録をまとめて転送して group ごとにデバイスコピーと graph を投入し最後に待つ方式を使うか選びます。`1` 相当は旧方式、`0` 相当は E-4 のまとめ転送方式です。ソースコメントでは処理順序は同じとされています。この変数が変えるのは prefill の準備・同期方式で、MTP の有効化、draft 数、候補選択を直接設定するものではありません（`engine/src/core/mtp.cpp:1738-1748`、`engine/src/core/mtp.cpp:1807-1829`、`engine/sycl/src/core/mtp.cpp:1456-1473`）。

MTP を使う実行経路で、プロンプト処理側の `Prefill::draft_kv` が処理を引き受けない場合に `MtpDrafter::prefill` が呼ばれます。通常の generate/serve の chunk callback も同じ順で batched 経路を試し、失敗時に MTP prefill へフォールバックします（`engine/src/program/generate.cpp:24031-24043`、`engine/sycl/src/program/generate.cpp:8597-8602`）。また CUDA/HIP の `reserve_prefill` も同じ設定を使い、後続処理に備えて旧方式の graph を捕捉するか、新方式の device-input graph と入力領域を準備するかを選びます（`engine/src/core/mtp.cpp:1700-1724`）。

## 値と判定

環境変数が未設定なら、`STRATA_USE_HIP` が定義されたビルドでは旧方式、それ以外ではまとめ転送方式です。設定されている場合は `std::atoi` の結果が非ゼロかで判定し、文字列全体の厳密な検証はしません。先頭の空白と符号を含む整数接頭辞を変換し、後続文字は無視します。整数として読める数字がない文字列（空文字を含む）は `atoi` が 0 を返すため無効扱いです（`engine/src/core/mtp.cpp:1687-1697`、`engine/sycl/src/core/mtp.cpp:1466-1473`）。

| 条件 | unset | 有効になる値（旧方式） | 無効になる値（まとめ転送方式） |
| --- | --- | --- | --- |
| CUDA/HIP 共通実装、`STRATA_USE_HIP` 定義あり | 旧方式 | `1`, `-1`, `2tail` | `0`, `0anything`, `true`, ``, `   ` |
| CUDA/HIP 共通実装、`STRATA_USE_HIP` 定義なし | まとめ転送方式 | `1`, `-1`, `2tail` | `0`, `0anything`, `true`, ``, `   ` |
| SYCL 実装 | `STRATA_USE_HIP` 定義時は旧方式、未定義時はまとめ転送方式 | `1`, `-1`, `2tail` | `0`, `0anything`, `true`, ``, `   ` |

`atoi("0anything")` は整数接頭辞 `0` を返し、`atoi("2tail")` は `2` を返します。したがって `true` / `false` の文字列、先頭が数字でも 0 の値、数字より前にある文字は有効な真値になりません。正の値・負の値とも 0 以外なら旧方式です。CLI 引数による同じ設定の上書きはこの実装にはなく、この環境変数が設定されていれば backend の既定値に優先します。

## 有効になる条件

- MTP が実行経路で有効であること（通常の generate/serve では MTP ドラフトを使う経路）。候補一覧の名前だけでは MTP 自体は有効になりません（`engine/src/program/generate.cpp:24031-24042`、`engine/sycl/src/program/generate.cpp:8597-8602`）。
- プロンプト K/V の処理が `MtpDrafter::prefill` まで到達すること。`Prefill::draft_kv` が処理した chunk では、この分岐は使われません（`engine/src/program/generate.cpp:24041-24042`、`engine/sycl/src/program/generate.cpp:8600-8602`）。ソースコメントでは MTP ring の KV streaming / `--kv-resident` 時などに `draft_kv` が辞退すると説明されています（`engine/src/core/mtp.cpp:1742-1747`、`engine/sycl/src/core/mtp.cpp:1460-1465`）。
- 変数の選択結果は関数内 `static` に保存されます。`prefill_per_group_sync()`（CUDA/HIP）または `MtpDrafter::prefill`（SYCL）の最初の評価後、同一プロセス内で環境を変更しても反映されません（`engine/src/core/mtp.cpp:1688-1697`、`engine/sycl/src/core/mtp.cpp:1466-1473`）。
- Metal の `MtpDrafter::prefill` は Metal 実装へ直接委譲する compile-time 分岐があり、同関数内のこの設定分岐を通りません（`engine/src/core/mtp.cpp:1727-1732`）。ただし共通ソースの `reserve_prefill` は別途 helper を呼びます。Metal 実行経路からその予約メソッドが呼ばれるかはここで確認した通常 callback からは断定できません。
- `sync` 引数はこの環境変数とは別です。まとめ転送方式で `sync == false` の呼び出しは stream 上の完了待ちをせず戻り、呼び出し元の stream ordering に委ねます。`sync == true` なら処理後に stream/queue 完了を待ちます。旧方式は group ごとに同期します（`engine/src/core/mtp.cpp:1795-1825`、`engine/sycl/src/core/mtp.cpp:1570-1616`、`engine/src/program/generate.cpp:20287-20288`）。

## 実行時の詳細

設定の初回評価後、旧方式では各 group の token / step / position を host 側の mapped 領域に書き、入力と residual row を使った graph を投入して group ごとに stream 同期します。まとめ転送方式では `n` 行分の token / step / position record を組み立てて一括 upload し、`max_t_` 行以下の group ごとに device-to-device copy と graph launch を行い、通常は最後に一度だけ同期します。既に必要な window より古い K/V cell の group はどちらの方式でも処理を飛ばします（`engine/src/core/mtp.cpp:1735-1748`、`engine/src/core/mtp.cpp:1761-1829`、`engine/sycl/src/core/mtp.cpp:1453-1475`、`engine/sycl/src/core/mtp.cpp:1488-1634`）。

予約経路では旧方式は `capture_prefill(T)` を準備し、まとめ転送方式は device input を使う `capture_prefill_dev(T)` を準備します。まとめ転送経路の pinned upload 領域予約に失敗した場合は stderr に `strata mtp: the prompt records' pinned upload slots could not be reserved (they grow at first use)` と出しますが、その失敗だけでは予約を中断せず、初回利用時に領域を増やす経路を続けます（`engine/src/core/mtp.cpp:1700-1724`）。

## ログと測定値

この変数の値を表示する有効化ログや無効値警告は見当たりません。入力領域の確保や upload / graph / 同期で失敗すると `MtpDrafter::prefill` は `false` を返し、たとえば generate の呼び出し元は callback の失敗として扱います。CUDA/HIP では主に `mtp prefill: the input records do not fit`、`mtp prefill: the input records upload failed`、または CUDA エラー文字列を `err` に設定します（`engine/src/core/mtp.cpp:1750-1805`）。SYCL では対応する確保・upload エラーを `err` に設定し、SYCL exception の捕捉箇所は例外文とファイル・行を stderr に出して `exit(1)` します（`engine/sycl/src/core/mtp.cpp:1424-1446`、`engine/sycl/src/core/mtp.cpp:1475-1589`）。

SYCL 実装のコメントは、gfx1201 / ROCm 7.2.4 の R9700 で `--kv-resident`、full IQ3_XXS、32,768-token prompt などを使った混合負荷時にまとめ転送方式が完了しないことがあり、同コメント内の試行では旧方式が 30 回完了し prompt speed に差がなかったと記録しています。これはソースコメントに記載された特定条件の観測であり、この調査で再測定した結果ではありません（`engine/sycl/src/core/mtp.cpp:1460-1465`）。

## 根拠

- `engine/src/core/mtp.cpp:1687-1724` — CUDA/HIP の既定値、helper の cache、予約経路。
- `engine/src/core/mtp.cpp:1727-1829` — MTP prefill の両方式、upload、同期、失敗経路。
- `engine/sycl/src/core/mtp.cpp:1424-1447` — SYCL の予約と exception 処理。
- `engine/sycl/src/core/mtp.cpp:1449-1634` — SYCL の値判定と prefill の両方式。
- `engine/src/program/generate.cpp:24031-24043`、`engine/sycl/src/program/generate.cpp:8597-8602` — MTP prefill の呼び出しと batched 経路からの fallback。
