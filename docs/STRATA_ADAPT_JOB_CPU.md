# `STRATA_ADAPT_JOB_CPU`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

非同期 adaptive tier のバックグラウンド `JobThread` を、指定した論理 CPU に配置する。スレッドが実行するのは adaptive tier のコピーやメモリーコピー処理で、変数は tier の有効化や swap の選択自体を変えない。`--adapt-async 1` が有効で、非同期 tier の `JobThread` が実際に作られた場合にだけ読まれる。

## 値と判定

| 環境変数の状態・値 | `atoi` の結果と処理 |
|---|---|
| 未設定 | Windows では `smt_spare_cpu()` が選ぶ CPU を使う。Linux では同関数が `-1` を返し、CUDA/HIP 系では `--aux-cpus` のスレッド配置へ委ねる。SYCL 系ではこの箇所で追加の pin をしない。 |
| `-1` など負数 | `cpu < 0` となり、明示的な CPU pin をしない。CUDA/HIP 系では明示設定ありとして補助 CPU の対象外にする。SYCL 系では対象外登録もない。 |
| `0` 以上の整数 | その番号を論理 CPU として `pin_current_thread(cpu)` に渡す。CUDA/HIP 系では明示設定ありとして補助 CPU の対象外にする。 |
| 空文字、数字で始まらない文字列 | `atoi` が `0` を返すため、CPU 0 への pin を試みる。 |
| 数字の後ろに文字が続く値 | 数字の先頭部分が変換される。たとえば `12junk` は `12`。空白と符号も `atoi` の規則で処理される。 |

コードは文字列全体の検証、範囲制限、無効値の fallback をしていない。したがって、CPU 番号が実行環境で有効かは pin の成否による。CPU 配置 helper が失敗した場合、以前の配置を保ち、OS 別の `strata cpu pool: ... affinity ... failed ...; previous ... kept` 警告を stderr に出す。`atoi` で `int` に表現できない値の結果はここでは規定しない。

## 有効になる条件

- native CUDA/HIP 系では `--adapt-async 1` が要求され、`--serve`、adaptive tier の `--adapt-every` / swap 数、resident RAM mode (`--resident-experts`) などの条件を満たす必要がある。batch group、peer device、remote expert 経路などでは非同期 tier が blocking tier に切り替わる。環境変数自体はこれらの条件を上書きしない。
- `JobThread` の生成時には、usage 情報があり、resident complement が準備済みで、exchange buffer 容量が必要量以上であることも確認する。
- `smt_spare_cpu()` の自動選択は Windows のみ。二つ以上の論理 CPU がある物理 core のうち、host/pool の割当を避ける最後の spare SMT sibling を返す実装で、取得に失敗すると `-1`。他 OS では常に `-1`。
- Linux の native CUDA/HIP 系は、CPU を自動選択できないとき `STRATA_AUX_CPUS` / `--aux-cpus` が有効なら、その補助 CPU set へ移動する。変数が明示設定されている場合は `note_owned_thread()` に登録し、後続の aux thread sweep がこのスレッドを移動しない。SYCL 側の同じ `JobThread` にはこの登録・補助 CPU fallback がない。

## 実行時の詳細

環境値は `JobThread` のワーカースレッドが起動し、`loop()` に入ったときに一度だけ読み取る。コンストラクタがスレッドを作った後、ループ開始時に `getenv` を呼び、設定値なら `atoi`、未設定なら Windows の自動選択を行う。その後はジョブ待機ループに入るため、スレッド作成後に環境を変更しても配置は再評価されない。子プロセスへの転送や書き換えはない。

native CUDA/HIP 系の `loop()` は、CPU 番号が非負なら `strata::kernels::cpu::pin_current_thread()` を呼ぶ（失敗結果は呼び出し側で無視するが、helper は警告を出す）。設定値が存在する場合は、その数値が負でも `note_owned_thread()` を呼び、Linux の aux sweep に移動されないようにする。未設定かつ自動選択不能なら `strata::aux_cpus::pin_current_thread()` を呼ぶ。補助 CPU 機能が無効ならこの呼び出しは何もしない。

SYCL 系の `JobThread` も環境値を同じ `getenv` / `atoi` で読み、非負値を CPU pin helper に渡す。未設定時の Windows 自動選択処理は native 版と共通だが、SYCL 版のループには `note_owned_thread()` と `aux_cpus::pin_current_thread()` の分岐がない。

## 根拠

- native CUDA/HIP 系の値読み取り、配置、aux CPU 登録: `src/program/generate.cpp:1411-1444`。ワーカースレッドの生成条件: `src/program/generate.cpp:8642-8649`。
- `--adapt-async` が blocking tier に戻る条件: `src/program/generate.cpp:6676-6700`。通常の適用条件の説明: `docs/DETAILS.md:168-179`。
- SYCL 系の値読み取り・配置と、`JobThread` の生成: `sycl/src/program/generate.cpp:1334-1365`, `sycl/src/program/generate.cpp:8072-8079`。
- CPU affinity helper の失敗時ログと既存配置の維持: `src/kernels/cpu/pool.cpp:363-386`。
- Linux aux thread の登録と未登録 thread の移動: `include/strata/platform/aux_cpus.hpp:234-260`。他 OS では aux helper が空実装: `include/strata/platform/aux_cpus.hpp:344-357`。
- Strata の thread-placement 文書も、明示した `STRATA_ADAPT_JOB_CPU` が adaptive tier の job thread に優先すると説明する: `docs/DETAILS.md:1744-1763`。文書には文字列変換の細則はないため、上表はソースの `atoi` 呼び出しに基づく。
