# `strata` / `strata-q36` `--expert-slots`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family 経路、または `strata-q36` |
| オプション | `--expert-slots` |
| 別名 | なし |
| 値 | 整数。正数は各対象層で VRAM に置く expert slot 数を指定し、0 以下は自動決定を使う |

## 役割

Qwen3.6 専用エンジンの hybrid expert 配置で、各 expert 層に確保する VRAM slot 数を指定します。expert は全件ホストメモリに置かれ、slot 数分の expert が VRAM に常駐します。slot 数が指定されると自動の slot 算出を使わず、指定数（ただし層あたり expert 総数が上限）で配置可能かを判定します（`engine/src/qwen35/q36_engine.cu:4247-4260,4351-4370,4442-4453`、`engine/include/strata/qwen35/hybrid_fit.hpp:31,46-63`）。

## 使い方

```sh
# Qwen3.6 GGUF で単発推論し、各層の expert slot を 64 に固定する
strata-q36 --model /path/to/Qwen3.6-35B-A3B.gguf --tokens 1,2,3 --n 16 --expert-slots 64
```

`strata` の family 経路でも同じ専用 parser に渡されます。通常の Terminal CLI の `strata launch` と、この engine parser の引数体系は異なります（`engine/src/qwen35/q36_engine.cu:5354-5387`）。

## 値と既定値

- 既定値は `0` です。`0` または負数は固定値として使われず、自動配置経路になります（`engine/src/qwen35/q36_engine.cu:5345,5386,4277,4301,4318`）。
- 正数は `std::atoi` で整数化されます。明示的な正数範囲検証はありません。`hybrid_plan` は指定数を expert 総数 `ne` で上限づけるため、総数より大きい指定は各層の全 expert 数に丸められます（`engine/src/qwen35/q36_engine.cu:5386`、`engine/include/strata/qwen35/hybrid_fit.hpp:52-58`）。
- 値が欠けると `strata-q36: --expert-slots needs a value` を標準エラーに出して終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。
- `atoi` のため、不正な数値文字列は明示的な検証エラーにならず、変換結果が 0 なら自動配置扱いになります。数値形式の厳密な検証は実装されていません（`engine/src/qwen35/q36_engine.cu:5386`）。

## 実行時の動作

- 配置対象は通常層と、モデルが持つ場合は MTP block を含む全 expert 層です。slot 数は「層あたり」で、層ごとの expert stride 合計を使って VRAM 必要量を見積もります（`engine/src/qwen35/q36_engine.cu:4253-4261,4352-4366`）。
- 正数指定では、全 expert が VRAM に収まる場合でも all-in-VRAM 配置分岐には入らず、hybrid 配置を試みます。CPU expert pool が有効な build では、各層に指定数（最大 `ne`）を割り当て、expert 全体を host arena に保持し、その先頭 slot 分を VRAM にコピーします（`engine/src/qwen35/q36_engine.cu:4318-4336,4337-4350,4442-4453`）。
- 0 以下の自動配置では、VRAM 予算に応じて slot 数を算出します。正数指定時はこの自動算出をせず、budget から算出した値ではなく指定数を `hybrid_plan` に渡します（`engine/include/strata/qwen35/hybrid_fit.hpp:49-63`）。
- 明示的な正数指定は `--expert-slots` が 0 以下であることを条件にした最適化も抑止します。具体的には packed Q8_0 decode copy の返却による全 expert VRAM 配置、および MTP block のみ hybrid にする配置判定を通りません（`engine/src/qwen35/q36_engine.cu:4277-4291,4301-4317`）。
- streamed prompt 用 staging pair が指定 slot 数と同時に収まらないとき、環境変数 `STRATA_Q36_KEEP_STAGING` が未設定なら staging なしの計画を再試行し、成功すれば streamed prompt path を無効化します。このとき標準エラーに staging が収まらず prompt が遅くなる旨を出します。環境変数が設定されている場合はこの fallback を許可しません（`engine/src/qwen35/q36_engine.cu:4360-4376`、`engine/include/strata/qwen35/hybrid_fit.hpp:29,66-77`）。

## 適用条件と副作用

- Qwen3.6 専用 parser のオプションです。`strata` は Qwen3.6 family 経路で同じ parser に渡し、別 executable `strata-q36` も同じ `run` 実装を使います（`engine/src/qwen35/q36_engine.cu:5339-5356,5386`。索引上の scope は [`docs/cli/README.md`](../../README.md) の `strata-engine / qwen36` 節）。
- CPU expert pool を含まない build では、全 expert が VRAM に収まるケース以外は hybrid 配置できず失敗します。正数指定は all-in-VRAM 分岐を迂回するため、そのような build では明示指定自体が配置失敗につながり得ます（`engine/src/qwen35/q36_engine.cu:4318-4343`）。
- 固定 slot 数を見積もった hybrid plan が VRAM に収まらない場合、slot 数を自動で減らさず配置を拒否します。`STRATA_Q36_KEEP_STAGING` 未設定の場合に限り staging を外した再試行がありますが、それでも収まらなければ失敗します（`engine/include/strata/qwen35/hybrid_fit.hpp:52-77`）。
- host arena と VRAM slot の確保を行います。ホスト pinned allocation が失敗した場合は通常の `malloc` に fallback し、それも失敗すると host memory 不足として返します（`engine/src/qwen35/q36_engine.cu:4397-4409`）。

## 出力とエラー

- slot 数・buffer の計画が VRAM に収まらない場合、`not enough VRAM left for the hybrid experts' buffers and slots (...)` を標準エラーへ出します。メッセージは `--prefill` chunk、`--batch`、`--max-context` の削減を案内し、明示 slot 数が正数のときは `--expert-slots` も減らす候補として追加します。呼び出し側は配置失敗として終了コード 1 を返します（`engine/src/qwen35/q36_engine.cu:4380-4385,5523-5525`）。
- CPU pool を持たない build で hybrid 配置に進んだ場合は、expert が VRAM に収まらず CPU pool もない旨を標準エラーに出し、同じく終了コード 1 で終了します（`engine/src/qwen35/q36_engine.cu:4337-4342,5523-5525`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5345-5387` — 既定値と parser。`--expert-slots` は alias なしで `atoi` により読み取られる。
- `engine/src/qwen35/q36_engine.cu:4247-4265,4277-4336` — 配置計画、正数時に迂回する自動配置専用最適化、および all-in-VRAM 条件。
- `engine/src/qwen35/q36_engine.cu:4337-4385,4397-4409,4442-4453` — CPU pool 条件、slot 計画・staging fallback、VRAM/host allocation と失敗経路。
- `engine/include/strata/qwen35/hybrid_fit.hpp:20-77` — forced slot 数の上限、VRAM 必要量と staging なし fallback の計算。
- `docs/cli/README.md:1240-1255` — `strata-engine / qwen36` のコマンド階層と索引リンク。索引に対象 option があることを確認。
