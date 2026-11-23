# `HY4S_RAM_BUDGET_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_RAM_BUDGET_GB` は Intel Arc 向け HY4-Flash SYCL runner が unified expert pool を準備するとき、GPU0 VRAM と peer GPU に載らない Section 4 experts のうち RAM arena に割り当てる予算を指定する。余った experts は `cold_mask` に回される。したがって、この値は expert の配置と SSD cold tier の量を変えるが、コード上ではモデルの expert の順位付け・選択や生成 token を変更する設定として使われていない（`engine/src/hy4flash/sycl/sy_graph.h:155-200`）。

対象経路は `setup_experts_unified()` であり、単発実行と `--serve` の初期化から呼ばれる。SYCL runner は別個の実験的 backend である（`engine/src/hy4flash/sycl/sy_main.cpp:298-306`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`、`engine/CMakeLists.txt:25-30`）。

## 値と判定

関数内で `std::getenv("HY4S_RAM_BUDGET_GB")` を一度呼ぶ。ポインタが null なら未設定、null でなければ値を `atof()` に渡して結果に `1e9` を掛け、`uint64_t` に変換する。文字列全体の検査、範囲検査、clamp、変換失敗時の警告はない（`engine/src/hy4flash/sycl/sy_graph.h:162-170`）。

| 条件 | unset | 有効になる値（例） | 無効・境界になる値（例） |
|---|---|---|---|
| `--ram-experts-gb` が正でない場合 | `CpuExperts::ram_budget_bytes()` を使い、`host_overhead_bytes + 8.5e9` を差し引いた自動予算（下限 0） | `8` → 8,000,000,000 bytes。数値の後ろに文字がある値も `atof()` の数値変換で解釈される | 空文字や数値として始まらない文字列は `atof()` が 0 とし、予算 0。`0` も 0。負数・非有限値・変換範囲外をコードは検査しないため、整数変換結果を有効な予算として保証できない |
| `--ram-experts-gb` が正の場合 | 環境変数を参照せず CLI 値を使う | `--ram-experts-gb 8` → 8,000,000,000 bytes | CLI の 0 または負数は優先値にならず、環境変数または自動予算へ進む |

`atof()` によるため、先頭空白は数値変換の対象となり、数値の後続文字列や大文字小文字の真偽値は設定形式として検証されない。例えば `8GB` は数値部分 8 として扱われ、`true` や `abc` は 0 になる。`atof()` の結果を符号なし整数へ直接変換するので、負数や表現範囲外の値については portable な挙動をこのコードから保証できない。明示的な環境値 `0` は未設定と異なり、自動予算に戻らない（`engine/src/hy4flash/sycl/sy_graph.h:162-170`）。

## 有効になる条件

- HY4-Flash の SYCL runner の実行経路であること。通常の CUDA/HIP 経路にこの名前の読み取りはない（この checkout の全参照検索では `engine/src/hy4flash/sycl/sy_graph.h:165` のみ）。
- `--ram-experts-gb` を省略するか、0 以下にすること。正の CLI 値があれば環境変数は無視される（`engine/src/hy4flash/sycl/sy_main.cpp:103-104,140-141`）。
- 関数は GPU0 VRAM と active peer GPU の expert mask を先に除外し、残りを rank 順に予算内 RAM mask へ入れる。最初に予算を超える expert に達すると `ram_full` を立て、その expert と以後の未配置分は cold mask に入る（`engine/src/hy4flash/sycl/sy_graph.h:173-200`）。
- `--serve` でも同じ設定が使われる。serve 側に独立した `--ram-experts-gb` parser はなく、`sy_main.cpp` が CLI 値を `ServeOpts` に渡して同じ初期化関数を呼ぶ（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:36-37,280-285`）。
- 未設定の場合の自動経路は `CpuExperts::ram_budget_bytes()` を呼び、`host_overhead_bytes + 8.5 GB` を保持分として差し引く。ソース全体では `hy4s_cpuexp.cpp` に同名の `static` な名前空間内関数がある一方、`CpuExperts::ram_budget_bytes()` の宣言・定義は検索で確認できず、呼び出しとの不一致が残る。このため、自動経路のビルド可否やシステム RAM から得る具体的な予算はソース確認だけでは確定できない（呼び出し: `engine/src/hy4flash/sycl/sy_graph.h:167-170`; 同名関数: `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:332,480-494`）。
- cold experts がある非 Windows 経路では、`STRATA_CPUEXP_COLD_IO` が未設定かつ cold 総量が 12 GB 未満なら、Strata はこれを `buffered` に設定してから cold experts の登録を試みる。これは本変数の値を読み直す処理ではない（`engine/src/hy4flash/sycl/sy_graph.h:217-227`）。

## 実行時の詳細

単発 runner はモデルと Runner の初期化後、推論前に `setup_experts_unified()` を呼ぶ。serve はモデル・Runner・必要なら DFly2 の初期化後に同じ関数を呼ぶ。RAM 予算はその呼び出しの中で決まり、関数内でキャッシュされない。プロセス起動後に環境を変更しても、既に作成された mask と expert pool の配置には反映されない。serve のリクエストごとの再評価もない（`engine/src/hy4flash/sycl/sy_main.cpp:298-308`、`engine/src/hy4flash/sycl/sy_serve.h:271-287`、`engine/src/hy4flash/sycl/sy_graph.h:162-200`）。

予算に収まる未配置 experts は `cpu_mask`、それ以外は `cold_mask` に分けられる。続けて CPU expert pool を初期化し、非 Windows で cold があれば cold tier の登録を行う。GPU cache / peer 初期化、rank table または body size table の読み込み、CPU pool 初期化、cold tier 登録のいずれかが失敗すると helper は `false` を返す（`engine/src/hy4flash/sycl/sy_graph.h:127-159,173-227`）。

## ログと測定値

成功時は stderr に `[experts] unified pool ...` の行を出し、RAM と cold SSD の expert 数・GB を含む（`engine/src/hy4flash/sycl/sy_graph.h:229-235`）。専用の値不正警告はなく、空文字・不正文字列は 0 予算として処理される。

初期化失敗時、単発 runner は stderr に `experts: <error>` を出して status 1 で戻る。serve は protocol 出力に `ERR experts: <error>` を出して status 1 で戻る（`engine/src/hy4flash/sycl/sy_main.cpp:304-306`、`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。この環境変数についての測定値は Strata ソースで確認できない。

## 根拠

- 全参照と予算判定・rank 順 partition・cold tier・成功ログ: `engine/src/hy4flash/sycl/sy_graph.h:123-235`
- CLI 既定値・引数 parse・serve への引き渡し・単発実行呼び出し: `engine/src/hy4flash/sycl/sy_main.cpp:103-104,140-141,215-248,298-306`
- serve の既定値と共通 helper 呼び出し: `engine/src/hy4flash/sycl/sy_serve.h:28-44,280-285`
- SYCL backend の分離と実験的 build 条件: `engine/CMakeLists.txt:25-30`
