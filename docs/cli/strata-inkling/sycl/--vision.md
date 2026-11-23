# `--vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision encoder の `.strata` ファイルパス |

## 役割

SYCL 版 Inkling-2 の実行中に画像エンコーダーのファイルと画像ファイルを指定すると、画像を encoder で処理し、生成した埋め込みの統計を表示する。通常のモデル実行に画像を渡すオプションではなく、`--image` と組み合わせる任意の Vision 確認経路である。

## 使い方

```sh
# モデルをロードした後、画像エンコーダーで画像を処理して結果を表示する
strata-inkling-sycl --model ./inkling.strata --vision ./vision.strata --image ./sample.png
```

`--model` は必須で、Vision 処理に入る前にモデルをロードする。Vision 処理の後も通常の runner 初期化と、指定された実行モードの処理へ続く。

## 値と既定値

- 値は直後の引数を文字列として受け取る。値の形式・拡張子・存在確認を parser で検証する処理はない。値がない場合は空文字列になる。`--vision` を複数回指定した場合は、最後に代入された値が残る（parser は各出現の値を同じ変数へ代入する）。`engine/src/inkling2/sycl/ink_sy_main.cpp:112-118`
- 未指定時は空文字列で、Vision ファイルはロードされない。Vision 確認処理は `--vision` と `--image` の両方が空でない場合だけ実行される。片方だけの指定はエラーにならず、Vision 処理を行わない。`engine/src/inkling2/sycl/ink_sy_main.cpp:103,185-190`
- `need()` は次の引数がオプション表記かどうかを判定せず消費する。そのため値を省略して次のオプションを置くと、その文字列が `--vision` の値として扱われる。`engine/src/inkling2/sycl/ink_sy_main.cpp:112-118`

## 実行時の動作

通常経路では、まず必須の `--model` をロードし、その後 `--vision` と `--image` の両方が指定されていれば `InkSyVision::load()` で Vision shard を読み込む。実装は指定ファイルから 4096 バイトのヘッダー、圧縮 manifest、Section 1 の重みを読み、重みを SYCL device allocation に転送して tensor の参照を設定する。ロード成功時は stderr にロードしたパス、tensor 数、サイズを出力する。`engine/src/inkling2/sycl/ink_sy_main.cpp:171-190`; `engine/src/inkling2/sycl/ink_sy_vision.h:51-97`

続いて画像ファイルを読み、画像エンコードを実行する。エンコード後は埋め込みの token 数、平均、L2 norm、先頭4要素を stdout に `[VISION]` 行として表示する。Vision 結果を Inkling の prompt や生成処理へ渡すコードはこの経路にない。Vision 確認後に runner を初期化し、selfcheck・spec-check・bench・parallel sweep などの通常処理を続ける。`engine/src/inkling2/sycl/ink_sy_main.cpp:185-205`; `engine/src/inkling2/sycl/ink_sy_main.cpp:257-288`

`--info` を併用した場合は model の probe と情報表示の後に終了するため、Vision shard や画像は読み込まれない。表示する `images` 値は `--vision` の値が空かどうかを示すだけで、ファイルの有効性や画像処理の成否は確認しない。`engine/src/inkling2/sycl/ink_sy_main.cpp:173-180`

## 適用条件と副作用

- `--model` の指定・ロードが先に必要である。モデルがないと usage を stderr に出して終了コード 1、モデルのロードに失敗した場合も `[ERROR]` を stderr に出して終了コード 1 となり、Vision 処理には到達しない。`engine/src/inkling2/sycl/ink_sy_main.cpp:166-183`
- Vision の encoder ファイルが開けない、header が短い、manifest の読み込み・解析に失敗する、Section 1 を完全に読めない場合は、エラー文字列を stderr に出して終了コード 1 となる。重みは全体を読み込んで device allocation へ転送するため、SYCL デバイス側のメモリを使用する。`engine/src/inkling2/sycl/ink_sy_vision.h:51-97`; `engine/src/inkling2/sycl/ink_sy_main.cpp:186-190`
- 画像を開けない、デコードできない場合も stderr にエラーを出して終了コード 1 となる。画像は最大辺が 4096 ピクセルを超える場合に縮小され、縦横は `patch * merge` の倍数に切り上げてパディングされる。アルファは市松模様の背景色と合成されてからエンコードされる。`engine/src/inkling2/sycl/ink_sy_vision.h:339-369`
- この parser の Vision ロードは Inkling SYCL の `InkSyVision` による `.strata` artifact 読み込みである。共有 CPU encoder が持つ safetensors 対応を、この CLI オプションにも適用できるとは確認できない。SYCL 用 loader の実装範囲を超える形式の互換性は未確認。`engine/src/inkling2/sycl/ink_sy_vision.h:51-80`

## 出力とエラー

- 成功時は `[ink_sycl_vis] loaded ...` を stderr、`[VISION] image=... tokens=... mean=... l2=... first4=[...]` を stdout に出す。`engine/src/inkling2/sycl/ink_sy_vision.h:95-97`; `engine/src/inkling2/sycl/ink_sy_main.cpp:191-195`
- Vision shard または画像処理で失敗した場合、main が `[ERROR] <理由>` を stderr に出して `1` を返す。`engine/src/inkling2/sycl/ink_sy_main.cpp:186-190`

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:103-118` — `--vision` の値受け取り、別名なし、既定の空文字列。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-190` — model 必須条件、`--info` の早期終了、Vision 処理の適用条件と失敗経路。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:191-205,257-288` — Vision 結果の出力と、その後の runner 実行。
- `engine/src/inkling2/sycl/ink_sy_vision.h:51-97` — SYCL Vision shard の読み込み、device への重み転送、エラーと stderr 出力。
- `engine/src/inkling2/sycl/ink_sy_vision.h:339-369` — 画像読み込み、寸法調整、エンコード呼び出し。
- `docs/cli/README.md:1572-1592` — `strata-inkling-sycl` のコマンド階層と `--vision` の索引リンク。
