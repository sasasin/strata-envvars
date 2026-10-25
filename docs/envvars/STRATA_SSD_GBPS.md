# `STRATA_SSD_GBPS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt planner がファイル tier から expert ファイルを読む速度として仮定する値を、GB/s 単位で指定します。planner は候補 chunk/ring ごとの予測 prompt 時間を比較するため、この値は候補選択に使われます。実測速度を変更したり、I/O 自体を制限したりする変数ではありません。

## 値と判定

`drive_read_gbps()` は `std::getenv()` で変数を読み、`std::atof(e) > 0.0` の場合だけ採用します。条件を満たすと `why` に `STRATA_SSD_GBPS` を設定し、`atof()` の結果を返します。文字列全体の妥当性検査はありません。

| 値 | 扱い |
|---|---|
| 未設定 | 自動推定値を使う |
| 空文字、`0`、負数、数値に変換できない文字列 | `atof()` が正数にならないため自動推定値を使う |
| 正数（例 `0.45`, `2.5`） | その数値を GB/s として採用 |
| 数値の後ろに文字がある場合（例 `2.5junk`） | `atof()` が先頭の数値部分を変換し、正数なら採用 |

空白や指数表記などの変換規則も `atof()` に従います。上限 clamp はありません。正の無限大を返す入力も `> 0.0` を満たして採用され得ます。`why` は planner の入力ログに表示される出所ラベルです。

## 有効になる条件

この値が使われるのは `host_plan_chunk()` が呼び出され、planner が早期 return しない場合だけです。少なくとも次の条件が必要です。

- `--prefill-auto` が有効で、chunk が正。
- `srcp == &src` である。
- `STRATA_PREFILL_HOST_PLAN` が `0` で始まる値ではない（未設定を含む）。
- prefill ring bytes が有効。
- GPU cache に全 expert が収まらず、host memory のサンプルが得られる。

この helper は Linux と Windows の両方の実行経路から呼ばれます。ただし Windows は file tier を unbuffered で読むため page cache が 0 として扱われ、`docs/DETAILS.md` は planner が既存 chunk を維持すると説明しています。`STRATA_SSD_GBPS` を指定してもその経路で chunk を変える保証はありません。

## 実行時の詳細

値は `drive_read_gbps()` が呼ばれるたびに評価され、static cache されません。helper は GPU prefill 側と resident host 側の prompt 処理から呼ばれます。各呼び出しでは `o.native_preset` が空なら `o.pack`、そうでなければ `o.native_preset` を drive 判定の path として渡します。

正の override がない場合、Linux では path の device 情報を sysfs から調べ、rotational disk は `0.15`、NVMe は `2.5`、その他の非回転 disk は SATA-class と仮定して `0.45` GB/s を使います。device を判定できない場合と Windows では `1.5` GB/s を使います。これらは planner の仮定値です。

planner は予測時間の読み込み項を `read_bytes / (ssd_gbps * 1e9)` として計算し、最小予測時間の候補を選びます。出力には `drive %.2f GB/s (%s)` として採用値と出所が stderr に表示されます。変数自体の値を読み取ったときに専用の警告やエラーを出す処理はありません。

## 根拠

- `src/program/generate.cpp:1365-1380` — override の `getenv` / `atof` 判定、Linux の device 推定値と fallback。
- `src/program/generate.cpp:1316-1334` — Linux で path の device と rotational 属性を調べる処理。
- `src/program/generate.cpp:7651-7670` — planner の早期 return 条件、drive 速度の設定、別変数 `STRATA_PREFILL_PLAN_TOKS` の読み取り。
- `src/program/generate.cpp:7719-7727` — 候補選択と planner 入力の stderr 表示。
- `src/program/generate.cpp:8475-8494,15555-15571` — GPU prefill および resident host 経路からの呼び出し。
- `include/strata/program/prefill_plan.hpp:81-98` — SSD 速度を含む予測時間の計算。
- `docs/DETAILS.md:1943-1958` — planner の適用範囲、Windows の unbuffered 経路、関連変数についての説明。
