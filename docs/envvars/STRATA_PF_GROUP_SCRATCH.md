# `STRATA_PF_GROUP_SCRATCH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の prompt prefill における MoE の MMQ 経路で、gate/up 出力 `GU`、SwiGLU 出力 `H`、down 用 q8_1 scratch `Hq` を全 chunk 分ではなく expert group 分の行数で確保します。各 group の計算が終わってから次の group に進み、必要なら group 内の expert を sub-range に分けます。入力量子化 `Xq` は引き続き chunk 全体分です。バッファ量を減らし、同じ借用 VRAM の範囲で大きい prefill chunk を選べる場合があります。実装コメントは、group ごとの処理が chunk 全体用 scratch と同じ積を行い、同じ bit 値になる設計としています（`src/prefill/prefill.cpp:1520-1525,1585-1590,5662-5703`）。

## 値と判定

値は `std::atoi(v) != 0` で判定されます。文字列全体の検証や範囲制限はありません。`atoi` が読む先頭の整数部分が 0 なら無効、0 以外なら有効です。未設定と空文字は無効です。たとえば `1`、`-1`、`1tail` は有効、`0`、`0tail`、`true`、`tail`、空文字は無効です。先頭空白と符号は `atoi` の変換規則に従います。整数範囲外の値について Strata 独自の検査はありません（`src/prefill/prefill.cpp:1526-1528`）。

| 値 | 判定 |
|---|---|
| unset / 空文字 | OFF |
| 先頭から変換した整数が 0（例: `0`, `false`, `abc`） | OFF |
| 先頭から変換した整数が 0 以外（例: `1`, `-1`, `1abc`） | ON 候補 |

CLI 引数による上書きはこの変数の読み取り箇所にはありません。ON 候補でも、以下の適用条件を満たさなければ scratch 縮小は行われません。

## 有効になる条件

ソースと `docs/DETAILS.md` が示す対象は CUDA の prompt path です。有効値に加えて、prompt の expert plan で全層が通常の MMQ 経路を取る必要があります。MMQ が build されて有効でなければならず（`STRATA_PREFILL_MMQ` が未設定または `atoi` で非 0）、形式・層の組み合わせにより FP16 fallback や WMMA 専用層があっても対象外です。また、`STRATA_MMQ_DIRECT` により resident expert を直接読む層がある場合も無効です（`src/prefill/prefill.cpp:1445-1475,1479-1499,1518-1540`）。

条件を満たさないときは従来の scratch 配置を使い、stderr に次の形式で理由を出します（変数が ON 候補の場合のみ）。

`strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: <reason>`

理由は `the prompt path runs the FP16 path or pf_wmma here, not MMQ`、`a layer does not take MMQ`、または `STRATA_MMQ_DIRECT is on for a layer (its guard tables are per whole group)` です（`src/prefill/prefill.cpp:1529-1538`）。

## 実行時の詳細

設定値は `pf_group_scratch()` が初めて呼ばれた時点で `static const bool` に保存され、適用条件の判定も別の static 値として一度だけ行います。最初の呼び出しは prefill バッファサイズ算出（`Prefill::bytes_needed_impl` → `moe_set_bytes` → `moe_bufs`）からも起こります。そのため、プロセス起動後でも初回判定より前の環境値が使われ、判定後に環境を変更しても再評価されません（`src/prefill/prefill.cpp:1526-1540,1585-1590,1597-1600,2757-2795`）。

適用時の group scratch 行数 `group_cap` は、`STRATA_PF_GROUP_CAP` が `atoll` で正数に変換される場合は `max(その値, chunk の token 数 T)`、それ以外は `T + 3 × group 平均行数` を 64 行単位に切り上げた値です。`STRATA_PF_GROUP_CAP` はテスト用の容量調整であり、この変数の有効化自体は行いません（`src/prefill/prefill.cpp:1544-1550`）。

各 16 expert の group が cap 以下ならまとめて処理し、超える場合は cap 内に収まる連続 expert sub-range に分割します。`GU` / `H` / `Hq` の割り当てサイズと down 計算が sub-range の行数を使い、bound table には sub-range 用の相対 bounds を追加します（`src/prefill/prefill.cpp:1585-1590,5037-5058,5662-5703`）。レイアウトが適用されたときは stderr に `strata prefill: chunk <T> tokens: STRATA_PF_GROUP_SCRATCH on (GU/H/Hq hold <cap> rows, not <T*K>);` を出します（`src/prefill/prefill.cpp:2064-2070`）。

実行中の防御チェックとして、層が fused/FP16 経路に入った場合は `prefill: STRATA_PF_GROUP_SCRATCH needs MMQ on every layer (a layer took the fused or FP16 path)` を `err` に設定して処理を失敗させます。sub-range の bounds table が確保上限を超えた場合、または実際の range が cap を超えた場合にも、それぞれ `STRATA_PF_GROUP_SCRATCH's bounds table overflowed`、`STRATA_PF_GROUP_SCRATCH: a range of ... rows passes the scratch's ...` を `err` に設定して prefill を失敗させます。`Prefill::run` は失敗を呼び出し元へ返し、generate 経路では stderr に `strata generate: <err>` を出して status 1 で終了します（`src/prefill/prefill.cpp:4542-4545,5055-5058,5671-5677,7738-7746`; `src/program/generate.cpp:19366-19369`）。

`docs/DETAILS.md` は `STRATA_PF_GROUP_SCRATCH=1` と `STRATA_PF_HC_REGION=1` をまとめた説明として、借用 cache slot を 0.3–0.5 GiB 空けた例と、エミュレートした 8 GB card で `STRATA_PREFILL_CPU_SHARE=0` の場合に限って観測した +7〜+11% の prompt 速度を記載しています。これは二つの switch を併用した記載であり、この環境変数単独の測定値としては扱えません（`docs/DETAILS.md:1087`）。

## 根拠

- 読み取り・値判定・条件判定・理由ログ: `src/prefill/prefill.cpp:1520-1540`。
- MMQ plan と層ごとの backend 判定、direct 経路: `src/prefill/prefill.cpp:1445-1499`。
- scratch サイズ、行 cap と bounds の計算: `src/prefill/prefill.cpp:1544-1555,1585-1600,2757-2800,5037-5058`。
- 実行時の適用ログ、MMQ group/sub-range 処理、失敗経路: `src/prefill/prefill.cpp:2064-2070,4542-4545,5662-5707,7738-7746`; generate の stderr と終了 status: `src/program/generate.cpp:19366-19369`。
- 併用設定と条件付き測定の記述: `docs/DETAILS.md:1087`。
