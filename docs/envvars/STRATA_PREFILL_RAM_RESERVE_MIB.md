# `STRATA_PREFILL_RAM_RESERVE_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、拡張された prompt chunk の RAM ガードが空き RAM に残す予約量を MiB で上書きする。予約量を増減するだけで、chunk の上限を直接指定する変数ではない。空き RAM が resident expert の必要量・追加で借りる GPU cache slot の RAM 量・予約量の合計を下回る場合、Strata は自動 chunk 上限を 32768 → 16384 → 8192 の順に下げる。対象の計算は `generate.cpp` の prefill 計画処理で行われる（`engine/src/program/generate.cpp:11182-11222`）。

## 値と判定

`prefill_ram_reserve_mib` は `std::getenv` の結果を `std::strtoll(..., 10)` で変換し、少なくとも 1 文字を変換でき、変換後に文字列末尾へ達し、値が 0 以上なら MiB 値として採用する。未設定・空文字・不正文字列・負値は既定値へ戻る。末尾に空白や文字が残る値（例: `"2048 "`, `"0anything"`）は全体を消費しないため無効。先頭空白や符号は `strtoll` が受理し得る。正の `long long` 範囲を超える数値は `strtoll` の戻り値が `LLONG_MAX` となり、errno を確認していないため受理される。既定値は `--resident-experts` 相当の `o.resident_cpu_experts` が真なら 6144 MiB、偽なら 3072 MiB（`engine/include/strata/core/gfx12_chunk.hpp:24-35`）。

| 条件 | unset / 空文字 / 無効値 | 有効になる値 | 例 |
|---|---|---|---|
| `o.prefill_gfx12_16k` が真で RAM ガードが評価されるとき | resident experts 有効なら 6144 MiB、無効なら 3072 MiB | 10 進 `long long` として全体を読み切れた 0 以上の数値 | `"0"` は 0、`"2048"` は 2048、`"+5"` は 5。`""`, `"bad"`, `"-1"`, `"0anything"`, `"2048 "` は既定値 |

設定値に clamp はない。なお、`STRATA_PREFILL_RAM_RESERVE_MIB` が正しく読めても、この変数単独で chunk guard が有効になるわけではない（次節）。

## 有効になる条件

- この値を使う RAM guard は、`o.prefill_gfx12_16k` が真で、`auto_ceiling` が 8192 より大きいときに限り反復する（`engine/src/program/generate.cpp:11170-11190`）。主な設定経路は bare `--prefill auto`。
- CUDA の NVIDIA 経路では、bare `--prefill auto` かつ `--prefill` の `auto:N` でも `STRATA_PREFILL_AUTO_MAX` でもない場合に、対応する compute capability と `STRATA_NV_CHUNK` の判定で拡張上限を設定する（`engine/src/program/generate.cpp:4489-4520`）。AMD HIP の Linux 経路では同じ bare auto 条件で gfx12 または discrete RDNA3 gfx11 を検出して設定する（`engine/src/program/generate.cpp:4532-4564`）。Windows HIP では明示的な `STRATA_GFX11_CHUNK` を使った bare auto の gfx11 経路が対象（`engine/src/program/generate.cpp:4568-4587`）。
- 明示的な `--prefill N`、`--prefill auto:N`、または `STRATA_PREFILL_AUTO_MAX` により bare auto でなくなった経路は、この拡張上限と guard を有効化しない。引数処理では `auto:N` と環境変数の値を上限へ変換し、bare auto かどうかを別に記録する（`engine/src/program/generate.cpp:3995-4016`）。
- layer split で `multi_gpu` が真の場合、`STRATA_SPLIT_CHUNK16K` が整数変換後に 0 なら上限を 8192 へ戻すため、guard のループへ入らない。非ゼロ値なら拡張上限が残る（`engine/src/program/generate.cpp:11171-11189`）。
- 各候補で空き RAM `avail_mib` が 0 の場合は比較を行わず、また `STRATA_NV_CHUNK` / `STRATA_GFX11_CHUNK` / `STRATA_GFX12_CHUNK` のうち該当する名前が文字列全体で `"1"` の場合は不足判定を無視する（`engine/src/program/generate.cpp:11189-11210`）。この強制値は予約量の parse 結果を変えない。
- `--resident-experts` などで `o.resident_cpu_experts` が真なら、未キャッシュ expert と 8192 chunk 分の loan を含む `pin_mib` が比較に加わる。偽なら `pin_mib` は 0（`engine/src/program/generate.cpp:11198-11208`）。
- `--memory-limit-mib` または `STRATA_MEMORY_LIMIT_MIB` は RAM sample の算定に影響する別設定で、本変数の値を上書きしない。`--memory-limit-mib` が指定されている場合はそれが優先され、未指定時にだけ `STRATA_MEMORY_LIMIT_MIB` を読む（`engine/src/program/generate.cpp:4083-4102`, `4724-4737`; sample への適用は `engine/src/core/conversation_memory.cpp:411-423`）。

## 実行時の詳細

RAM guard は候補 chunk ごとに expert cache から追加で借りる slot 数を算出し、その slot の RAM 量 `extra_mib`、resident expert の必要量 `pin_mib`、本変数から得た予約量を、Strata が取得した空き RAM `avail_mib` と比較する。`avail_mib > 0 && avail_mib < pin_mib + extra_mib + ram_reserve_mib` なら、強制 chunk 値が `"1"` でない限り候補を一段下げ、`o.prefill_auto_max` と `o.prefill_chunk` もその上限へ制限して再評価する。これは chunk 上限の選択に関する制御であり、ここで生成 token を変換する処理はない（`engine/src/program/generate.cpp:11189-11222`）。

値の helper は static cache を使わない。guard の各候補評価で `std::getenv` が呼ばれ、その都度値を変換する（`engine/src/program/generate.cpp:11207-11209`, `engine/include/strata/core/gfx12_chunk.hpp:28-35`）。空き RAM は `sample_host_memory()` を先に使い、値を得られない場合は `mem_sample().avail_mib` に fallback する。sample の OS ごとの実装・失敗時の扱いは `engine/src/core/conversation_memory.cpp:378-423`、fallback の Linux `/proc/meminfo` 読み取りは `engine/src/program/generate.cpp:1745-1784` にある。`--memory-limit-mib` と `STRATA_MEMORY_LIMIT_MIB` の優先順位は上記のとおり（`engine/src/program/generate.cpp:4724-4737`）。

不足で chunk を下げたときだけ stderr に次の形式で理由を出す。既定予約量か override かはログに区別されず、実際に使った予約量が表示される。空き RAM が 0、必要量を満たす、または該当 chunk 変数が `"1"` の場合、この分岐のログは出ない。Strata がこの不足を理由に終了する処理はなく、ここでは候補を下げて続行する（`engine/src/program/generate.cpp:11209-11222`）。

```text
strata generate: <gfx12|gfx11|NVIDIA>: prompt chunks stay at <next>: <candidate> would lend <slots> more cache slots (<MiB> MiB more held in RAM during a prompt), and <available> MiB of RAM is available for <resident> MiB of resident experts plus that and <reserve> MiB reserve (#2090/#6687; <chunk-env>=1 or STRATA_PREFILL_RAM_RESERVE_MIB=N overrides)
```

## ログと測定値

Strata の設定一覧 `docs/SETTINGS.md:261` はこの名前を `on / off` 型としていますが、実装は 0 以上の MiB 数値を読みます。調査対象のソースでは `docs/DETAILS.md` にこの変数固有の測定値や説明は見つかりませんでした。測定値は記載しません。

## 根拠

- `engine/include/strata/core/gfx12_chunk.hpp:24-35` — helper の単位、数値変換、既定値。
- `engine/src/program/generate.cpp:3995-4016`, `4083-4102`, `4489-4587`, `4724-4737` — CLI と bare-auto/backend 別の拡張上限設定、および RAM limit 設定との関係。
- `engine/src/program/generate.cpp:11170-11222` — 適用条件、RAM 量の比較、step-down、ログ。
- `engine/src/core/conversation_memory.cpp:378-423`, `engine/src/program/generate.cpp:1745-1784` — 空き RAM の取得と fallback。
