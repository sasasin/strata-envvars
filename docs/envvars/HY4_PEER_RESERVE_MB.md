# `HY4_PEER_RESERVE_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4_PEER_RESERVE_MB` は、Hy4-Flash の tiered expert 配置で、各 peer GPU の空き VRAM から差し引く予約量を MiB 単位で指定する。未指定または正の整数に変換できない値では、prefill chunk に応じた自動予約（最低 1 GiB）を使う。予約後の容量は peer GPU に配置する expert の上限になる。primary GPU の予約には使われず、peer GPU の P2P 可否や expert の計算結果も直接変更しない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-895,1013-1040`）。

この値が配置に影響するのは peer GPU がある場合である。CUDA または HIP peer 対応 build の tiered loader が読み取る。通常の単一 GPU 配置では peer ごとのループがなく、読み取られても値は使われない（同 `:792-801,877-886`）。

## 値と判定

値は `getenv` で取得し、C の `atoi` で変換する。変換結果が正の場合に限り、その整数を `size_t` にして 20 bit 左シフトした値を使う（1 MiB = `1 << 20` bytes）。文字列全体の妥当性検査や上限 clamp はない。`atoi` のため、先頭の空白と符号は受け付け、数字以降の文字列は無視する。数字に変換できない場合は 0 となり、自動値へ戻る。`atoi` の `int` 範囲外の文字列の結果は保証されない（同 `:882-885`）。

| 条件 | 未設定 | 使用する値の例 | 自動値に戻る例 |
|---|---|---|---|
| `HY4_CUDA || HY4_HIP_PEERS` が有効な build | 自動値 | `1`、`256`、`+2`、` 3`、`12MiB`（先頭の `12` を変換） | 空文字、`0`、`-1`、`true`、`0anything` |
| peer GPU がない、または下記 build 条件外 | peer 単位の処理なし | 該当なし | 該当なし |

自動値 `preserve` は `max(1 GiB, chunk_ws)`。`chunk_ws` は `max(planned_chunk, 1024)` を使い、`max(planned_chunk, 1024) * 16 * 1536 * 6 + max(planned_chunk, 1024) * 1536 * 10 + 512 MiB` bytes で計算する（同 `:879-885`）。

## 有効になる条件

- `load_gpu_model` が expert を読み込み、通常の tiered loader に進む必要がある。複数 GPU が指定されると full expert arena の単一 GPU 読み込み経路を通らず tiered loader を使う（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1436,1486-1500`）。
- build で `HY4_CUDA || HY4_HIP_PEERS` が真であること。HIP build では `HY4_HIP_PEERS` の既定値は 1（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-886`; `engine/src/hy4flash/run/hy4_gpu.h:324-331`）。
- `g.peer_devs` に peer GPU があること。CLI の `--gpus` / `--devices`、または `HY4_GPUS` から peer GPU を選べる（`engine/src/hy4flash/run/hy4_main.hip.cpp:361,404,514-541,647-659`）。serve 経路も同じ `load_gpu_model` に peer GPU を渡す（`engine/src/hy4flash/run/hy4_serve.hip.h:268-295`）。
- 予約後の peer GPU の空き量が正であること。`pfr <= preserve` の場合は容量を 0 とし、expert はその GPU に配置されない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:886-895,1013-1040`）。
- `--vram-experts-gb` が全 GPU 合計の上限をかける場合、peer の容量も比例縮小されるため、この変数で確保した容量をすべて配置に使うとは限らない（同 `:937-952`）。`--layer-split` が指定されると、層ごとの配置先制約も適用される（同 `:954-1009`）。
- 分散 expert shard 経路は `load_experts_tiered` より前に `load_expert_shard` へ進むため、この peer 予約値を使わない（同 `:1400-1409`）。

## 実行時の詳細

通常の CLI と serve は、model load 時に `load_gpu_model` を呼ぶ。tiered loader は `HY4_PEER_RESERVE_MB` をその呼び出し中に取得し、各 peer GPU の `hipMemGetInfo` が返す空き量 `pfr` から予約分を引いて `vcap` を決める。環境変数の値を static cache するコードはなく、同じモデルロード中に再読込もしない（`engine/src/hy4flash/run/hy4_main.hip.cpp:647-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:291-295`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-895`）。

`vcap` が各 peer GPU の expert 配置上限となり、rank 順に expert を選ぶ通常経路、または `--layer-split` による層指定経路で容量内の expert を割り当てる。tier 4 として割り当てられた expert は peer GPU の arena に読み込まれる。予約によって容量が減ると、そこに収まらない expert は別 GPU または host 側の tier に残る（同 `:1013-1071,1145-1155,1204-1215,1236-1245`）。

### CLI・他設定との関係

- `--gpus` / `--devices`（または `HY4_GPUS`）は peer GPU の有無と構成を決める。`HY4_PEER_RESERVE_MB` は GPU 選択を上書きしない（`engine/src/hy4flash/run/hy4_main.hip.cpp:361,404,514-541`）。
- `--vram-experts-gb` は配置容量全体に上限をかける。`--layer-split` は peer を含む各 GPU の担当層を制約する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:937-1009`）。
- `HY4_PEER_NO_P2P` は peer access の有効化を抑える設定で、予約値や peer expert 容量の算出には使われない（同 `:877-899`）。P2P を使わない場合でも予約量の計算自体は同じである。
- `HY4_RESERVE_GB` は primary GPU の expert budget や adaptive vcache allocation に関係する別の予約設定であり、この peer GPU ごとの `preserve` には適用されない（同 `:1125-1137,1420-1429`）。

## ログと測定値

peer GPU の空き VRAM が予約量以下になると、標準エラーに次の形式で出力する。この場合、その GPU の expert 配置上限は 0 になる。

```text
[load] peer GPU%d free %.2f GiB <= required reserve %.2f GiB (chunk=%d); placing 0 experts on GPU%d
```

予約値を使ったこと自体を示す専用ログはない。予約量を超えた場合、この条件のログは出ず、選ばれた expert 数や最終容量は後続の multi-GPU load summary に出る（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:891-895,1256-1262`）。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-801,877-895` — tiered loader、build guard、値の変換、既定予約、peer ごとの VRAM 上限。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:937-952,1013-1071,1145-1155,1204-1215,1236-1245` — 容量上限から expert 配置・peer arena 読み込みへの流れ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1436,1486-1500` — 分散 shard と通常の tiered loading の分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:361,404,514-541,647-659` — GPU 選択と CLI model load。
- `engine/src/hy4flash/run/hy4_serve.hip.h:268-295` — serve 経路からの model load。
- `engine/src/hy4flash/run/hy4_gpu.h:324-331` — HIP peer build の既定 macro。
