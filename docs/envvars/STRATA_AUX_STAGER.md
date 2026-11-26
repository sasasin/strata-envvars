# `STRATA_AUX_STAGER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU prefill の `Stager` が作る専門家データのコピー用スレッドを、`--aux-cpus` の補助 CPU 配置から除外するかを指定する。値の `atoi` 結果が 0 ならスレッドを `note_owned_thread()` に登録し、補助 CPU への移動対象にしない。それ以外なら `pin_current_thread()` を呼び、補助 CPU 配置が有効な場合に通常どおり配置する。スレッドの CPU 配置だけを変え、コピー内容や生成結果を変える処理はない（`engine/src/prefill/prefill.cpp:1121-1125,1173-1182`; `engine/include/strata/platform/aux_cpus.hpp:243-263`）。

この環境変数は `STRATA_AUX_CPUS` / `--aux-cpus` の配置機能が対象のときに意味を持つ。Metal の `Prefill::init` 経路は Metal 実装へ戻り、この CUDA/HIP `Stager` を通らない（`engine/src/prefill/prefill.cpp:2448-2456`）。

## 値と判定

コピー用スレッドの作成時に `std::getenv` で値を読み、`std::atoi(v) == 0` を判定する。未設定は `keep=false`。空文字や数値に変換できない文字列は `atoi` が 0 を返すため `keep=true` になる。文字列全体の妥当性検査はなく、数値の後ろの文字も検査しない（`engine/src/prefill/prefill.cpp:1178`）。

| 条件 | unset | 有効になる値（スレッドを補助 CPU 配置から除外） | 無効になる値（通常配置経路） |
|---|---|---|---|
| `Stager` がコピー用スレッドを作成 | `keep=false` | `0`, `00`, `-0`, 空文字, `abc`, `0anything`（`atoi` 結果が 0） | `1`, `-1`, `1abc`（`atoi` 結果が非 0） |

空白や符号、数値の後続文字は `atoi` の変換規則に従い、文字列全体の検証や大文字小文字の扱いはない。整数の変換範囲外の入力については `atoi` の規定外動作となるため、コードから有効値として保証されない。値による警告や fallback はない（`engine/src/prefill/prefill.cpp:1178-1181`）。

## 有効になる条件

- CUDA/HIP prefill の `Stager` が初期化され、コピー用スレッドが作られる必要がある。Metal 経路ではこの `Stager` を使用しない（`engine/src/prefill/prefill.cpp:2448-2456,2518-2525,2554`）。
- `STRATA_AUX_STAGER=0` 相当でそのスレッドが補助 CPU への移動対象から除外される効果は、Linux の `strata::aux_cpus` 実装で補助 CPU 配置が使われる場合に限られる。Linux 以外では関連関数が no-op（何もしない）実装（`engine/include/strata/platform/aux_cpus.hpp:151,243-263,407-424`）。
- Linux でも `--aux-cpus` / `STRATA_AUX_CPUS` の配置が無効なら `pin_current_thread()` は何も移動しない。補助 CPU 計画が空の場合も配置は有効にならない（`engine/include/strata/platform/aux_cpus.hpp:243-263,375-404`）。
- `STRATA_AUX_STAGER` は `--aux-cpus` の値を上書きしない。前者は stager コピー用スレッドの登録方法、後者は補助 CPU 配置自体の計画を決める（`engine/src/program/generate.cpp:4715-4724`; `engine/src/prefill/prefill.cpp:1175-1181`）。

## 実行時の詳細

環境変数を読むのは `Stager::init` が作るスレッドのラムダ内である。関数スコープの `static const bool keep` はプロセス内で一度だけ初期化され、最初に実行されたスレッドが読んだ結果を後続のスレッドも共有する。そのため、最初の stager スレッドがこの式を評価した後にプロセス環境を変えても反映されない（`engine/src/prefill/prefill.cpp:1173-1182`）。

`keep=true` のときは `note_owned_thread()` に登録する。Linux の補助 CPU `sweep()` は登録済みスレッドを除外するため、要求ごとに補助 CPU 配置を有効化する経路でも移動対象にならない。`keep=false` のときは `pin_current_thread()` を呼び、補助 CPU 配置が有効なら計画された CPU 群へ移す。有効化時の sweep はエンジンが所有しない既存スレッドにも適用される（`engine/include/strata/platform/aux_cpus.hpp:237-263,276-289`; `engine/src/program/generate.cpp:21431-21439`）。

stager 自体は `Prefill::init` の一度きりの初期化ブロックで生成される。対象のコピー用スレッド数は別途 `STRATA_STAGER_THREADS` や入力ソース種別から決まるが、それらの値が `STRATA_AUX_STAGER` の判定を上書きすることはない（`engine/src/prefill/prefill.cpp:2518-2526,2537-2555`）。

## ログと測定値

この変数を読んだこと、有効/無効になったこと、または変換不能だったことを示す個別ログはない（`engine/src/prefill/prefill.cpp:1173-1182`）。補助 CPU 全体の配置状態は `strata aux cpus: ...` の起動行に出るが、その行は `STRATA_AUX_STAGER` の値や個々の stager スレッドの除外状態を報告しない（`engine/include/strata/platform/aux_cpus.hpp:378-404`）。

`docs/DETAILS.md` は `STRATA_AUX_STAGER=0` が prefill copy threads を作成時の場所に残すと説明しており、実装の登録・配置分岐と一致する。同資料および関連ベンチマークにある中立という測定記録は特定構成での記録であり、この環境変数の一般的な性能効果を示すものとしては記載しない（`docs/DETAILS.md:1433-1447`; `docs/bench-results/2026-10-08-community-2x-rtx3080-20gb-ud-q4-k-xl-512k-pool/README.md:341`）。

## 根拠

- `engine/src/prefill/prefill.cpp:1121-1125,1173-1182` — Stager の役割、スレッド生成、値の読み取りと分岐。
- `engine/src/prefill/prefill.cpp:2448-2456,2518-2526,2537-2555` — Metal 経路との差、stager の初期化とスレッド数。
- `engine/include/strata/platform/aux_cpus.hpp:237-263,276-289,375-424` — 所有スレッド登録、配置、Linux 以外の no-op 実装。
- `engine/src/program/generate.cpp:4715-4724,21431-21439` — `STRATA_AUX_CPUS` の起動時設定と要求単位の配置制御。
- `docs/DETAILS.md:1433-1447` — 補助 CPU の説明。
