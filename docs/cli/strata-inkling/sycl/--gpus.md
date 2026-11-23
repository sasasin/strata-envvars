# `--gpus`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--gpus` |
| 別名 | `--devices` |
| 値 | GPU 台数、またはカンマ区切りの GPU 番号。実装は `atoi` で変換する |

## 役割

SYCL 版 Inkling エンジンが要求する GPU 数、または GPU 選択番号を指定します。2 台以上が要求された場合はモデルロード時に Dual-GPU Expert Parallelism（EP2）の初期化を試み、成功すると expert を2 GPUへ割り当てます。GPU が足りないなど初期化できない場合は単一 GPU 実行へフォールバックします（`engine/src/inkling2/sycl/ink_sy_main.cpp:129-140,183`; `engine/src/inkling2/sycl/ink_sy_common.h:784-835`）。

## 使い方

```sh
# GPU 0 と GPU 1 を使った EP2 を要求
strata-inkling-sycl --model model.strata --gpus 0,1

# 2 台を要求し、列挙順の先頭2台を使う
strata-inkling-sycl --model model.strata --gpus 2

# 別名 --devices で同じ指定をする
strata-inkling-sycl --model model.strata --devices 0,1
```

## 値と既定値

- 省略時は要求台数 `1`、GPU ID リストなしです。単一 GPU 指定だけでは EP2 は開始しません（`engine/src/inkling2/sycl/ink_sy_main.cpp:105-106,150-163`）。
- 値にカンマが含まれると ID リストとして扱い、空要素を除いて各要素を `std::atoi` で整数化します。リストが空でなければ先頭要素を主 GPU index、要素数を要求台数にします（`engine/src/inkling2/sycl/ink_sy_main.cpp:19-29,129-140`）。整数として読めない要素も拒否されず `atoi` の結果（通常 `0`）になります。空要素は無視されるため、たとえば `0,,1` は `[0, 1]` 相当です。
- カンマがない値は `atoi` で台数に変換し、`std::max(1, ...)` により最小値を1にします。したがって `0`、負数、整数に変換されない文字列は要求台数1になります（`engine/src/inkling2/sycl/ink_sy_main.cpp:137-140`）。範囲外番号や重複番号を parser でエラーにする検査はありません。
- オプション値の欠落も明示的にエラーにしません。`need()` は値がなければ空文字列を返し、台数形式では上記の変換により1台扱いになります（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-115,129-140`）。

## 実行時の動作

parser は `--gpus` と `--devices` を同じ分岐で受け取ります。モデルロード時に要求数が2以上、または ID リストが2個以上なら、SYCL GPU を列挙して EP2 を試します。ID リストが2個以上なら、先頭 ID を GPU0 とし、後続から範囲内かつ GPU0 と異なる最初の ID を GPU1 に選びます。該当する ID がなければ、GPU0 が0なら1、それ以外なら0を GPU1 にします。台数形式では列挙順を基準に GPU0/1 を選びます。要求が3台以上でも、この処理で設定する peer GPU は1台です（`engine/src/inkling2/sycl/ink_sy_common.h:792-810`）。

`--gpu` も同じ parser にあり、引数の並びに従って主 GPU index を設定します。`--gpus` の ID リストは先頭 ID でこれを上書きしますが、台数形式は既存の主 index を保持します（`engine/src/inkling2/sycl/ink_sy_main.cpp:128-140`）。

`IK2_GPUS` は、処理後の要求台数が1で ID リストが空の場合に読み取られます。そのため、`--gpus 2` や2つ以上の ID リストは環境変数の値を抑止しますが、`--gpus 1` はこの条件を満たし、環境変数で要求数が置き換わる場合があります。環境変数のカンマ区切り値も同じ CSV 変換を通ります（`engine/src/inkling2/sycl/ink_sy_main.cpp:150-162`）。詳細は [`IK2_GPUS`](../../../envvars/IK2_GPUS.md) を参照してください。

## 適用条件と副作用

- SYCL GPU が2台以上列挙されれば、peer queue の作成と GPU1 の空き予算確認を行い、予算が正なら P2P 可否を調べて EP2 を有効化します。EP2 が有効なロード結果は stderr に `Dual-GPU EP2`、GPU 名・分割比・`p2p` または `pinned` を含む行を出します。単一 GPU 経路でもロード概要を stderr に出します（`engine/src/inkling2/sycl/ink_sy_common.h:806-826,965-987`）。
- 可視 GPU が2台未満なら stderr に要求台数と可視台数を出し、単一 GPU で続行します。peer queue 作成時の `sycl::exception` も stderr に理由を出して単一 GPU にフォールバックします。GPU1 の VRAM 予算が0の場合は peer queue を破棄して EP2 を無効にします（`engine/src/inkling2/sycl/ink_sy_common.h:813-835`）。
- GPU index の列挙範囲外値は選択時に `[0, 可視 GPU 数 - 1]` へ丸められます。ID リスト内に有効な別 GPU がない場合も、既定の別 GPU index が使われます（`engine/src/inkling2/sycl/ink_sy_common.h:122-127,795-805`）。
- `IK2_GPUS` 以外に GPU 台数指定の優先順位へ関わる設定は、この parser と loader の追跡範囲では確認できませんでした。SYCL runtime 自体の device 選択・列挙挙動は外部実装のため、ここでは扱いません。

## 出力とエラー

GPU が不足してもエラー終了とはせず、警告を stderr に出して単一 GPU で継続します。モデルファイルを開けない、形式が不正などモデルロード自体が失敗した場合は呼び出し側が `[ERROR] <理由>` を stderr に出して終了コード1を返します（`engine/src/inkling2/sycl/ink_sy_common.h:664-670`; `engine/src/inkling2/sycl/ink_sy_main.cpp:183`）。GPU 指定の構文・番号に対する専用の parser エラーや警告は確認できませんでした。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:105-140` — 初期値、parser、alias、整数・CSV 変換。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:150-164,183` — `IK2_GPUS` の適用条件、主 index の設定、GPU 要求をモデル loader に渡す箇所。
- `engine/src/inkling2/sycl/ink_sy_common.h:71-100,119-129` — 主 GPU index、SYCL GPU 列挙と index による queue 選択。
- `engine/src/inkling2/sycl/ink_sy_common.h:660-670,784-835,965-987` — loader の引数、EP2 選択・fallback・出力。
- `docs/cli/README.md:1572-1580` — `strata-inkling-sycl` の階層、parser 所在、`--gpus` と `--devices` の索引登録。
