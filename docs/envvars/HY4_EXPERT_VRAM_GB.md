# `HY4_EXPERT_VRAM_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 GPU runner が expert Section 4 を VRAM に置くための予算（GiB）を指定する。設定されると、GPU 空き容量から `HY4_RESERVE_GB` を引く自動予算を置き換える。単一 GPU で Section 4 全体以上の予算なら全体を一括ロードし、それ未満、または複数 GPU の場合は tiered 配置の VRAM budget として使う。残りの expert は pinned host memory、CPU/RAM、または SSD tier に回り得る。この変数自体は配置方式を強制せず、生成内容や expert 選択を変更する処理もない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1436,1486-1505`; tiered 配置: 同 `:792-875,1084-1110,1251-1264`）。

読み取りは同じ HY4 実装を使う CUDA と HIP の両 build に含まれる（`engine/src/hy4flash/run/hy4_gpu.h:1-9,17-23,324-330`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `HY4_EXPERT_VRAM_GB` が設定済み | 同名変数が未設定の場合のみ `STRATA_HY4_VRAM_GB` を調べる。両方未設定なら空き VRAM から `HY4_RESERVE_GB`（未設定時 6.0 GiB）を差し引く | `atof` が正の数を返す文字列。例: `1`, `1.5`, `2GiB`（数値 prefix の `2` を変換） | 空文字、`0`, `0anything`, `true`, 数値で始まらない文字列は `atof` が 0 を返し、予算 0。`-1` は負の予算となり、tiered loader に渡す際 0 に丸められる |

取得は `getenv("HY4_EXPERT_VRAM_GB")` の非 null 判定で行い、その後 `atof` で変換する。新しい名前が空文字または無効な文字列でも「設定済み」なので旧名 `STRATA_HY4_VRAM_GB` には fallback しない。文字列全体の検証、suffix 検証、明示的な範囲制限はない。`atof` が読む数値 prefix 以降は検査されない。環境変数の数値は `1073741824.0` 倍され byte budget になる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1424-1429`）。

資料との照合では、Strata の `docs/SETTINGS.md:114` に旧名 `STRATA_HY4_VRAM_GB` は掲載されているが、この現行名は掲載されていない。`docs/DETAILS.md` にこの HY4 budget 変数の説明は見当たらない。上記の動作はソース実装に基づく。

CLI の `--vram-experts-gb` は parser 初期値 `-1.0`。単一 GPU で値が 0 以上なら環境変数で得た budget との小さい方を使うため、CLI は cap として優先する。CLI が負値ならこの cap は適用されない。peer GPU がある場合はこの箇所の単一 GPU cap は通らず、その後 `--vram-experts-gb` の総量 cap を各 GPU の budget に比例適用する（`engine/src/hy4flash/run/hy4_main.hip.cpp:367,451-454,654-659`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1426-1432,937-952`）。

## 有効になる条件

- `load_gpu_model(..., true)` で expert を読み込む経路で評価される。通常 CLI は `engine/src/hy4flash/run/hy4_main.hip.cpp:659`、serve は `engine/src/hy4flash/run/hy4_serve.hip.h:291-296` からこの経路に入る。
- `g.h_trunk_mapped` が非 null の場合は、この変数や CLI cap による budget をさらに 0 にする（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1431-1433`）。
- 単一 GPU かつ予算が page-aligned Section 4 全体以上なら一括ロードを試みる。それ以外は tiered loader に進み、予算で VRAM に配置する expert を制限する。複数 GPU ではこの一括ロード条件を満たさない（同 `:1434-1486`）。
- 全体一括 allocation が失敗すると stderr に `[load] full expert hipMalloc (...) failed; falling back to tiered loading`（HIP）または `[load] full expert cudaMalloc (...) failed; falling back to tiered loading`（CUDA）を出し、空き容量から `HY4_RESERVE_GB` を引いた予算を再計算する。この fallback では先に読んだ `HY4_EXPERT_VRAM_GB` と CLI cap を再適用しない（同 `:1449-1459,1473-1482`）。
- `HY4_CPU_EXPERTS` は VRAM budget ではなく、VRAM に置けなかった host expert を CPU 計算にするかの選択に関わる。未設定時は host expert 量・RAM 量・CPU 能力（Windows では別の閾値も含む）で既定モードを決める（同 `:1486-1499`）。

## 実行時の詳細

`load_gpu_model` の expert 読み込み時に現在の GPU 空き byte 数を取得する。UMA では先に trunk 分を空き量から差し引き、未設定時の基準予算を `free - HY4_RESERVE_GB * 2^30`（予約変数も未設定なら 6 GiB）とする。`HY4_EXPERT_VRAM_GB` があればその値がこの基準予算を置き換え、なければ旧名 `STRATA_HY4_VRAM_GB` を使う。したがって明示値は初期予算計算で reserve を差し引かない。次に単一 GPU では CLI cap との min を取り、mapped trunk なら 0 にする（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1434`）。

十分な予算があれば単一 GPU で全 expert Section 4 の allocation と読み込みを試す。予算不足または複数 GPU の場合、tiered loader は budget を `size_t` にし、最も hot な expert から static VRAM arena に配置する。単一 GPU の CPU mode では条件に応じて予算の一部を adaptive VRAM slots に分ける。残りは pinned host、RAM/CPU、または RAM 予算を超えた cold SSD に分類される（同 `:1434-1503,792-875,1084-1110`）。

環境値は `load_gpu_model` の呼び出しごとに読み直され、関数 static cache はない。通常の CLI 起動・serve 起動ではこのモデル読み込み時に評価されるため、モデルロード後の環境変更で既に決まった配置は再計算されない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1275,1420-1429`; 呼び出し元: `engine/src/hy4flash/run/hy4_main.hip.cpp:658-659`, `engine/src/hy4flash/run/hy4_serve.hip.h:291-296`）。

## ログと測定値

単一 GPU の tiered 配置が完了すると stderr に `[load] experts 4-tier: ... static VRAM ... + ... adaptive VRAM slots ...` の要約が出る。複数 GPU の場合は `[load] multi-GPU experts (...)` の要約になる。設定値そのものを表示する専用ログは見当たらない。tiered loader が false を返す場合は呼び出し元が `experts: <理由>` を stderr に出してモデル読み込みを失敗させ、CLI は終了コード 1、serve は `ERR cannot load <model>` を返して終了コード 1 となる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1251-1264,1499-1502`; `engine/src/hy4flash/run/hy4_main.hip.cpp:658-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:294-296`）。この変数固有の測定値は Strata 資料に見当たらない。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu.h:1-9,17-23,324-330` — HY4 の共通 CUDA/HIP build 条件。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1436,1449-1482` — free VRAM、reserve、対象変数と旧名の優先、CLI cap、mapped trunk、全体 allocation と失敗時の再計算。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-875,1084-1110,1251-1264,1499-1505` — tiered 配置、host/SSD fallback、結果ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:367,451-454,654-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:291-296` — CLI 値の既定・引き渡しと CLI/serve の読み込み経路。
