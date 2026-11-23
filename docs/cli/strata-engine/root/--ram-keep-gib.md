# `--ram-keep-gib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--ram-keep-gib` |
| 別名 | なし |
| 値 | GiB 単位の数値 `W`（`0` 以上。内部では byte に変換し、上限 1024 GiB） |

## 役割

expert arena を使うときに、arena の読み込み後も空けておきたい RAM 量を指定します。利用可能 RAM が arena の必要量と `W` の合計に届かなければ、条件を満たす場合は arena の代わりに expert の一部を RAM に置く fallback を選び、そのコピー用 RAM 予算にも空き容量の目安を反映します。OS の RAM を予約したり、指定量が常に空くことを保証したりするオプションではありません。

## 使い方

```sh
# 既存のモデルパックを使い、expert arena の後に 8 GiB を空ける目安を指定
strata --pack ./my-model --ram-keep-gib 8
```

## 値と既定値

- 値は必須で、`--ram-keep-gib` の次の引数を `std::atof` で `double` に変換します。省略時の既定値は `0` です。`strata --help` の使用法表示も既定値を 0 としています（`engine/src/program/generate.cpp:1490-1494`）。
- 変換後の値が 0 未満、または NaN なら `strata generate: --ram-keep-gib needs N >= 0` を stderr に出して終了コード 2 で拒否します。値を省略すると `--ram-keep-gib needs a value` を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:3837-3841,4225-4229`）。
- `atof` のため厳密な数値全体の検証はありません。数値として読めない文字列は 0 として扱われ、数値の後ろに変換できない文字があっても数値部分が使われます（`engine/src/program/generate.cpp:4225-4228`）。
- 0 以下は内部 byte 値 0 になり、正の GiB 値は `1073741824` 倍して byte に切り捨てられます。1024 GiB 以上は 1024 GiB に飽和します（`engine/include/strata/core/ple_residency.hpp:148-155`）。
- 同じフラグを複数回指定すると parser が順に値を代入するため、最後に指定した値が残ります。フラグを一度でも指定すると、値が 0 でも `STRATA_RAM_KEEP_GIB` よりフラグが優先されます（`engine/src/program/generate.cpp:3836-3837,4225-4229,4275-4277`）。

## 実行時の動作

- このフラグを省略した場合、`STRATA_RAM_KEEP_GIB` が空でなく、`atof` の結果が正なら、その値を同じ GiB→byte 変換で読み込みます。環境変数が未設定・空・0 以下・数値として読めない場合、値は既定値 0 のままです。CLI フラグがあれば環境変数を読みません（`engine/src/program/generate.cpp:4272-4277`）。環境変数の仕様は [`STRATA_RAM_KEEP_GIB`](../../../envvars/STRATA_RAM_KEEP_GIB.md) を参照してください。
- arena の通常の RAM 判定では、arena と予備 blob の必要量に `W` を加えた量が利用可能 RAM に収まる場合に arena を選ぶ条件になります。加算は整数 overflow を避けて飽和します（`engine/src/core/expert_source.cpp:6532-6537`、`engine/include/strata/core/ple_residency.hpp:159-162`）。
- hard memory limit 下で arena 不足時の fallback が許可されている場合、arena の判定に使う必要量は arena と `max(W, fallback headroom)` の合計です。`STRATA_RESIDENT_HEADROOM_GIB` が `atof` で 0 以上になる値ならその値が fallback headroom を決め、OS は Windows で 8 GiB、それ以外で 4 GiB を既定の安全 headroom とします。ここも厳密な数値全体の検証はなく、数値として読めない文字列は 0 として headroom を上書きします（`engine/src/program/generate.cpp:8542-8546`、`engine/include/strata/core/ple_residency.hpp:157,174-177`）。
- RAM 不足時に RAM-copy fallback が選ばれると、利用可能 RAM から headroom を差し引いた範囲で expert RAM 予算を決めます。headroom と 1 GiB の余裕を確保できない場合、RAM copy の予算は 0 になります（`engine/src/program/generate.cpp:8827-8837`、`engine/include/strata/core/ple_residency.hpp:180-183`）。この自動 fallback は expert profile があり、明示的な resident CPU mode がなく、`STRATA_ARENA_FALLBACK_RESIDENT=0` でもない場合に限って RAM-copy mode へ進みます。それ以外はファイルを読む経路などへ移ります（`engine/src/program/generate.cpp:8821-8839`）。
- `--resident-budget-gib` または `--resident-experts` の明示的 RAM mode では、`W > 0` かつ `STRATA_RESIDENT_HEADROOM_GIB` の `atof` 結果が 0 未満または NaN でない場合、その環境値が優先されます（数値として読めない文字列も 0 として優先）。それ以外では既存の `resident_headroom` が `W` より小さければ `W` まで引き上げます（`engine/src/program/generate.cpp:4216-4223,4272-4280`）。
- RAM 不足時の自動切替は常に有効ではありません。`--ple-io ram` を明示した場合、`--shared-expert-arena` を指定した場合、または `STRATA_ARENA_RAM_FALLBACK=0` の場合は fallback が無効です（`engine/src/program/generate.cpp:8526-8532`、`engine/include/strata/core/ple_residency.hpp:67-73`）。また shared arena file が指定されると、arena RAM 判定の host-memory probe 自体が行われません（`engine/src/core/expert_source.cpp:6532-6533`）。
- RAM の必要量判定は `host_available_memory` が情報を取得できる場合の処理です。したがって、このオプションだけで他プロセスの RAM 消費を制限したり、常に `W` GiB の空きを保証したりすることはできません（`engine/src/core/expert_source.cpp:6532-6537`）。

## 適用条件と副作用

- 通常の効果は expert arena の起動時 RAM 判定に現れます。すでに `--mmap-experts` などファイルベースの expert mode を選んでいる場合は、arena の採否判定ではなく、明示的 RAM mode における headroom 調整に関係します（`engine/src/program/generate.cpp:8550-8587,4272-4280`）。
- arena が RAM 不足で fallback すると、expert の一部または全体がモデルファイルから読み込まれ、stderr に不足通知が出ます。`--serve` では同じ通知を stdout にも出します（`engine/src/program/generate.cpp:8810-8819`）。arena を使い続ける経路では、正の `W` のとき設定値と fallback headroom を説明する行が stderr に出ます（同 `generate.cpp:8791-8798`）。
- fallback が無効で hard memory limit を満たせない場合、arena 読み込みは失敗し、エラーを stderr に出して終了コード 1 になります。通常の利用可能 RAM が不足しても fallback が無効なら、ソース上はその不足だけで必ず拒否するとはしておらず、警告後の扱いは RAM 判定経路に依存します（`engine/src/core/expert_source.cpp:6543-6559,6604-6605`、`engine/include/strata/core/expert_source.hpp:1384-1389`）。

## 出力とエラー

値が無効または欠けている場合の stderr と終了コードは「値と既定値」を参照してください。正の値なら arena 起動前に stderr へ説明行を出します。arena 不足時の fallback 通知も stderr に出て、`--serve` の場合は stdout にも出ます（`engine/src/program/generate.cpp:8793-8798,8810-8817`）。

## 根拠

- `engine/src/program/generate.cpp:1490-1494` — help 表示上の値、既定値、RAM keep と fallback の説明。
- `engine/src/program/generate.cpp:3836-3841,4225-4229` — root parser の値取り、変換、負値・NaN の拒否、フラグ優先を示す状態。
- `engine/src/program/generate.cpp:4272-4280` — `STRATA_RAM_KEEP_GIB` の読み込みと `STRATA_RESIDENT_HEADROOM_GIB` との優先関係。
- `engine/src/core/expert_source.cpp:6532-6537,6543-6559,6604-6605` — arena 必要 RAM の算定と不足時の判定・失敗経路。
- `engine/include/strata/core/ple_residency.hpp:67-73,140-183` — fallback の抑止条件、GiB 変換・上限、安全 headroom と fallback 予算。
- `engine/src/program/generate.cpp:8526-8546,8791-8819,8821-8839` — fallback 有効条件、RAM-copy headroom、起動時の出力と自動 RAM-copy 適用条件。
- `engine/src/program/generate.cpp:8550-8587` — `--mmap-experts` を含む file-based expert mode の処理。
- ツール ID と scope は `docs/cli/000_cli_tools.md:10`、対象リンクと root scope は `docs/cli/README.md:1036-1041,1187-1190` で照合しました。

調査制約: 安全に実行できる同一 revision の既存 `strata` バイナリによる `--help` 確認は行わず、help 表示文字列と parser のソースを照合しました。Qwen3.6 系など独自 parser に振り分けられるモデルでは別 parser となるため、この文書の説明範囲は `engine/src/program/generate.cpp` の root parser です。
