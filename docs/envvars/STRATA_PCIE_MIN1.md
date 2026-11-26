# `STRATA_PCIE_MIN1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

共有 multi-token expert dispatch の PCIe 割当数 `m` が 0 になったとき、条件を満たす layer-window に限り `m` を 1 に引き上げます。これにより、非 resident で CPU 側へ回る expert のうち最大 1 件が、既存の PCIe 経路へ割り当てられる余地を作ります。環境変数だけで PCIe 経路を有効化するものではなく、router の選択・重み・モデル設定自体も変更しません。読み取りと割当の補正は `expert_pool_dispatch_multi` 内です（`engine/src/core/expert_source.cpp:5426-5429,5543-5550`）。

## 値と判定

値は `std::getenv` で読み、`std::atoi(v) != 0` を真とします。厳密な文字列・数値検証はなく、`atoi` が先頭から変換できる整数部分で判定します（`engine/src/core/expert_source.cpp:5549`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `expert_pool_dispatch_multi` が PCIe 計画分岐に入り、初めて変数を評価 | `false` | `1`、`-1`、`2tail`、` 1`（`atoi` が非 0） | 空文字、`0`、`0anything`、`true`、`false`、整数に変換できない文字列（`atoi` が 0） |

空文字は未設定とは異なり `getenv` 自体は非 null ですが、`atoi("")` が 0 なので無効です。`atoi` は先頭の空白と符号を許し、数字列の後ろは判定に使いません。読み取り値は関数内 `static const` に保存されるため、同一プロセス内で読み取り後に環境を変更しても反映されません（同上）。

## 有効になる条件

- `expert_pool_dispatch_multi` が `d.plan != nullptr` かつ `n <= kMaxWindowEntries` かつ `n <= d.plan->cap` の計画分岐に入り、その中で初めて環境値を読み取る必要があります。条件を満たさない呼び出しでは変数の評価・効果はありません（`engine/src/core/expert_source.cpp:5475-5479,5549`）。
- `pcie_ok` が真である必要があります。これは `d.pcie_num > 0` または `d.pcie_model.on` のいずれかに加えて、現在 layer で `d.src->pcie_layer(d.layers)` が真である条件です。PCIe share がなく、balance model も off なら、この変数だけでは割当を作りません（`engine/src/core/expert_source.cpp:5543-5545`）。
- 現在の window の miss 数 `nmiss` は 2 以上、既存の `d.pcie_model.pick(...)` の結果 `m` は 1 未満である必要があります。`nmiss` は distinct な routed expert のうち host cache、peer GPU、remote helper のいずれにもないものから数え、`STRATA_ROUTE_TAIL_SKIP` による除外後の数です（`engine/src/core/expert_source.cpp:5481-5500,5510-5526,5545-5550`）。
- 選ばれた miss の blob が pin 済みでなければ PCIe transfer にはなりません。fetch 経路では候補選択時に pin 状態を確認し、それ以外の経路でも blob を得られたときだけ `kd = 1` として PCIe 用 fetch 配列に積みます。pin されていない miss は従来どおり CPU miss のままです（`engine/src/core/expert_source.cpp:5555-5571,5593-5606`）。
- `--pcie-frac` は既存 share の入力で、`generate.cpp` が `d.pcie_num` に変換します。`STRATA_PCIE_MIN1` はその値を置き換えるのではなく、既存の計算後に `m` が 0 のときだけ補正します。自動 PCIe balance の場合は `STRATA_PCIE_BALANCE=1` が `pcie_model.on` を有効にし得ますが、これは native pack・単一 GPU・batch 無効・`--pcie-frac` 未指定の条件に限られます（`engine/src/program/generate.cpp:4057,5535-5543,5590-5597,14931`; `engine/src/core/expert_source.cpp:5543-5550`）。

## 実行時の詳細

各 multi-token window で、まず miss に対する固定 share `((nmiss * d.pcie_num) >> 8)` と、利用可能なら `PcieModel::pick` の結果を使って `m` を決めます。その後、環境値が真で PCIe 経路が使用可能、`m < 1`、`nmiss >= 2` の場合だけ `m = 1` にします（`engine/src/core/expert_source.cpp:5543-5550`）。

fetch/admission 経路を使わない場合、miss を routing order で数え、最後の `m` 件を PCIe 候補とします。fetch 経路を使う場合は pin 済み候補を usage 順で選びます。どちらも `staging_cap`・64 件上限および実際の pin 状態に制約されます。PCIe 候補は `P.ptr2` / `P.start2` に計上され、plan publish 後に `P.fetch` を呼びます。満たせない場合、環境変数が真でも PCIe 件数は増えません（`engine/src/core/expert_source.cpp:5555-5571,5597-5606,5622-5635,5681-5695`）。

## ログと測定値

この変数専用の警告・エラー・ログはありません。生成時の集計では、`d.pcie_num > 0` の場合に stdout へ `pcie experts` として PCIe 経由で読んだ distinct expert 数の平均と share が表示されます。batch 集計では stderr の `strata batch: ... PCIe ...` に window 当たりの値が含まれます。これらは環境変数の有効化を直接表示するものではありません（`engine/src/program/generate.cpp:25356-25359,17495-17505`）。

## 根拠

- 候補名の実行コード上の読み取りは `engine/src/core/expert_source.cpp:5549` の1箇所。値の解釈と補正条件は同ファイル `:5543-5550`。
- PCIe 経路の可否、pin 確認、plan への反映は `engine/src/core/expert_source.cpp:5240-5267,5555-5571,5593-5606,5622-5635,5681-5695`。
- CLI share と自動 balance の関係は `engine/src/program/generate.cpp:4057,5535-5543,5590-5597,14931`。
- 観測可能な集計出力は `engine/src/program/generate.cpp:17495-17505,25356-25364`。
