# `STRATA_HY4_VRAM_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の GPU loader が Section 4 の expert weights 用に見積もる VRAM budget を GiB 単位で指定する。値は通常の空き VRAM から `HY4_RESERVE_GB` 分を差し引いた値を置き換える。これによりロード時に VRAM に配置できる expert 数が変わり、残りは tiered loader の host/CPU/SSD 側に回る。trunk の配置や計算値そのものを直接指定する設定ではない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1434, 1486-1502`）。

## 値と判定

読み取りは `getenv` の設定有無を調べた後、選ばれた文字列を `atof` で変換する。空文字を含む設定値は「設定あり」として選ばれ、空文字や数値に変換できない文字列は `atof` の結果 0 となる。数値の後ろにある非数値文字は `atof` が変換できる先頭部分の後では検査されない。コードに範囲検証や clamp はない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1424-1429`）。

| 条件 | `STRATA_HY4_VRAM_GB` が未設定 | 変換例 | 0 以下の budget になる値の例 |
|---|---|---|---|
| `HY4_EXPERT_VRAM_GB` も未設定、通常の単一 GPU / 複数 GPU tiered load | 空き VRAMから `HY4_RESERVE_GB`（未設定なら 6.0 GiB）を引いた budget | `1`, `8.5`, `0.5GB`（`atof` が先頭数値を変換） | `0` は有効な 0 GiB 指定。`-1` は負 budget。空文字, `true`, `abc`, `0anything` は `atof` で 0 |
| `HY4_EXPERT_VRAM_GB` が設定済み | 対象変数は参照されず、`HY4_EXPERT_VRAM_GB` の値を使用 | 対象変数の設定は効果なし | 優先変数が空文字・不正文字列でも対象変数には fallback しない |

負値は直接 budget を負にし、全量配置条件を満たさず、tiered loader に渡す直前に 0 に丸められる。0 は明示的な VRAM expert budget 0 GiB。正の値は `1073741824` 倍して byte budget にする。数値文字列の全体一致、空白除去、大文字小文字、有限値、上限・下限の検査は行わない（同 `:1426-1429, 1434-1436, 1497-1499`）。

## 有効になる条件

- HIP/CUDA の HY4 GPU 実装を使い、モデルロード時に `with_experts` が true であること。CLI と server の両方が `load_gpu_model(..., true)` を呼ぶ（`engine/src/hy4flash/run/hy4_main.hip.cpp:659`, `engine/src/hy4flash/run/hy4_serve.hip.h:294`）。CPU・Metal・SYCL の別実装ではこの変数の読み取り箇所を確認できない。
- `HY4_EXPERT_VRAM_GB` が未設定であること。同変数が設定されていると、空文字でもそちらが優先される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1426-1427`）。
- `STRATA_HY4_DISTRIBUTED` ビルドで `g.expert_shard >= 0` の経路に入る場合、この変数を読む箇所より前に shard をロードして return するため適用されない（同 `:1400-1409`）。
- host-mapped trunk になった場合は、この変数の値にかかわらず expert budget が 0 に上書きされる（同 `:1431-1433`）。
- `--vram-experts-gb` が指定された場合、single-GPU tiered path ではその cap とこの変数由来の budget の小さい方が使われる。multi-GPU では CLI cap は全 GPU の配置上限に反映される（`engine/src/hy4_main.hip.cpp:451-454, 654-659`; `engine/src/hy4_gpu_model.hip.h:937-952`）。
- 単一の discrete GPU で expert 全量を VRAM に置くサイズの budget があっても `hipMalloc` / `cudaMalloc` が失敗すると、loader は現在の空き VRAMから `HY4_RESERVE_GB` を引いて budget を再計算し、tiered loading に切り替える。この再計算では本変数の値を維持しない（同 `:1434-1459, 1473-1482`）。

## 実行時の詳細

対象値は `load_gpu_model` の expert-loading 処理で読み取られ、プロセス起動時の静的 cache ではない。CLI 実行ではモデルロードの一回、server では server 初期化時のモデルロードで評価されるため、リクエストごとには再読込されない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1275, 1420-1429`; `engine/src/hy4flash/run/hy4_serve.hip.h:268-295`）。

通常は空き VRAMから `HY4_RESERVE_GB`（既定 6.0 GiB）を差し引いて予算を作るが、本変数または優先される `HY4_EXPERT_VRAM_GB` があればその数値がこの予算を置き換える。単一 GPU では全 expert section を置ける budget のとき全量 allocation を試し、それ以外は tiered loader に進む。tiered loader は expert を VRAM、pinned host memory、CPU/RAM、SSD の各 tier に配置し、必要な RAM 予算を超えると CPU + SSD cold-expert streaming を自動選択する（`engine/src/hy4_gpu_model.hip.h:1420-1436, 1486-1502`; tier 配置と RAM 判定は同 `:789-850, 1011-1044`）。

multi-GPU の tiered loader では本変数由来の budget は primary GPU の VRAM cap として渡され、peer GPU ごとの空き容量は別に計算される（同 `:792-803, 866-892`）。ただし `--vram-experts-gb` は別途全 GPU の総 cap として全 GPU の各 budget を比例縮小する（同 `:937-952`）。

## ログと測定値

この変数の値自体を表示する専用ログはない。全量 allocation に失敗すると stderr に `[load] full expert hipMalloc (...) failed; falling back to tiered loading`（CUDA 側では `cudaMalloc`）を出す。tiered loader の結果は `[load] experts 4-tier: ...`、複数 GPU では `[load] multi-GPU experts ...` として stderr に表示され、ロード失敗時は `experts: <理由>` を表示してロード関数が失敗する（`engine/src/hy4_gpu_model.hip.h:1453-1459, 1476-1482, 1251-1263, 1499-1505`）。性能測定値はこの変数に結びつく条件付き資料を確認できなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1429` — 分散 shard の早期 return、対象変数と優先変数の読み取り、budget の設定および CLI cap。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1431-1505` — host-mapped trunk による上書き、全量 allocation と fallback、tiered loader 呼び出し、結果ログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:789-850, 866-892, 1011-1044, 1251-1263` — tiered loader の配置・budget 適用とログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:451-454, 544-579, 649-659` — CLI の `--vram-experts-gb` 値と server / offline model load への伝達。
- `engine/src/hy4flash/run/hy4_serve.hip.h:268-295` — server 初期化時の model load。
