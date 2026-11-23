# `IK2_EP_SPLIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling2 の CUDA/HIP/SYCL デュアル GPU Expert Parallelism（EP）で、ハッシュに基づいて GPU 1 側へ優先配置する expert の割合を指定する。値 `0.3` はハッシュ値の 30% を GPU 1 に割り当てる優先値となる。VRAM の空き容量が足りない場合は別 GPU へ割り当てるか、ホスト側へ置かれるため、実際の配置数が指定割合と一致する保証はない（`engine/src/inkling2/ep_dual_gpu.cu:926-958`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1097`; `engine/src/inkling2/sycl/ink_sy_common.h:837-860`）。

## 値と判定

CUDA/HIP 共通入口と SYCL 入口が、それぞれ起動時に `std::getenv` で取得する。変数が未設定、または空文字なら読み飛ばす。空でない値は `std::atof` で変換し、変換結果 `v` が厳密に `0 < v < 1` の場合だけ採用する。文字列全体の妥当性検査はなく、`atof` が数値として読める先頭部分を変換する。従って `0.25tail` は `0.25` として採用され、`0`、`1`、`-0.1`、`1.1`、`true`、変換不能文字列は採用されず既定値または CLI 値を保つ。先頭空白は `atof` の変換規則に従い、`0.25` のような範囲内数値は採用される。大文字小文字は判定しない（`engine/src/inkling2/ink_main.cpp:470-472,505-509`; `engine/src/inkling2/sycl/ink_sy_main.cpp:142-148`）。

| 入口 | 未設定・空文字 | 有効な値 | 無効な値 |
|---|---|---|---|
| CUDA/HIP 共通入口 | 既定 `0.5`、または先に指定した `--ep-split` の値 | `atof` の結果が `0` より大きく `1` より小さい値。例: `0.25`, `0.25tail` | CLI 値または既定値を維持。例: `0`, `1`, `-0.1`, `true`, 変換不能文字列 |
| SYCL 入口 | 既定 `0.5`、または先に指定した `--ep-split` の値 | 同上 | 同上 |

CLI の `--ep-split` は先に解析され、環境変数の有効値があれば上書きされる。環境値が未設定・空・範囲外・変換不能なら CLI 値が残る。CLI 値自体は `atof` で読み込むが、環境変数と同じ範囲検査を入口では行わず、EP backend が採用時に `0.1` から `0.9` に clamp する（`engine/src/inkling2/ink_main.cpp:470-472,505-509`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:578-580`; `engine/src/inkling2/ep_dual_gpu.cu:732-735`; `engine/src/inkling2/sycl/ink_sy_common.h:784-789`）。

## 有効になる条件

- `--gpus 2`（または対応する複数 GPU 指定）か、既定の GPU 数が 1 のとき `IK2_GPUS` で複数 GPU を指定し、利用可能な GPU が2台以上あること。`IK2_EP_SPLIT` 自体は GPU 数を変更しない。`--gpus` 等で明示指定された GPU 数・ID が `IK2_GPUS` の適用条件より優先される（`engine/src/inkling2/ink_main.cpp:436-468,510-533`; `engine/src/inkling2/sycl/ink_sy_main.cpp:129-162`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-615`; `engine/src/inkling2/sycl/ink_sy_common.h:792-835`）。
- 実行ファイルに CUDA、HIP、または SYCL backend が組み込まれ、選択されていること。`--cpu` は CPU backend を選び、そこでこの割合による GPU 分割は行われない。ビルド macro による backend 選択は `engine/src/inkling2/ink_backend.h:131-168` にある。
- モデル読込・backend 初期化を行う実行経路であること。通常の生成、serve、selfcheck、bench は backend を初期化する。`--info` と tokenizer export はその前に終了するため、この値を backend に適用しない（`engine/src/inkling2/ink_main.cpp:544-572`; SYCL は `engine/src/inkling2/sycl/ink_sy_main.cpp:171-183`）。
- SYCL は2台目デバイスの queue 作成と正の VRAM budget が成立したときに EP を有効にする。初期化に失敗すれば1 GPUへ fallback し、GPUが1台しか見えなければ要求数不足のログを出す。HIP/CUDA も実際に2 GPU が選ばれた場合にのみ割合を使う（`engine/src/inkling2/sycl/ink_sy_common.h:792-835`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-683`; `engine/src/inkling2/ep_dual_gpu.cu:727-735`）。

## 実行時の詳細

環境変数はプロセス起動後、引数解析の直後に一度読み取られ、後続のリクエストごとには再評価されない。CUDA/HIP 共通入口では `BackendOpts::ep_split` に格納し、選択された CUDA/HIP backend に渡す。SYCL 入口は同様に `ep_split` を読み、モデルの `load` に渡す。実行中の環境変更がこの値に反映されるコードや、この値を子プロセスへ渡す処理はない（`engine/src/inkling2/ink_main.cpp:470-472,505-509,564-568`; `engine/src/inkling2/sycl/ink_sy_main.cpp:142-148,183`; `engine/src/inkling2/ink_backend.h:150-168`）。

CUDA EP、HIP EP、SYCL EP は受け取った値を `0.1..0.9` に制限して expert ごとのハッシュから GPU 1 優先配置を決める。空き VRAM 予算を超える expert は空きのある側へ回すかホスト配置になるため、指定値は配置の優先比率であって厳密な割当比率ではない（`engine/src/inkling2/ep_dual_gpu.cu:926-958`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1101`; `engine/src/inkling2/sycl/ink_sy_common.h:837-880`）。CUDA の別 runner 経路では、EP が有効で入力 split が既定値 `0.5` 近傍、かつ GPU 1 の空きが GPU 0 より 512 MiB 超多い場合、`eff_split` を VRAM 比率から `0.50..0.625` に調整する（`engine/src/inkling2/cuda/ink_runner.cuh:1173-1177`）。

## ログと測定値

変数の設定値そのものを入口で報告するログや、範囲外値への警告はない。CUDA EP backend の初期化成功時は stderr に `[inkling2-ep] Loaded ... | gpus=... (p2p=..., ep_split=...) ...` を出し、有効な EP と採用 split を表示する（`engine/src/inkling2/ep_dual_gpu.cu:1064-1068`）。HIP EP も初期化成功時に `ep_split` を含むロード情報を出す（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1324-1330`）。初期化エラーは通常入口では `init: <理由>`、serve では `ERR init: <理由>` として出力される（`engine/src/inkling2/ink_main.cpp:564-568`）。

`docs/DETAILS.md` にこの変数の記載は見つからず、条件付き測定値も確認できなかった。

## 根拠

- 候補名の直接読み取り全件: `engine/src/inkling2/ink_main.cpp:505-509`, `engine/src/inkling2/sycl/ink_sy_main.cpp:146-149`。
- 引数優先順位と共通の既定値: `engine/src/inkling2/ink_main.cpp:436-472,505-509`; SYCL の既定値と引数: `engine/src/inkling2/sycl/ink_sy_main.cpp:107,129-148`。
- backend への伝播と backend 選択: `engine/src/inkling2/ink_main.cpp:564-568`; `engine/src/inkling2/ink_backend.h:150-168`; `engine/src/inkling2/sycl/ink_sy_main.cpp:183`。
- CUDA/HIP/SYCL の EP 条件・split 利用: `engine/src/inkling2/ep_dual_gpu.cu:727-735,926-958`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-615,1064-1101`; `engine/src/inkling2/sycl/ink_sy_common.h:784-835,837-880`。
