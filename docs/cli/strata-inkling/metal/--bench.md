# `--bench`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--bench` |
| 別名 | なし |
| 値 | 取らない flag |

## 役割

Metal runner で決定的な token ID 列を prompt として評価し、prefill と greedy decode の時間・スループットを測定します。モデル品質の評価や、利用者が入力した文章の測定ではありません。parser はこの flag をベンチ実行フラグとして記録し、モデルと runner の初期化後にベンチ経路を実行します（`engine/src/inkling2/metal/ink_metal_main.cpp:456`, `:481-494`, `:589-603`）。

## 使い方

```sh
# model file をロードして既定のベンチを実行する
strata-inkling-metal --model model.strata --bench

# prompt 長と生成数を指定する。--prompt-len と --gen は別オプション
strata-inkling-metal --model model.strata --bench --prompt-len 256 --gen 64

# draft を使わない通常 decode として測定する
strata-inkling-metal --model model.strata --bench --draft off
```

## 値と既定値

- `--bench` 自体は値を取りません。複数回指定しても同じ boolean を `true` にするだけです（`engine/src/inkling2/metal/ink_metal_main.cpp:427`, `:456`）。
- `--prompt-len` の既定値は 128、`--gen` の既定値は 32 です。いずれも `atoi` で整数化され、parser 側に範囲検証はありません（`engine/src/inkling2/metal/ink_metal_main.cpp:423-424`, `:451-452`）。
- ベンチ prompt は長さ `--prompt-len` の配列で、各位置 `i` の ID は `100 + (i * 17) % 50000` です。`--ids` で設定する通常 prompt はこのベンチ prompt には使われません（`engine/src/inkling2/metal/ink_metal_main.cpp:460-463`, `:589-592`）。
- `--prompt-len` に数値でない値を渡すと `atoi` により 0 になります。負数も拒否されず、その値で `vector` を構築しようとします。大きさの上限や負数時の専用エラー処理はこの経路では確認できません（`engine/src/inkling2/metal/ink_metal_main.cpp:452`, `:589-591`）。

## 実行時の動作

1. `--model FILE.strata` が必要です。指定がない場合は usage を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:470-473`）。
2. Metal context を作成し、model をロードして、既定では `mod.warm(8)` を行ってから runner を初期化します。`--no-warm` を付けるとこの warm 呼び出しを省きます（`engine/src/inkling2/metal/ink_metal_main.cpp:475-493`）。したがって `--bench` の計測にはモデルロード・runner 初期化・warm の時間は含まれません。
3. 固定 prompt を用いて slot 0 を reset し、prompt の prefill 時間と生成時間を別々に計測します。`--gen` が 0 以下なら prefill の後に生成を行わず、decode 時間は 0 になります。生成ループは `max_ctx` に近づくと終了するため、指定した生成数より出力が短い場合があります（`engine/src/inkling2/metal/ink_metal_main.cpp:133-164`, `:174-177`）。
4. `--draft off` でなければ draft を希望し、runner はモデル manifest に DSpark がある場合に限りそれを有効化します。ベンチで speculative decode を使うかは `runner.use_dspark` にも依存し、DSpark がないモデルでは通常 decode になります。`--draft tree`、`beam`、`tree6` などは tree budget にも影響します（`engine/src/inkling2/metal/ink_metal_main.cpp:489-493`, `:550-558`, `:595-596`; `engine/src/inkling2/metal/ink_metal_runner.h:230-239`）。
5. 成功時は stdout に `[BENCH]` 行を出し、build 表示、実際に使った draft 表示、prompt 長と prompt tokens/s、出力 token 数と decode tok/s、accept/offered 数を含めます。計測の分母が 0 に近い場合は表示計算で `1e-6` 秒を下限にします（`engine/src/inkling2/metal/ink_metal_main.cpp:600-603`）。

## 適用条件と副作用

- Metal backend の `strata-inkling-metal` が対象です（索引 `docs/cli/README.md:1549-1552`）。モデルを GPU/Metal runner にロードし、ベンチ用の forward pass と生成を実行するため、GPU 時間とモデル・runner のメモリを使用します（`engine/src/inkling2/metal/ink_metal_main.cpp:475-493`, `:589-596`）。
- `--bench` と `--par-sweep` は独立したフラグです。`--bench` 単独では並列 sweep を行いません。両方を指定すると通常の `--bench` の後に sweep が実行されます（`engine/src/inkling2/metal/ink_metal_main.cpp:589-614`）。
- runner は指定 context 長を最低 256 に補正し、working set に応じて context 長や batch 上限をさらに調整する場合があります。したがってベンチの生成は `--gen` だけでなく実際の runner context にも制約されます（`engine/src/inkling2/metal/ink_metal_runner.h:230-239`, `:385-410`）。
- ベンチ経路自体は結果ファイルを指定・生成しません。標準出力の測定行に加え、起動時の device 情報や runner ready 情報などが標準エラーに出ます（`engine/src/inkling2/metal/ink_metal_main.cpp:475-479`, `engine/src/inkling2/metal/ink_metal_runner.h:758-764`）。

## 出力とエラー

- model のロード失敗は `[ERROR] load: ...` を stderr に出し、終了コード 1 です。runner 初期化失敗は `[ERROR] runner init: ...` を stderr に出し、終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:481-493`）。
- ベンチ内の `run_greedy_decode` が失敗すると `[ERROR] bench: ...` を stderr に出し、終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:595-599`）。forward batch は `M <= 0` または `M > max_batch` を失敗として返します（`engine/src/inkling2/metal/ink_metal_runner.h:995-1003`）。
- `--bench` に値を付ける構文はありません。値を別引数として置くと、その引数は別オプションとして解析され、未知の引数なら `unknown arg: ...` を stderr に出して終了コード 2 です（`engine/src/inkling2/metal/ink_metal_main.cpp:456`, `:464-466`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-467` — parser、関連 option の既定値、欠落値・未知引数の処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — model 必須条件、Metal context/model/warm/runner の初期化順。
- `engine/src/inkling2/metal/ink_metal_main.cpp:120-164`, `:174-177` — prefill・decode の計測、`--gen` と context による終了条件。
- `engine/src/inkling2/metal/ink_metal_main.cpp:550-558`, `:589-603` — draft mode の選択、bench prompt、実行と結果出力。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-239`, `:385-410`, `:758-764`, `:995-1003` — runner の値補正・DSpark 適用、working set 対応、初期化表示、batch validation。
- `docs/cli/README.md:1549-1552` — `strata-inkling-metal` のツール ID、parser scope、索引上の配置。

調査範囲はこの checkout の Metal runner と、その runner が呼ぶ `InkMetalRunner` の初期化・batch validation です。Apple GPU 上での実測、各モデルの性能差、負数・極端な長さを実行した際の OS/標準ライブラリ依存の結果は確認していません。
