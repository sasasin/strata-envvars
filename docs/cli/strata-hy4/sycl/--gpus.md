# `strata-hy4-sycl --gpus`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL backend） |
| オプション | `--gpus` |
| 別名 | `--devices` |
| 値 | GPU 数、または GPU index のカンマ区切り。例: `2`、`0,1` |

## 役割

SYCL で列挙された GPU のうち、主 GPU と追加の peer GPU を選びます。主 GPU は推論キューに使われ、追加 GPU は expert の配置先として初期化されます。追加 GPU が常に推論全体を分割実行する指定ではありません。

## 使い方

```sh
# GPU 0 を主 GPU、GPU 1 を追加 peer GPU として serve を起動
strata-hy4-sycl --serve --native model.strata --gpus 0,1

# GPU 0 を主 GPU とし、列挙順の GPU から合計 2 台を選択
strata-hy4-sycl --serve --native model.strata --gpus 2
```

## 値と既定値

- `--gpus` と `--devices` は同じ値を受け取ります。引数がない場合は指定した表記に応じて `ERR --gpus needs a value` または `ERR --devices needs a value` を標準出力に出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:108-115,135-136`）。
- 値にカンマが含まれる場合は GPU index の列として扱います。空要素は読み飛ばし、重複 index は一度だけ採用します。有効な index のうち最初が主 GPU、以後が peer GPU です（`engine/src/hy4flash/sycl/sy_common.h:123-143`）。
- カンマを含まない値は台数として `atoi` で整数化され、1 から可視 GPU 数の範囲に丸められます。`0` や負数は 1 台、可視数を超える値は可視 GPU 全台になります。主 GPU 以外から列挙順に追加します（`engine/src/hy4flash/sycl/sy_common.h:144-151`）。
- 省略時は環境変数 `HY4_GPUS` の値を初期値として使い、CLI で `--gpus` / `--devices` を指定するとその値で置き換えます。同じオプションを複数回指定した場合は、引数走査で最後に現れた値が残ります。どちらも空なら単一 GPU 指定 `--gpu` があればそれを主 GPU に、なければ GPU index `0` を主 GPU にし、peer GPU は指定しません（`engine/src/hy4flash/sycl/sy_main.cpp:93-95,105-115,130-136,199-213`）。環境変数の詳細は [HY4_GPUS](../../../envvars/HY4_GPUS.md) を参照してください。

## 実行時の動作

GPU 一覧は SYCL GPU device から取得され、既定では Level Zero、`HY4S_BACKEND=opencl` の場合は OpenCL backend の device に絞られます。該当 backend が見つからなければ、列挙先頭 device と同じ backend の device 群へ fallback します（`engine/src/hy4flash/sycl/sy_common.h:94-112`）。index はこの絞り込み後の一覧に対する 0 始まりの番号です。

`--gpus` の CSV 値に範囲外 index があると、その要素を標準エラーに `[gpu] ignoring out-of-range device index ...` と出して無視します。有効な要素が残れば先頭を主 GPU とします。数値指定は主 GPU と追加 GPU の合計台数です。`--gpu N` と併用した数値指定では `N` を主 GPU とし、CSV 指定では CSV の先頭が `--gpu` の値を置き換えます（`engine/src/hy4flash/sycl/sy_main.cpp:199-205`、`engine/src/hy4flash/sycl/sy_common.h:123-151`）。

主 GPU index は選択状態に保存され、SYCL queue の device 選択に使われます（`engine/src/hy4flash/sycl/sy_common.h:85-92,154-175`）。serve と通常実行の双方で peer index が expert 初期化へ渡され、peer GPU には主 GPU の VRAM cache にない expert を割り当てます（`engine/src/hy4flash/sycl/sy_main.cpp:226-248,280-309`、`engine/src/hy4flash/sycl/sy_serve.h:280-288`、`engine/src/hy4flash/sycl/sy_graph.h:144-153`）。

## 適用条件と副作用

- 実際に利用できる device は backend 選択や SYCL の可視 device に依存します。device がない場合、台数形式は可視数に対して clamp されますが、空の一覧では peer 選択はできません。
- peer index があっても可視 GPU が 2 台未満なら、peer expert は無効化され、その旨を標準エラーに出して処理を続けます。peer queue の生成に失敗した GPU も標準エラーに記録して飛ばします。利用可能な peer GPU では推論プロセス内に別 SYCL queue を作り、expert 用 device memory を確保します（`engine/src/hy4flash/sycl/sy_peer.h:182-194,231-259`）。
- peer GPU の初期化中にモデルファイルを開けない、または expert directory が不正な場合は初期化に失敗します。通常実行では `experts: ...` を標準エラーに出して終了コード `1`、serve の line protocol では `ERR experts: ...` を返して終了コード `1` になります（`engine/src/hy4flash/sycl/sy_peer.h:196-203`、`engine/src/hy4flash/sycl/sy_main.cpp:301-306`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`）。

## 出力とエラー

範囲外 CSV index は標準エラーに警告を出してスキップされます。GPU 自体が可視でない場合や queue が作れない場合の最終的な成否は、SYCL runtime および後続初期化の経路に依存し、CLI parser による一律の拒否処理は確認できません。値は `atoi` で変換されるため、数字以外を含む値に対する厳密な書式検証はありません（`engine/src/hy4flash/sycl/sy_common.h:123-151`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-95,105-115,130-136` — `HY4_GPUS` 初期値、引数取得、`--gpus` / `--devices` parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:199-213,226-248,280-306` — 主 GPU と peer index の確定、および serve / 通常実行から expert 初期化への引き渡し。
- `engine/src/hy4flash/sycl/sy_common.h:94-112,115-152,154-175` — backend ごとの GPU 列挙、値の解釈、主 GPU queue の選択。
- `engine/src/hy4flash/sycl/sy_peer.h:182-203,231-259` — peer GPU が使われる条件、device memory / queue の初期化と失敗時の扱い。
- `engine/src/hy4flash/sycl/sy_graph.h:144-153` — peer GPU 向け expert setup の呼び出し。
