# `--peer-slots`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata` |
| オプション | `--peer-slots` |
| 別名 | なし |
| 値 | 整数として変換される expert slot 数 |

## 役割

`--peer-device` で有効にする第2 GPU の expert cache tier に載せる expert 数の上限を指定します。指定数は上限であり、実際に載る数は peer GPU の空き VRAM、`--peer-reserve-mib` による予約、primary 側がすでに保持している expert にも制限されます。

## 使い方

```sh
# peer GPU 1 の expert tier を最大 128 slots に制限する
strata --pack pack/full --tokens "1,2,3" --expert-profile profile.strp \
  --expert-cache 1024 --peer-device 1 --peer-slots 128
```

この例は構文を示しています。pack、profile、token ID、expert cache の値は使用モデルと環境に合わせてください。`--peer-device` がない場合、このオプションの値は tier の初期化に使われません。

## 値と既定値

- 既定値は `0` です。値の解析には `std::atoll` を使い、parser 側で書式・範囲の検証や補正をしません。数値に変換できない文字列は `atoll` の変換結果に従います（`engine/src/program/generate.cpp:4205-4208`）。
- tier の選択処理は `max_slots > 0` の場合にだけ上限を適用します。そのため `0` と負数は上限なしとして扱われます（`engine/src/core/peer_experts.cpp:272-280`）。
- 正の値を指定しても、空き VRAMから予約分を引いた容量を超えて枠を確保することはありません。

## 実行時の動作

parser は値を `Options::peer_slots` に保存します。`--peer-device` が 1 以上なら、engine は expert profile、primary cache、expert source とともにこの値を `PeerExperts::open` へ渡します。peer tier は profile の順位に従い、primary が保持していない expert を選び、VRAM に収まる分だけロードします（`engine/src/program/generate.cpp:915-921,4205-4208,10211-10220`; `engine/include/strata/core/peer_experts.hpp:43-47`）。

`PeerExperts::open` は scratch と staging 領域を先に確保し、その後の空き VRAMから `max(reserve_mib, 128)` MiB を差し引いて expert の容量を見積もります。選択時に `--peer-slots` の正の値をさらに上限として使うため、このオプションはメモリ容量計算の代わりにはなりません（`engine/src/core/peer_experts.cpp:238-268,272-280`）。

## 適用条件と副作用

- `--peer-device` が 1 以上のときだけ peer tier の初期化が行われ、この値が適用されます。peer device を使うには `--expert-profile` と正の `--expert-cache` が必要です（`engine/src/program/generate.cpp:10211-10220`）。
- `--peer-device` は `--layer-split`、および `--expert-cache-device1..3` の remote expert cache と併用できません。併用時は parser 後の検査でエラーになります（`engine/src/program/generate.cpp:5284-5290`）。
- peer device が無効、primary GPU と同一、または利用可能な device 数の範囲外なら `PeerExperts::open` は失敗します（`engine/src/core/peer_experts.cpp:192-202`）。
- 初期化では peer GPU 上に stream、scratch、cache などの GPU メモリを確保し、選択した expert blob を tier にロードします。ファイルへの書き込みはこのオプションの処理では確認できません（`engine/src/core/peer_experts.cpp:238-258,264-312`）。
- 本調査ではビルドや GPU 実行をしていないため、特定の GPU 構成で確保できる実数や性能への影響は確認していません。

## 出力とエラー

- `--peer-slots` 単独に固有の値検証エラーはありません。値を省略した場合、共通の `next` 処理が `<option> needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3847,4207`）。
- peer tier 有効時、profile または expert cache がない場合はエラーメッセージを stderr に出して終了コード 1 になります。初期化失敗も `peer.open` が返したエラーを stderr に出して終了コード 1 になります（`engine/src/program/generate.cpp:10213-10222`）。
- 空き容量がない、または primary が保持していない expert が残っていない場合、tier の初期化は `peer experts: no room or no expert left for the peer` で失敗します（`engine/src/core/peer_experts.cpp:272-282`）。
- 初期化成功時は peer GPU 番号、ロードした expert 数、容量とロード時間を stderr に表示します（`engine/src/program/generate.cpp:10224-10227`）。

## 根拠

- `engine/src/program/generate.cpp:915-921` — `peer_slots` の型と既定値、および peer tier との関係。
- `engine/src/program/generate.cpp:1426-1431` — usage 上の option 表記と既定説明。
- `engine/src/program/generate.cpp:3842-3847,4205-4208` — 引数値の取得、`atoll` による変換と保存。
- `engine/src/program/generate.cpp:5284-5290,10211-10227` — peer device の併用制約、必要条件、tier 初期化、成功・失敗時の出力。
- `engine/include/strata/core/peer_experts.hpp:43-47` — ranked expert を空きメモリ内で選び、正の `max_slots` で上限を設ける契約。
- `engine/src/core/peer_experts.cpp:192-202,238-268,272-312` — device 検査、予約を含む空き VRAM計算、slot 数上限、ロードと失敗条件。
