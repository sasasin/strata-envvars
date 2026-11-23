# `IK2_GPUS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2 実行ファイルで使う GPU 数、または明示的な GPU ordinal のリストを指定する。通常の既定は1 GPUで、`IK2_GPUS` がその既定状態を置き換え、複数 GPU を必要とする Expert Parallelism (EP) を有効にできる。通常エンジンは CUDA/HIP 等の build、専用 `strata-inkling-sycl` は SYCL build で読む。これは Inkling-2 の設定であり、他の Strata エンジンやドライバーが読む環境変数の挙動はこの文書の対象外。読み取りは `engine/src/inkling2/ink_main.cpp:510-532` と `engine/src/inkling2/sycl/ink_sy_main.cpp:150-163`。

## 値と判定

どちらもプロセス起動後、CLI 引数をすべて読んだ直後に `std::getenv` で取得する。未設定または空文字では何もしない。数値変換は `std::atoi` で、文字列全体の妥当性を検査しない。したがって先頭の空白・符号と数値接頭辞を読み、数値以降の文字は無視する。変換結果が0以下なら GPU 数は `std::max(1, ...)` により1になる。例: `2junk` は2、`0`、`-2`、`true`、`0anything` は1。大文字小文字による判定はない。カンマを含む場合は数値リストとして扱い、空要素を飛ばす。通常エンジンでは `atoi` 変換後の負値を除き、重複も除く。一方、SYCL の環境変数経路では負値や重複を除かず、その数も GPU 数として渡す。通常エンジンの処理は `engine/src/inkling2/ink_main.cpp:511-532`、SYCL は `engine/src/inkling2/sycl/ink_sy_main.cpp:151-162`、SYCL CSV parser は同 `:19-29`。

| 入力・状態 | 通常エンジン (`ink_main.cpp`) | 専用 SYCL (`ink_sy_main.cpp`) |
|---|---|---|
| unset / 空文字 | 既定の `gpus=1`, ID リスト空を維持 | 既定の `req_gpus=1`, ID リスト空を維持 |
| `2` などカンマなし | `atoi` の結果を最低1にして GPU 数にする。ordinal は `--gpu` または0のまま | 同左 |
| `0,2` などカンマあり | 負値でない異なる ID を順に追加し、ID 数を GPU 数にする。空要素は飛ばす | `parse_csv_ints` で各非空要素を `atoi` し、ID 数を GPU 数にする |
| `,` | GPU 数1・空 ID リストのまま | GPU 数1・空 ID リストのまま |

カンマ付き要素にも `atoi` を使うため `1x,2` は両経路で `[1,2]`、`x,2` は `[0,2]` になる。通常エンジンでは `x,y` が `[0]`（無効文字列は `atoi` が0を返すため重複排除後に1 GPU）になるが、SYCL は `[0,0]` の2要素として渡す。`-1,-2` は通常エンジンでは負値を除いて空リストとなる一方、SYCL は負値2個を保持し、GPU 数2で backend に渡す。SYCL backend は primary を範囲内へ clamp し、secondary に使える ID がなければ別 GPU を探す (`engine/src/inkling2/sycl/ink_sy_common.h:792-805`)。空文字全体は早期条件で無視される。変換エラーを知らせる専用警告はない。`atoi` とリスト処理は `engine/src/inkling2/ink_main.cpp:511-531`、`engine/src/inkling2/sycl/ink_sy_main.cpp:151-162` にある。

## 有効になる条件

- `--gpus` / `--devices` が CLI で設定した結果、GPU 数が1より大きいか、明示 ID リストが空でなくなっている場合、環境変数の読み取り条件を満たさず無視される。CLI の `--gpus 1` は環境変数と同じ数値状態のため、環境変数を抑止しない。`--gpu N` 単独も抑止せず、環境変数のリスト指定ならその先頭 ID が `gpu_index` を置き換える。CLI 処理と guard は `engine/src/inkling2/ink_main.cpp:443-469,510-511`、SYCL は `engine/src/inkling2/sycl/ink_sy_main.cpp:128-141,150-151`。
- 通常エンジンでは GPU backend が選ばれている必要がある。`--cpu` または CPU のみの build では backend factory が CPU backend を返し、GPU 選択値は GPU 使用に結び付かない。build macro による CUDA / EP CUDA / HIP / Metal / SYCL backend の選択は `engine/src/inkling2/ink_backend.h:150-168`。
- CUDA backend は明示 ID のうち可視範囲内の異なる ID を最大4個使う。ID がない数値指定は選択 ordinal を先頭に、可視 GPU から最大4個を選ぶ。該当 GPU 数が揃わない場合でもこの処理自体は失敗にせず、得られた GPU 群を使う。`engine/src/inkling2/cuda/ink_cuda_backend.cu:104-131`。
- HIP backend は第一 ID（または `--gpu` / 0）を primary に使い、可視範囲へ clamp する。GPU 数が2以上または ID が2個以上で、可視 HIP device が2つ以上なら2-GPU EP を試みる。`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-580,602-615`。
- SYCL backend も2 GPU 以上を要求し、可視 SYCL GPU が2つ以上ある場合に EP setup を試す。ID リストから2つ目以降の可視で異なる ID を選び、該当しなければ primary 以外の0または1を選ぶ。GPU が1つしか見えない場合は単一 GPU に戻る。`engine/src/inkling2/sycl/ink_sy_common.h:784-835`。
- EP CUDA backend は `gpu_ids` リストを使わず、GPU 数が2以上なら2 GPU とし、`gpu_index` を先頭 GPU に使う。従って環境変数のカンマ付き ID 群は ID ごとの指定としては反映されない。`engine/src/inkling2/ep_dual_gpu.cu:732-734`。
- Metal backend は GPU ordinal / GPU 数を参照するコードが確認できず、この値による GPU 選択は確認できない。CPU / Metal を含め backend ごとの対応状況は build と factory 実装に依存する。`engine/src/inkling2/ink_backend.h:150-168`。

## 実行時の詳細

値はリクエスト単位や backend 呼び出しごとではなく、各実行ファイルの `main` で一度読み、設定構造体へ格納する。通常エンジンでは CLI parse 後・モード分岐前に読むため、`--selfcheck`、`--bench`、serve、通常生成など backend を初期化する経路へ渡る。`--info`、`--export-tokenizer` など GPU backend を初期化しない経路でも読み取り自体は行うが、選択値を使う処理へ進まない。通常エンジンの流れは `engine/src/inkling2/ink_main.cpp:503-533,544-579`。

環境値はプロセス起動中に再取得・cache 更新されない。起動後に環境を変更しても反映されず、子プロセスへの転送処理もこの環境変数については見つからない。専用 SYCL は同様に parse 後に値を適用し、モデル load に GPU 数と ID 群を渡す (`engine/src/inkling2/sycl/ink_sy_main.cpp:146-163,171-183`)。

カンマなしの値は GPU の ordinal ではなく GPU 数として扱う。たとえば `IK2_GPUS=2` は `--gpu` で選んだ GPU を先頭にした2 GPU 要求、`IK2_GPUS=0,2` は ordinal 0 と2のリスト要求となる。CUDA の具体的な採用上限・可視範囲処理は `engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131`、HIP の primary と2-GPU 条件は `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:575-615`。

## ログと測定値

`IK2_GPUS` の unset・空・不正値や CLI による抑止について、専用ログはない。SYCL で複数 GPU を要求したものの可視 GPU が不足する場合は `engine/src/inkling2/sycl/ink_sy_common.h:831-834` から stderr に `[ink_sycl] --gpus %d requested but only %zu SYCL GPU(s) visible; running single-GPU` を出す。SYCL の2 GPU queue 初期化が失敗した場合は同 `:827-830` で `[ink_sycl] Dual-GPU EP init on GPU%d failed (%s); falling back to 1 GPU` を出す。CUDA/HIP 側で観測される初期化エラーは backend の GPU API エラーで、環境変数専用のエラー文言ではない。新たな測定は行っていない。

`docs/MULTI_GPU.md:26` と `docs/DETAILS.md:283` は CLI の GPU 選択・複数 GPU の一般説明を載せているが、`IK2_GPUS` の値規則は説明していないため、本書の値・分岐の根拠には使っていない。この変数に対応した測定値も資料で確認できなかった。

## 根拠

- 環境変数の直接読み取りと CLI 優先条件: `engine/src/inkling2/ink_main.cpp:443-469,505-532`; `engine/src/inkling2/sycl/ink_sy_main.cpp:128-162`。
- 設定の用途: `engine/src/inkling2/ink_backend.h:17-24`。
- CUDA / HIP / SYCL の適用: `engine/src/inkling2/cuda/ink_cuda_backend.cu:104-131`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-615`; `engine/src/inkling2/sycl/ink_sy_common.h:784-835`。
- EP CUDA と build backend 選択: `engine/src/inkling2/ep_dual_gpu.cu:732-734`; `engine/src/inkling2/ink_backend.h:150-168`。
