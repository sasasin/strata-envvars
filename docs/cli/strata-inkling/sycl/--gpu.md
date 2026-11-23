# `--gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling-sycl` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU の整数 ordinal。省略時は `0` |

## 役割

SYCL バックエンドがモデル処理に使う GPU を選びます。番号は SYCL が列挙した GPU の配列に対する 0 始まりの添字として使われます。複数 GPU での Expert Parallelism の台数・明示 ID は `--gpus`（alias `--devices`）側の設定です。

## 使い方

```sh
strata-inkling-sycl --model ./model.strata --gpu 1
```

モデルを読み込み、列挙された GPU の ordinal 1 を選ぶ例です。実際の列挙順や選択可能なデバイスは SYCL backend と `ONEAPI_DEVICE_SELECTOR` の設定に依存します。

## 値と既定値

- 初期値は `0` です。値は `std::atoi` で整数化されます。範囲・形式を検証する処理はなく、整数として解釈できない文字列は `atoi` の結果（通常 `0`）になります。`--gpu` の後に値がない場合も空文字列が渡され、結果は `0` です。`engine/src/inkling2/sycl/ink_sy_main.cpp:103-106,112-114,128`
- 負数は `set_primary_gpu_index()` で `0` に補正されます。大きすぎる値も、GPU queue を作るときに列挙数の末尾へ丸められます。`engine/src/inkling2/sycl/ink_sy_main.cpp:164`; `engine/src/inkling2/sycl/ink_sy_common.h:76-78,119-128`
- 複数回指定した場合、parser は引数を左から処理し、最後に現れた `--gpu` の値が残ります。ただし後続または先行する `--gpus` の CSV 値との関係は次節のとおりです。`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`

## 実行時の動作

parser は値を `gpu_index` に格納し、引数処理後に `set_primary_gpu_index(gpu_index)` へ渡します。モデルロード中に GPU queue が初期化されると、`enum_gpu_devices()` が `ONEAPI_DEVICE_SELECTOR` 未設定時に `INK_SYCL_BACKEND=opencl` なら `opencl:gpu`、それ以外なら `level_zero:gpu` をプロセス環境に設定して GPU を列挙します。queue はその列挙結果の `gpu_index` 番目（範囲外なら末尾）のデバイスを使います。`engine/src/inkling2/sycl/ink_sy_main.cpp:164,171-183`; `engine/src/inkling2/sycl/ink_sy_common.h:94-116,119-128`

`ONEAPI_DEVICE_SELECTOR` がすでに設定されている場合、列挙関数はそれを上書きしません。その selector が見せるデバイス群の中で ordinal が解釈されます。`--gpu` 自体が selector を変更する処理はありません。`engine/src/inkling2/sycl/ink_sy_common.h:94-100,119-128`

GPU 2 台以上の実行を `--gpus` で要求した場合、loader は `--gpu` の選択を第 1 GPU として使います。`--gpus 0,1` のような CSV 指定は parser が先頭 ID で `gpu_index` を更新するため、CSV より後ろに `--gpu` を置けばその値が第 1 GPU を上書きします。`--gpus 2` のような台数指定は `gpu_index` を変更しません。`engine/src/inkling2/sycl/ink_sy_main.cpp:128-140`; `engine/src/inkling2/sycl/ink_sy_common.h:784-810`

`IK2_GPUS` は、引数処理後も要求台数が 1 かつ GPU ID リストが空の場合に読み取られます。このため `--gpu` を指定しても環境変数の読み取りは抑止されません。環境変数が CSV ならその先頭 ID が `gpu_index` を上書きし、単一の数値なら要求台数だけを設定します。CSV ID の妥当性は loader 側で確認され、無効な第 2 GPU ID は採用されず、別の GPU が選ばれる場合があります。`engine/src/inkling2/sycl/ink_sy_main.cpp:146-164`; `engine/src/inkling2/sycl/ink_sy_common.h:792-805`

## 適用条件と副作用

この文書の対象は `engine/src/inkling2/sycl/ink_sy_main.cpp` の SYCL 単体 CLI です。同じ `--gpu` を持つ `engine/src/inkling2/ink_main.cpp` の共通 Inkling CLI や、`SyclInkBackend::init()` が `apply_gpu_index()` を呼ぶ backend 経路の処理とは別です。単体 CLI は `set_primary_gpu_index()` を呼び、loader 内で GPU を列挙します。`engine/src/inkling2/sycl/ink_sy_main.cpp:101-105,128,164`; `engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-71`; `engine/src/inkling2/sycl/ink_sy_common.h:76-92`

`--gpu` は単体ではプロセス内の GPU ordinal を選びます。複数 GPU が要求されても可視 GPU が 2 台未満なら、loader は stderr に警告を出して単一 GPU へフォールバックします。`engine/src/inkling2/sycl/ink_sy_common.h:792-834`

## 出力とエラー

GPU 番号専用の入力エラーや範囲エラーは実装されていません。モデルロードが失敗すると CLI は stderr に `[ERROR]` と loader のエラーを出し、終了コード `1` を返します。GPU 2 台以上を要求したのに可視 GPU が 1 台未満の場合はエラー終了ではなく、stderr に警告して単一 GPU にフォールバックします。`engine/src/inkling2/sycl/ink_sy_main.cpp:171-183`; `engine/src/inkling2/sycl/ink_sy_common.h:827-834`

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — SYCL 単体 CLI の parser、初期値、`--gpu` と `--gpus` の設定。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:146-183` — `IK2_GPUS` の適用条件、GPU index の確定、モデルロードおよび失敗時の出力。
- `engine/src/inkling2/sycl/ink_sy_common.h:71-128` — primary GPU index の補正、backend/selector に応じた GPU 列挙と queue 選択。
- `engine/src/inkling2/sycl/ink_sy_common.h:784-834` — 複数 GPU の選択、利用可能 GPU 不足時のフォールバック。
- `docs/cli/README.md:1572-1580` — `strata-inkling-sycl` の scope と `--gpu` の索引リンク。

調査ではソースコードのみを参照しました。GPU の実際の列挙順・利用可能デバイス、SYCL runtime が selector や queue 作成時に返す詳細なエラーは環境依存のため、この checkout のソースだけでは確定できません。
