# `strata` / `strata-q36` `--expert-vram`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 を選択した場合）または `strata-q36` |
| オプション | `--expert-vram` |
| 別名 | なし |
| 値 | routed experts 用の VRAM 予算（GiB、数値）。負数は自動予算として扱う |

## 役割

Qwen3.6 専用エンジンで、routed experts の VRAM 予算を GiB 単位で指定します。expert 配置の上限や hybrid 配置で常駐させる expert slot 数の計算に使われます。モデル本体、コンテキスト、セッション、hybrid 用バッファなどを含むプロセス全体の VRAM 上限ではありません。`strata` はモデルの family を判定して Qwen3.6 の parser に引き渡し、`strata-q36` も同じ parser を使います（`engine/src/program/generate.cpp:3805-3817`、`engine/src/qwen35/q36_engine.cu:5339-5385`）。

## 使い方

```sh
# Qwen3.6 の生成で routed experts の予算を 20 GiB にする
strata --model ./Qwen3.6.gguf --tokens "1 2 3" --n 1 --expert-vram 20
```

同じ引数は、専用実行ファイルがある環境では `strata-q36 --model ...` にも渡せます。索引上もこの option は Qwen3.6 専用 parser の scope に置かれています（`docs/cli/README.md:1240-1255`）。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。明示的な数値形式・範囲検証はありません。省略時の内部値は `-1.0` で、自動予算を選びます（`engine/src/qwen35/q36_engine.cu:5342-5344,5384`）。
- `--expert-vram` の後に値がない場合は stderr に `needs a value` を出して終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。同じ option を複数回指定すると、parser の逐次代入により最後の値が残ります（同 `:5348-5385`）。
- 値が負数なら未指定時と同じ自動予算経路です。0 以上なら指定値に `2^30` を掛けて byte 予算に変換します（`engine/src/qwen35/q36_engine.cu:4264-4266`）。0 は 0 byte の予算になります。
- 自動予算は配置開始時点の空き VRAM から 768 MiB を差し引いた値（空きがそれ以下なら 0）です。明示値はこの expert 予算を置き換えます（`engine/src/qwen35/q36_engine.cu:4262-4266`）。

## 実行時の動作

`place_experts` は全 routed experts の必要量を計算し、明示値が 0 以上ならその値を予算として、未指定または負数なら自動予算として配置を決めます。全 expert を VRAM に置く条件には、expert 予算に加えて実際の空き VRAM が必要量と追加 256 MiB を満たすことも含まれます（`engine/src/qwen35/q36_engine.cu:4256-4266,4318-4335`）。

全量を置けない場合、CPU expert pool を含む build では `hybrid_plan` が予算から VRAM 常駐 slot 数を算出し、残りの experts は host memory に置きます。計画には hybrid buffer と headroom の実空き VRAM 条件も適用されます（`engine/src/qwen35/q36_engine.cu:4343-4385`、`engine/include/strata/qwen35/hybrid_fit.hpp:20-35,46-77`）。`--expert-slots` に正数を指定すると hybrid 計画の slot 数はその指定値（expert 数を上限）で決まるため、予算から slot 数を算出する通常経路を上書きします（`engine/include/strata/qwen35/hybrid_fit.hpp:49-63`）。

`--chunk` / `--prefill` を省略または `auto` にした場合、chunk の初期選択でもこの予算が参照されます。slot 強制指定がなく、main experts が明示予算以下なら `fits` と判定されて初期値 512 になり、それ以外は空き VRAM に応じて 2048 / 1024 / 512 になります。明示 `--expert-vram` のときは、自動で大きい chunk を探す追加処理（1024 以上の候補選択）は走りません。`STRATA_Q36_CHUNK` があれば後段で 256..4096 に clamp した値に上書きされます（`engine/src/qwen35/q36_engine.cu:5475-5519`）。

自動予算のときだけ、必要量に応じて packed Q8_0 decode copies を解放して全 expert を VRAM に収める経路、および MTP block だけを CPU pool に置く経路が判定されます。明示予算（0 以上）ではこれらの auto-only 分岐条件を満たしません（`engine/src/qwen35/q36_engine.cu:4271-4301`）。

## 適用条件と副作用

- 対象は索引に示された Qwen3.6 専用 parser です。他の model family の parser に同名 option があるとは限りません（`docs/cli/README.md:1240-1255`、`engine/src/program/generate.cpp:3805-3817`）。
- CPU expert pool なしの build で全 routed experts が VRAM に収まらない場合、配置は失敗します。CPU pool ありでも hybrid 用 buffer / slot が空き VRAM に収まらなければ失敗します（`engine/src/qwen35/q36_engine.cu:4337-4343,4380-4385`）。
- `--expert-vram` を明示しても、その他の engine buffer や別プロセスの VRAM 使用量までは制限しません。実際の割当失敗は起こり得ます（`engine/src/qwen35/q36_engine.cu:4318-4326,4413-4425`）。
- Terminal の setup は VRAM reserve を構成すると、GPU の公称 VRAM から 3.0 GiB と予約 MiB を差し引いた値（下限 0）をこの engine option として生成引数に加えます（`terminal/setup.py:9994-9999`）。

## 出力とエラー

option 固有の値検証エラーや警告は確認できません。CPU pool が無効で VRAM 不足の場合は配置理由を stderr に出し、呼び出し側は終了コード 1 を返します。hybrid 計画が空き VRAM に収まらない場合も不足量と対処候補を stderr に出して終了コード 1 になります（`engine/src/qwen35/q36_engine.cu:4337-4343,4380-4385,5523-5526`）。

## 根拠

- `engine/src/program/generate.cpp:3805-3817` — model family による Qwen3.6 parser への振り分け。
- `engine/src/qwen35/q36_engine.cu:5342-5385` — parser の初期値、値取得、`--expert-vram` 登録。
- `engine/src/qwen35/q36_engine.cu:4247-4266,4271-4301,4318-4343` — 予算計算、auto-only の配置分岐、全量配置と CPU pool 不在時の失敗。
- `engine/src/qwen35/q36_engine.cu:4343-4385,4413-4425,5523-5526` — hybrid 配置計画、実 VRAM 不足時の失敗と呼び出し元。
- `engine/src/qwen35/q36_engine.cu:5475-5519` — auto chunk との相互作用。
- `engine/include/strata/qwen35/hybrid_fit.hpp:20-35,46-77` — expert budget と forced slot 数から hybrid slot / 必要 VRAM を計画する規則。
- `terminal/setup.py:9994-9999` — setup が VRAM reserve から `--expert-vram` を組み立てる経路。
