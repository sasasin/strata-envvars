# `STRATA_VERIFY_DEVICE_HITS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

部分 VRAM の verify window で、VRAM に常駐する expert hit のグループ計画を GPU 上で作る。CPU は expert の `kind[]` を分類し、非 resident expert の計算を担い、resident hit の計画と hit 出力の計算・加算は verifier の GPU 側が行う。`--pcie-frac 0` で PCIe staging が無い場合に限り有効になる機能で、値を有効にしただけでは起動しない。主な実装は `Verifier::init`、`Verifier::device_hits_active`、`Verifier::run` と `expert_pool_dispatch_multi` にある（`engine/src/core/verify.cpp:1414-1428,2686-2699`、`engine/include/strata/core/verify.hpp:439-442`、`engine/src/core/expert_source.cpp:5611-5619`）。

## 値と判定

実行時の判定は `device_hits_env_on` が `std::atoi` の結果を 0 と比較する。未設定は無効、空文字も `atoi("") == 0` で無効。先頭の空白・符号付き数値は `atoi` の規則で変換され、数値で始まる文字列は後続文字を無視する。したがって `1`、`2`、`-1`、`1junk` は有効、`0`、`0junk`、`true`、`false`、`junk`、空文字は無効。文字列全体の妥当性検査や範囲制限はない（`engine/include/strata/core/device_hits_plan.hpp:25-27`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| verifier の実行時判定 | `false` | `1`, `2`, `-1`, `1junk` | 空文字, `0`, `0junk`, `true`, `junk` |
| CUDA 起動時の NVIDIA 世代別既定 | 下記条件なら Strata が未設定変数を `1` に設定 | 利用者が事前に設定した値を保持 | 設定済みの空文字や `0` も保持され、既定値で上書きされない |

CUDA の同一 compute capability のカードだけが見える起動経路では、main card の VRAM が 16 GiB より大きく、以下の既定テーブルが有効な場合に限って `apply_nv_defaults` が未設定のこの変数を `1` にします。sm_86 は `STRATA_SM86_PERF=0` でテーブルを止めます。sm_89 / sm_120 / sm_121 はそれぞれ `STRATA_SM89_PERF=0` / `STRATA_SM120_PERF=0` / `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` でテーブルを止めます。sm_86 はこのコード上 `STRATA_DEFAULTS=026` による早期除外をしません。16 GiB 以下では通常 `STRATA_ADAPT_FETCH=2` の既定を優先し、device hits の既定は追加しません（`engine/src/core/nv_defaults.cpp:37-42,73-74,75-103,104-135,176-217`; VRAM 閾値: `engine/include/strata/core/nv_defaults.hpp:33-34`）。

既定値の適用時は `getenv(...) != nullptr` なら内容に関係なく利用者設定を優先し、未設定だけを環境へ書き込みます。起動時の既定設定は CUDA build で、可視 NVIDIA GPU が同一世代の場合に呼ばれます。HIP と Metal ではこの NVIDIA 既定設定ブロックを通りません（`engine/src/program/generate.cpp:4416-4444`、`engine/src/core/nv_defaults.cpp:222-233`）。

## 有効になる条件

- `Verifier::init` で `STRATA_VERIFY_DEVICE_HITS` が `atoi` で非 0 と判定され、全 expert 常駐 (`all_resident_`) ではなく、`always_publish_` でもなく、device residency table (`hits.d_res`) と cache (`hits.cache_base`) があること。Metal build は `device_hits_` を常に false にする。CUDA / HIP の verifier で判定される（`engine/src/core/verify.cpp:1417-1428`）。
- verify window が batch verifier ではないこと（`engine/src/core/verify.cpp:1532`）。
- PCIe share が 0 で、通常の動的 PCIe staging が無効であること。`device_hits_active()` はさらに all-resident graph、always-publish、remote optimization、adaptive gate、PCIe balance を除外する（`engine/include/strata/core/verify.hpp:439-442`）。serve の通常経路では layer split、peer/helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch`、`STRATA_ADAPT_OVERLAP=1`、0-slot cache、residency table 不在も対象外となる（`engine/src/program/generate.cpp:14960-14970`）。非 serve の generate 経路では layer split、peer tier、helper GPU、spec split、foresight swap、PCIe balance が対象外（`engine/src/program/generate.cpp:24464-24472`）。
- 明示した `--pcie-frac` は自動設定より優先する。CLI 値が未指定の `o.pcie_frac < 0` のときだけ起動時の PCIe share を決め、その段階でこの環境変数が非 0、native pack、single GPU、batch 指定なし、`STRATA_PCIE_FRAC_DEFAULT=old` でないなら `pcie_frac=0` にします。`--pcie-frac` を明示すればこの環境変数による強制は行われず、明示値が 0 の場合は 0 のままです（`engine/src/program/generate.cpp:5507-5514,5553-5560`）。
- serve の request `pcie_frac` は 0..1 に clamp されますが、起動時に `device_hits_active()` が有効になった verifier では各 request の PCIe 数を 0 に固定します。したがって request ごとの非 0 値もこの状態では適用されません（`engine/src/program/generate.cpp:18816,21335-21340`）。
- `STRATA_VERIFY_DEVICE_PLAN` は all-resident expert の device planning 用の別変数です。device plan 判定ではこれが設定済みなら `STRATA_VERIFY_DEVICE_HITS` より先に参照されます。ただし `device_hits_` はこの変数を別途読み、部分 VRAM hit planning の条件を独立に評価します（`engine/src/core/verify.cpp:1417-1428`）。

## 実行時の詳細

変数は `Verifier::init` の呼び出し時に verifier ごとに読み、`device_hits_` に保存されます。プロセスの `environ` を後から変更しても、初期化済み verifier の設定は更新されません（`engine/src/core/verify.cpp:1417-1428`）。expert dispatcher には別途、`STRATA_VERIFY_DEVICE_PLAN` またはこの変数の非 0 判定を関数内 `static` に保存する読み取りがあります。これは最初の dispatcher 呼び出し時に一度だけ評価され、GPU が処理する hit rows を host 側で先にゼロ化するかどうかを選びます（`engine/src/core/expert_source.cpp:5727-5735,5834`）。foresight swap は serve の初期化時に `STRATA_FS_SLOTS > 0` の場合だけこの変数を読み、device plan との併用を判定します（`engine/src/program/generate.cpp:14795-14805`、`engine/src/core/expert_source.cpp:7294-7305`）。generate 起動処理は未指定 PCIe share を決めるときにも環境変数を読み、該当条件で `o.pcie_frac` と `pcie_frac_auto` を変更します。ここで `STRATA_PCIE_FRAC_DEFAULT=old` は強制設定の適用を止めます（`engine/src/program/generate.cpp:5507-5514,5553-5559`）。

有効な window では verifier が各 layer の routed expert IDs と GPU residency table を `resident_hits_plan` に渡し、resident hit の GPU 計画を作ります。CPU 側 dispatcher は `device_hits_only` のとき resident hit group を host plan に積まず、その hit の `kind[]` を設定します。また dispatcher は通常の plan publish / fetch 処理を省略します（`engine/src/core/verify.cpp:2691-2695`、`engine/src/core/verify.cpp:4352-4356`、`engine/src/core/expert_source.cpp:5583-5619,5681-5696`）。

GPU hit 出力はゼロ初期化され、常駐 expert の結果を計算し、CPU が計算した miss rows と合成されます。resident hit 以外の routed experts は通常どおり CPU 側の miss 処理に残ります（`engine/src/core/expert_source.cpp:5361-5368,6030-6042,6074-6084`、device planner 呼び出し: `engine/src/core/verify.cpp:2686-2699`）。

`STRATA_FS_SLOTS` による foresight swap を有効にしていると、この方式とは併用できません。slots が正の場合、`STRATA_VERIFY_DEVICE_PLAN` またはこの変数が非 0 なら swap を止め、stderr に理由を出します（`engine/src/core/expert_source.cpp:7294-7305`）。

verifier 初期化時に device 用 slot offset buffer の確保・転送が失敗すると、`device_hits_` を false に戻して通常経路へ進みます。この分岐専用の警告はありません（`engine/src/core/verify.cpp:1439-1452`）。CUDA の `resident_hits_plan` に渡す entries が最大値を超えると `resident_hits_plan: %d entries, at most %d` を stderr に出して `exit(1)` し、kernel launch error も `resident_hits_plan: <CUDA error>` 形式で出して `exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:37-40,1851-1867`）。

## ログと測定値

実際に有効な `device_hits_active()` のときだけ stderr に次の行を出します（環境変数値が有効でも実行条件を満たさなければ出ません）。

```text
strata generate: STRATA_VERIFY_DEVICE_HITS=1: planning VRAM expert hits on-device (--pcie-frac 0: no plan/PCIe flag waits)
strata serve: STRATA_VERIFY_DEVICE_HITS=1: planning VRAM expert hits on-device (--pcie-frac 0: no plan/PCIe flag waits)
```

未指定 share を自動で 0 にした場合は、別の stderr 行 `strata generate: STRATA_VERIFY_DEVICE_HITS=1 -> pcie_frac 0.00 (on-device VRAM hit planning; pass --pcie-frac or STRATA_VERIFY_DEVICE_HITS=0 to override)` が出ます。NVIDIA 世代別の既定値を設定したときは `apply_nv_defaults` の既定スイッチ一覧ログに含まれます（`engine/src/program/generate.cpp:5553-5559,14966-14970,24468-24472`、`engine/src/core/nv_defaults.cpp:247-253`）。

`docs/DETAILS.md` にこの環境変数の記述は見つかりませんでした。ソースコード上の分岐・ログ以上の速度や出力品質の測定値はこの文書では主張しません。

## 根拠

- 値変換: `engine/include/strata/core/device_hits_plan.hpp:25-27`
- NVIDIA 既定値と利用者値優先: `engine/src/core/nv_defaults.cpp:37-42,73-74,75-106,129-135,176-179,214-233,247-253`
- 起動時の既定適用条件: `engine/src/program/generate.cpp:4416-4444`
- PCIe share の既定・上書き: `engine/src/program/generate.cpp:5507-5514,5553-5560`
- verifier の有効条件と計画: `engine/src/core/verify.cpp:1414-1428,2686-2699,4352-4356`; `engine/include/strata/core/verify.hpp:439-442`
- CPU dispatcher と GPU hit の合成: `engine/src/core/expert_source.cpp:5583-5619,5681-5696,6029-6084`
- serve / generate の実効条件とログ: `engine/src/program/generate.cpp:14960-14970,24464-24472`
- foresight swap との排他: `engine/src/core/expert_source.cpp:7294-7305`
