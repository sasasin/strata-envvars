# `HY4_PF_BOUNCE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の CPU tier expert を prefill 中に GPU へ転送する経路で、ホスト側 expert arena を直接 pin して DMA 元にするか、pinned bounce ring を介するかを選びます。非 Windows では、非ゼロ値が bounce ring を強制し、ゼロ値は arena pinning を試すよう `Runner::pf_init()` が分岐します。これは転送経路の選択であり、変数の読み取り箇所から生成結果への直接の変更は確認できません（`engine/src/hy4flash/run/hy4_graph.hip.h:545-578,659-675`）。

このコードは `strata-hy4` の CUDA/HIP ビルドに含まれます。Windows では `getenv` と値判定を含むブロックが `_WIN32` で除外されます（`engine/CMakeLists.txt:848-890`、`engine/src/hy4flash/run/hy4_graph.hip.h:563-578`）。

## 値と判定

非 Windows の `Runner::pf_init()` は `getenv` で設定有無を調べ、設定されていれば同じ文字列を `atoi` に渡します。文字列全体の検証はなく、`atoi` が先頭から変換した整数が 0 かどうかで分岐します。したがって空文字や数値で始まらない文字列、`0anything` は 0 扱い、`1`・`-1`・`2x` は非ゼロ扱いです。先頭の空白と符号は `atoi` の変換対象です。大文字小文字は関係しません（`engine/src/hy4flash/run/hy4_graph.hip.h:566-568`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 非 Windows の CUDA/HIP `strata-hy4` | 強制指定なし。安全条件を満たせば arena pinning を試し、それ以外は bounce ring | `atoi(value) != 0`。例: `1`, `-1`, `2x` は bounce ring を強制 | `atoi(value) == 0`。例: 空文字, `0`, `0anything`, `false`, `abc` は arena pinning を試す指定 |
| Windows の CUDA/HIP `strata-hy4` | 実装上、変数を読まない | 該当なし | 該当なし |

0 扱いの値は「arena pinning 成功」を保証しません。pinning が失敗すれば bounce ring に切り替わります。非ゼロ値は arena pinning を試さず、bounce ring を選びます（`engine/src/hy4flash/run/hy4_graph.hip.h:563-578`）。

## 有効になる条件

- `STRATA_BUILD_HY4=ON` で、CUDA または HIP を有効にしたビルドである必要があります。CMake は `strata-hy4` の GPU ソースを CUDA または HIP としてコンパイルします（`engine/CMakeLists.txt:848-890`）。
- Windows では読み取りブロックがコンパイル対象外のため、この変数による選択はありません。Windows では `pinned_arena` が初期値 `false` のまま `pf_bounce=true` になります（`engine/src/hy4flash/run/hy4_graph.hip.h:563-578`）。
- `Runner::init()` が `hyb` のときに限り、さらに `HY4_PF_STREAM` が未設定または `atoi` で非ゼロなら `pf_init()` が呼ばれます。`HY4_PF_STREAM=0` や空文字など `atoi` が 0 を返す設定では、この prefill streaming 初期化自体が行われず、本変数も読まれません（`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`）。
- `pf_init()` 内で CPU expert arena の有効な body を集計した結果 `maxb` が 0 なら、変数を読む前に戻ります（`engine/src/hy4flash/run/hy4_graph.hip.h:545-567`）。
- CLI 引数による `HY4_PF_BOUNCE` の上書きは確認できません。オフライン実行とサーバー実行はいずれも `Runner::init()` を呼ぶため、上記条件を満たせば同じ選択が適用されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-317`）。

## 実行時の詳細

読み取りは `Runner::init()` から呼ばれる `pf_init()` の初期化時に一度行われ、関数ローカル static などへの値の cache はありません。選ばれた経路は `pf_bounce` に保存され、その後の prefill streaming 中、bounce 経路では CPU worker pool が host arena のデータを bounce buffer に詰めてから `hipMemcpyAsync` し、arena pinned 経路では arena から直接 `hipMemcpyAsync` します（`engine/src/hy4flash/run/hy4_graph.hip.h:408-415,659-675,1706-1708`）。プロセス稼働中の環境変数変更を再読する処理は、この経路にはありません。

未設定時に arena pinning を試すには、arena の span が RAM の 70% 未満で、かつ span に 12 GiB を加えた量が RAM 未満である必要があります。`atoi` で 0 になる設定値はこの安全条件を迂回して pinning を試します。`hipHostRegister` が失敗した場合はエラーを捨て、`pinned_arena` を false のままにして bounce ring に進みます（`engine/src/hy4flash/run/hy4_graph.hip.h:569-578`）。

bounce ring の割り当てに失敗すると、容量を 64 MiB 以上の範囲で半減して再試行します。再試行後も失敗し、bounce 経路が必要な場合は prefill streaming を無効にして戻ります。scratch buffer 用の GPU 空き容量が 64 MiB 未満の場合も streaming を無効にします（`engine/src/hy4flash/run/hy4_graph.hip.h:593-619`）。

## ログと測定値

初期化が最後まで成功すると stderr に `[hybrid] prefill streaming on (...)` が出て、括弧内は `pinned bounce ring` または `arena pinned` になります。scratch buffer の空き容量が足りない場合は `[hybrid] prefill streaming disabled: no room for a scratch buffer ...`、bounce ring の確保に失敗した場合は `[hybrid] prefill streaming disabled: cannot allocate ... pinned bounce ring ...` が出ます（`engine/src/hy4flash/run/hy4_graph.hip.h:540-543,597-619`）。

この変数について、上記ソースに性能測定値はありません。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:545-578` — `getenv`、`atoi`、OS 条件、arena pinning の判定。
- `engine/src/hy4flash/run/hy4_graph.hip.h:593-619` — scratch 容量と bounce ring の割り当て、失敗時のログと無効化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:659-675` — bounce 経路と arena pinned 経路の転送。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708` — `hyb` と `HY4_PF_STREAM` による呼び出し条件。
- `engine/CMakeLists.txt:848-890` — HY4 実行ファイルと CUDA/HIP ビルド条件。
