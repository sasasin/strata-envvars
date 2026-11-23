# `STRATA_CPUEXP_ACT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU resident expert の入力活性を Q8_1 の 1 項で処理する `q8` と、量子化残差を第 2 の Q8_1 項として加える `hi` の切り替えです。`hi` では `z` と gate/up 後の `h2` を本項と残差項に分け、fast kernel では 2 回の積和を fp32 で合算します。これは CPU experts の計算経路に対する設定であり、GPU resident experts 自体の動作をこの環境変数が直接設定するコードは確認できません。実装は `CpuExperts::Impl::load` と、その呼び出し元である HY4 CUDA/HIP graph および SYCL unified pool です（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1865,2311-2336,2355-2372,2395`; `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`; `engine/src/hy4flash/sycl/sy_graph.h:214-230`）。

## 値と判定

`CpuExperts::Impl::load` は CPU kernel を選んだ後、`std::getenv` で環境変数を読み、文字列全体を大文字小文字を区別して `strcmp` します。`hi` だけが `hi=true`、`q8` だけが `hi=false` に上書きします。数値変換、空白除去、範囲検査はありません。未設定なら kernel 由来の初期値を保ちます。空文字を含むその他の設定値は警告なしで初期値を保ちます（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1821-1862`）。

| 経路・条件 | unset | 有効になる値（例） | 無効・初期値を保つ値（例） |
|---|---|---|---|
| `CpuExperts::Impl::load` 共通初期値。AVX2 kernel `kern==1` は `hi`、library kernel `kern==0`・AVX2-VNNI `kern==4`・AVX-512 `kern==2`・NEON `kern==3` は `q8` | 選択 kernel の初期値 | `hi` → `hi`、`q8` → `q8` | `HI`、`1`、`true`、`0`、空文字、`0anything` → 初期値のまま。無効値の警告なし |
| CUDA/HIP graph が CPU expert pool を初期化する経路 | `CpuExperts::init` 後に `set_hi_activations(true)` を呼ぶため最終値は `hi` | `hi` → `hi`。`q8` → `q8` | 空文字や未知値も「設定済み」なので graph の未設定時 `hi` 上書きを止め、共通初期値を残す |
| SYCL unified pool | 共通初期値。CLI による強制指定がなければ維持 | `hi` → `hi`、`q8` → `q8` | 空文字や未知値は共通初期値のまま |

共通初期値の kernel 選択は CPU / OS の命令セット対応と `STRATA_CPUEXP_KERNEL` 等にも依存します。x86 の選択と対応確認は `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1131-1185,1820-1839`、NEON は同 `:1202-1216,1840-1855` にあります。値の例は上記の `strcmp` 分岐に対するものです。

## 有効になる条件

- `CpuExperts` の初期化経路が実行される必要があります。HY4 CUDA/HIP graph は `g.cpu_mask` が空でない場合に初期化し（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）、SYCL は GPU/peer に割り当てなかった残余 expert を CPU mask に振り分けて unified pool を初期化します（`engine/src/hy4flash/sycl/sy_graph.h:173-200,214`）。CPU resident expert がない場合、この設定で CPU expert 計算の結果は変わりません。
- CUDA/HIP graph では `getenv` が非 null かだけで未設定を判定します。従って `STRATA_CPUEXP_ACT=` のような空文字も未設定扱いにはならず、graph 側の `hi` 強制を抑止します（`engine/src/hy4flash/run/hy4_graph.hip.h:1579`）。
- SYCL の単発 CLI は `--cpu-hi` または `--expert-act 0` で `hi_act` を true にし、初期化後に `set_hi_activations(true)` を呼びます。`--expert-act` の既定値は `1` であり、既定では強制しません（`engine/src/hy4flash/sycl/sy_main.cpp:99-104,143,160,237,292-304`; `engine/src/hy4flash/sycl/sy_graph.h:214-215`）。この明示的な CLI `hi` は環境値 `q8` より後に適用され、最終値を `hi` にします。`--expert-act 1` は環境値 `hi` を解除しません。
- SYCL serve も `--cpu-hi` または `--expert-act 0` を `ServeOpts::hi_act` に渡し、pool 初期化後に `hi` を強制できます（`engine/src/hy4flash/sycl/sy_main.cpp:226-240`; `engine/src/hy4flash/sycl/sy_serve.h:280-285`）。
- GPU resident experts は SYCL の別設定経路（`vcache.set_q8_act` / `peers->set_q8_act`）で扱われます。SYCL CLI の hi 指定はそれらにも影響しますが、`STRATA_CPUEXP_ACT` の読み取り結果をそこへ渡す処理は見つかりません（`engine/src/hy4flash/sycl/sy_graph.h:141-152,214-215`）。

## 実行時の詳細

環境値は `CpuExperts::Impl::load` の初期化時に一度読み、`Impl::hi` に保持します。各 `submit` はその時点の `hi` を job にコピーし、CPU worker は job の値で `z` の量子化と gate/up・down の積和を選びます。`hi` の場合は残差ブロックを追加計算します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1866,2589-2612,2311-2336,2355-2372,2395-2401,3117`）。このためプロセス環境を pool 初期化後に変更しても自動再読込されません。一方 `set_hi_activations(bool)` は実行中 job の完了を `wait()` してから `Impl::hi` を変更する実行時 API です（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:3130-3143,3165-3169`）。

CUDA/HIP graph は共通初期化が終わった直後に、環境変数が未設定なら `set_hi_activations(true)` を呼びます。このため同じ unset でも共通初期値とは異なり、graph で pool を使う経路の最終値は `hi` です。空文字や無効値も設定済み判定に通るため、この上書きは行われません（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1583`）。HY4 graph の serve/main などは同じ graph 実装を include します（`engine/src/hy4flash/run/hy4_main.hip.cpp:11`; `engine/src/hy4flash/run/hy4_serve.hip.h:37`）。

## ログと測定値

CPU pool の初期化時に stderr へ `[cpuexp] ... kernel=%s, act=%s` が出て、共通初期化時点の `hi(2xQ8_1)` または `q8` を表示します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1863-1866`）。CUDA/HIP graph の未設定時上書きと SYCL CLI の明示的上書きはこのログより後なので、この行は最終設定を表さない場合があります。SYCL は上書き後に `[experts] unified pool (..., act=%s)` を stderr に出します（`engine/src/hy4flash/sycl/sy_graph.h:214-234`）。環境値が未知・空文字の場合の専用警告や失敗経路はありません。SYCL pool 初期化自体が失敗した場合は単発 CLI が `experts: ...` を出して status 1、serve は `ERR experts: ...` を protocol に出して status 1 で戻りますが、これは環境値の検証エラーではありません（`engine/src/hy4flash/sycl/sy_main.cpp:304-306`; `engine/src/hy4flash/sycl/sy_serve.h:283-285`）。

この commit の `docs/DETAILS.md` からは本変数に関する条件付き測定値を確認できなかったため、性能・品質の数値は記載していません。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1821-1866` — kernel 選択、環境値の完全一致判定、初期化ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583` — CUDA/HIP 側の CPU pool 初期化と unset 判定による上書き。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2311-2401,2589-2612,3117,3165-3169` — job への値のコピー、活性計算、setter の待機と更新。
- `engine/src/hy4flash/sycl/sy_graph.h:141-152,173-215,229-234` — SYCL の pool・CLI hi 指定・ログ。
- `engine/src/hy4flash/sycl/sy_main.cpp:99-104,143,160,226-240,292-306`; `engine/src/hy4flash/sycl/sy_serve.h:280-285` — SYCL CLI / serve の設定伝播と初期化失敗時の結果。
