# `--resident-budget-gib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。生成・serve の両経路） |
| オプション | `--resident-budget-gib` |
| 別名 | `--ram-experts-gb` |
| 値 | 数値 `N`。GiB として扱う。`N >= 0`。 |

## 役割

GPU の expert cache に入らない experts のうち、expert profile の順位が高いものから最大 `N` GiB を RAM に置き、残りは model files（mmap または選択された file tier）から読むための上限を指定します。GPU と file tier の間に RAM の resident 層を設けたい場合に使います。`N = 0` は特別扱いで、RAM 層を設けない SSD/file-only モードになります。

## 使い方

```sh
# モデルの expert cache 外から、上位最大 32 GiB を RAM に置いて生成する
strata --pack /path/to/model --resident-budget-gib 32 --tokens 1,2,3

# 同じ設定を alias で指定する（値の単位も GiB）
strata --pack /path/to/model --ram-experts-gb 32 --tokens 1,2,3

# RAM の expert 層を使わず、GPU cache 外の experts を file tier から読む
strata --pack /path/to/model --resident-budget-gib 0 --tokens 1,2,3
```

## 値と既定値

- 値は必須です。次の引数がない場合、共通の `next()` が `--resident-budget-gib needs a value` を stderr に出して終了コード 2 で終了します。
- parser は `std::atof` で読み、`N >= 0` を検査します。負数と NaN は `strata generate: --resident-budget-gib needs N >= 0`（alias 指定時は alias 名）を stderr に出し、終了コード 2 で拒否します。`atof` が数値として読めない文字列を 0 と解釈した場合は、0 の分岐に入ります。
- 既定値は `0` ですが、これはオプションを省略したときの `resident_budget` 初期値です。省略だけで `--ssd-experts` が有効になるわけではなく、明示した `--resident-budget-gib 0` が SSD/file-only モードを選択します。
- 正の値は `N * 1,073,741,824` bytes に変換されます。整数 GiB に限定する検査はなく、小数も受理されます。
- 同一オプションの複数回指定や他の residency オプションとの組み合わせについて、重複を拒否する検査はありません。各引数を順に処理し、関連する状態を更新します。`--resident-experts`、`--ssd-experts` と併用する場合は、それぞれが更新する状態も関わるため、単純な「最後のフラグが全設定を置き換える」挙動とは限りません。

## 実行時の動作

- 正の `N` では `mmap_experts` と `resident_cpu_experts` を有効にし、resident copy を page-locked にするかどうかは `STRATA_RESIDENT_PIN` で選びます（値が文字列 `0` の場合だけ pageable）。headroom は通常 4 GiB で、`STRATA_RESIDENT_HEADROOM_GIB` に非負値がある場合はその値になります。`--ram-keep-gib` または `STRATA_RAM_KEEP_GIB` が有効なら、明示的な `STRATA_RESIDENT_HEADROOM_GIB` がない限り headroom は RAM keep 値以上に引き上げられます。
- expert cache 外の experts を profile 順に調べ、各 expert が予算内に収まるものを RAM にコピーします。予算に収まらないものは mapped files に残ります。Windows では物理 RAM に加えて commit 容量も上限になります。multi-GPU layer split の prompt lend regions も同じ予算の範囲で扱われます。
- 実際の空き RAM または Windows commit 容量が指定値より少ない場合、利用可能量から headroom と 0.25 GiB の余裕を差し引いて予算を clamp し、stderr に縮小内容を出します。Windows の複数 CUDA GPU では WDDM shared segment による追加の上限が適用される場合があります。Windows HIP の一部 UMA/batch 条件でも、resident copy の上限がさらに調整される場合があります。
- resident copy を作れない場合、明示予算モードは起動を直ちに中止せず、GPU cache 外の experts を model files から読む fallback に進み、stderr に警告します。実際の RAM copy の大きさに応じて Linux/Windows では file tier の buffered/unbuffered 読み込みを再評価します。
- 明示値 `0` は parser 上 `ssd_experts` と `mmap_experts` を有効にし、resident RAM copy を無効にします。file tier の読込み形式や詳細は OS・モデル配置で異なります。

## 適用条件と副作用

- 効果があるのは、エンジンが expert model を読み、GPU expert cache 外の領域を処理する経路です。GPU cache が全 experts を保持する場合、RAM に置く補集合がなく、この指定による resident experts のコピーはありません。
- RAM copy は大きな host memory allocation を行い、既定では page-locked です。空き RAM・commit・headroom の条件に応じて縮小または fallback し、RAM が足りない場合は残りを model files から読むため、読み込み経路と速度に影響します。
- 0 の SSD/file-only 経路では、resident RAM arena を確保せず、file tier から必要な experts を読み込みます。実際の I/O 方式はエンジンが選択し、利用可能なコード根拠から全 OS で同一とは確認できません。
- `--ram-experts-gb` は parser 上の alias です。名前に `gb` とありますが、この分岐でも値を GiB として byte 換算します。

## 出力とエラー

- 有効な正の予算を適用すると、RAM に収めた experts 数・予算と残りを files から読む旨が stderr に出力されます。空きメモリに合わせて縮小した場合は `FileExpertSource: --resident-budget-gib ... exceeds available ...` 形式の行も出ます。
- 空きメモリを取得できない場合や、GPU cache が未準備など copy 側の条件が満たされない場合、resident copy の作成は失敗します。明示予算モードでは警告を出し file-backed 読み込みへ fallback します。詳細エラー文字列には、失敗した条件が含まれます。
- `N < 0`、NaN、値の欠落は終了コード 2 です。数値変換後の値域を上限検証する処理は確認できません。

## 根拠

- `engine/src/program/generate.cpp:888-894` — residency 関連の状態と予算の役割。
- `engine/src/program/generate.cpp:3842-3849` — 共通 parser の必須値処理と `--help`。
- `engine/src/program/generate.cpp:4220-4257` — `--resident-experts`、`--ssd-experts`、対象オプションと alias の parser、validation、状態更新、単位換算。
- `engine/src/program/generate.cpp:4277-4285` — `--ram-keep-gib` / 環境変数と headroom の関係。
- `engine/include/strata/core/resident_ram_copy.hpp:11-15` — `STRATA_RESIDENT_PIN` の既定値と pageable 指定。
- `engine/include/strata/core/expert_source.hpp:774-799` — RAM copy と順位付き予算選択の契約。
- `engine/src/core/expert_source.cpp:3985-4024` — copy 前提条件と GPU cache 外補集合の作成。
- `engine/src/core/expert_source.cpp:4040-4105` — 空き RAM/commit による clamp、警告、および Windows WDDM 上限。
- `engine/src/core/expert_source.cpp:4131-4151` — profile 順に予算内の experts を選択し、結果を stderr に出す処理。
- `engine/src/program/generate.cpp:8650-8686` — resident budget / SSD mode による file tier 読み込み選択。
- `engine/src/program/generate.cpp:12077-12117` — copy 呼び出し、失敗時の fallback、および警告。
- `engine/src/program/generate.cpp:12054-12075` — Windows HIP の特定 batch/UMA 条件における resident copy 上限。
- `engine/src/program/generate.cpp:12203-12217` — resident copy 不成立時の file-backed fallback 出力。

調査範囲は指定 revision の Strata 所有ソースです。`--help` 実行や build は行っていません。
