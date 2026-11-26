# `STRATA_RAM_ADAPT_QUEUE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`STRATA_RAM_ADAPT_QUEUE` は、resident RAM の適応でファイルから読む expert を先行ステージするときに、未処理 job を `ram_jobs_` に何件まで保持するかを決める上限です。キューが上限に達している場合、追加 job を登録せず `ram_stage` は `false` を返します。値は RAM 適応を有効化するスイッチではなく、VRAM/RAM の容量や expert の選択規則も変えません。読み取りは `FileExpertSource::ram_stage` のみです（`engine/src/core/expert_source.cpp:5007-5031`）。

このキュー経路は `--serve` の処理内で、`STRATA_RAM_ADAPT2` が有効なときに使われます。さらに `STRATA_RAM_ADAPT` が正でなければステージ対象の選定自体が行われません。これらの条件を満たさない場合、この変数を設定しても効果はありません（`engine/src/program/generate.cpp:12302-12307`, `12333-12349`, `22836-22922`）。

## 値と判定

`ram_stage` の最初の呼び出しで `std::getenv` を行い、未設定なら容量を `64` とします。設定されていれば `std::atoi` の結果と `1` の大きい方を `size_t` に変換します。したがって設定値の有無だけではなく、整数への変換結果が使われます（`engine/src/core/expert_source.cpp:5013-5019`）。

| 条件 | unset | 有効になる値 | 結果・例 |
|---|---:|---|---|
| `ram_stage` の初回呼び出し | 64 件 | `atoi` の値が 1 以上 | `1` は 1、`8` と `8xyz` は 8。先頭空白や符号は `atoi` の変換規則に従う |
| 設定値を整数として読めない、空文字、`0`、負数 | — | なし | `atoi` が 0 を返す場合は `max(1, 0)` で 1。たとえば `true`、空文字、`0anything`、`-3` は 1 |

`atoi` は文字列全体の妥当性を検査しません。整数部分の後ろの文字は無視されます。整数として表現できないほど大きい値に対する `atoi` の結果は C/C++ ライブラリの仕様上保証できないため、受け付けられる上限をこのコードから定めることはできません。明示的に `1` 未満を指定してキュー登録を無効化する値はなく、最小容量は 1 です。

## 有効になる条件

- `STRATA_RAM_ADAPT` が正で、`STRATA_RAM_ADAPT2` が `std::atoi` で 0 以外となる必要があります。`STRATA_RAM_ADAPT2` が未設定、空文字、または `atoi` の結果が 0 なら staged 経路は選ばれません（`engine/src/program/generate.cpp:12333-12349`, `22843-22850`）。
- 呼び出し元の RAM 適応処理は `o.serve` 分岐の内側にあるため、環境変数の効果は `--serve` に限られます（`engine/src/program/generate.cpp:12302-12307`, `22836-22850`）。
- デコードが最初の window を過ぎ、routing usage があり、adaptive round が未処理で、resident RAM copy が利用可能である必要があります。multi-GPU、peer、remote expert、`--batch` の経路では staged RAM promotion は行われません（`engine/src/program/generate.cpp:22847-22856`）。
- 上記条件を満たしても、候補の expert が各層で RAM 外かつ GPU 外で、適応ポリシー上の対象となり、対応する RAM 内 expert と組み合わせられる必要があります（`engine/src/program/generate.cpp:22862-22909`）。
- `ram_stage` の読み取り箇所自体に OS/backend の分岐や build macro はありません。実装は共通 GPU engine の `strata_engine` に含まれ、その engine の実行ファイルが `generate.cpp` から作られます。CUDA/HIP 共通のソース構成です（`engine/src/core/expert_source.cpp:5013-5019`; `engine/cmake/strata_gpu_engine.cmake:310,548`）。

## 実行時の詳細

`ram_adapt_n`（`STRATA_RAM_ADAPT`）と `ram_adapt2.on`（`STRATA_RAM_ADAPT2`）が staged RAM 適応経路を選ぶと、各 decode window の境界で、まず完了済み job を `ram_install` が取り出して RAM copy に反映します。次に適応ポリシーが選んだ promotion 候補を gain 順に見て、`ram_adapt_n` 件まで `ram_stage` に登録します（`engine/src/program/generate.cpp:22843-22857`, `22913-22918`）。

キュー容量は `ram_stage` 内の関数ローカル `static` です。プロセス内で最初にこの関数が呼ばれたときに一度だけ評価され、その後の環境変更や別の `FileExpertSource` インスタンスでは読み直されません。キュー本体は各 `FileExpertSource` が持ちます。容量判定は `ram_jobs_.size() >= cap` で、job が読み込み中だけでなく、読み込み完了後に `ram_install` が回収するまでの job も件数に含まれます（`engine/src/core/expert_source.cpp:5013-5028`, `5073-5081`; `engine/include/strata/core/expert_source.hpp:1198-1207`）。

上限に達した場合は待機せず `false` を返し、その候補はその呼び出しでは queue に入りません。呼び出し元は `false` をステージ件数に加算せず、残りの候補を続けて検討します。空きができると次の適応 window で再び候補選定され得ます（`engine/src/core/expert_source.cpp:5019-5031`; `engine/src/program/generate.cpp:22914-22918`）。job が受理されると単一の `strata-ram` worker thread がファイル読み込みを行い、完了した job は後続の window 境界で install されます（`engine/src/core/expert_source.cpp:5023-5028`, `5041-5071`, `5073-5093`）。

## ログと測定値

キューが満杯で候補を拒否したことを示す専用ログはありません。読み込み失敗や install 時の不整合もキュー拒否とは別に扱われ、`ram_install` は失敗 job を skip カウンターに加えます（`engine/src/core/expert_source.cpp:5061-5069`, `5083-5092`）。

`STRATA_RAM_ADAPT2` が有効なら、リクエスト終了時に stderr へ `strata serve: resident RAM (STRATA_RAM_ADAPT2): ... promotions read on the I/O thread, ... installed, ... skipped at the install (... of them: the GPU tier took one of the pair)` を出し、読み込み・install・skip の累積数を示します。この行に queue 容量や満杯による拒否数は含まれません（`engine/src/program/generate.cpp:23801-23805`）。`STRATA_RAM_ADAPT2` 経路が無効な場合、この行も出ません。

`docs/DETAILS.md` は旧来の `STRATA_RAM_ADAPT` による RAM copy の適応条件と挙動を記載していますが、`STRATA_RAM_ADAPT_QUEUE` の上限値・parse 規則・ログについては記載していません（`docs/DETAILS.md:274-282`）。本書の queue に関する記述は現行コードに基づきます。

## 根拠

- `engine/src/core/expert_source.cpp:5007-5031` — `ram_stage` の前提条件、環境変数の parse、上限判定、job 登録。
- `engine/src/core/expert_source.cpp:5041-5093` — worker によるファイル読み込みと、完了 job の install / skip。
- `engine/src/program/generate.cpp:12333-12349` — `STRATA_RAM_ADAPT2` の既定値・判定。
- `engine/src/program/generate.cpp:22836-22922` — RAM 適応の条件と staged 候補の登録。
- `engine/src/program/generate.cpp:23801-23809` — staged RAM promotion および RAM 適応の stderr 集計。
- `engine/cmake/strata_gpu_engine.cmake:310,548` — expert source と生成プログラムを GPU engine に含める構成。
- `engine/include/strata/core/expert_source.hpp:880-889`, `1198-1207` — staged promotion API と queue/thread の所有範囲。
- `docs/DETAILS.md:274-282` — 既存説明との照合。
