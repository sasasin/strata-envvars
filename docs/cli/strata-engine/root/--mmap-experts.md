# `strata generate --mmap-experts`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--mmap-experts` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

GPU キャッシュにない expert の供給元として、既定の resident arena を使わず、パック内の `experts.bin`（または条件によりモデルの GGUF shard）をファイルマップから読むよう指定する。OS のファイルキャッシュに依存する経路を明示的に選ぶため、expert 全体の resident arena を確保しない実行や比較に使える。`--resident-cpu-experts` や `--resident-budget-gib` と組み合わせた場合は、ファイルマップを残したまま一部 expert を RAM にコピーする構成にもなる。既定では `mmap_experts` は false で、engine は resident arena を選ぶ（`engine/src/program/generate.cpp:874`, `engine/src/program/generate.cpp:8498`, `engine/src/program/generate.cpp:8595`, `engine/src/program/generate.cpp:8619-8622`）。

## 使い方

```sh
# 既存の pack と native GGUF を使い、ファイルマップ経由の expert source を選ぶ
strata generate --pack /path/to/pack --native /path/to/model.gguf \
  --tokens "1,2,3" --mmap-experts
```

`--pack` と token 入力は generate の基本引数で、`--native` は native pack の GGUF shard を指定する場合に使う（`engine/src/program/generate.cpp:1208-1219`, `engine/src/program/generate.cpp:3851`, `engine/src/program/generate.cpp:3926`）。

## 値と既定値

値を取りません。parser は引数が `--mmap-experts` と一致すると内部フラグを true にし、数値や文字列の validation はありません。複数回指定しても同じ bool を true にするだけです。未指定時は false で、後段の条件による上書きがなければ resident arena 経路です（`engine/src/program/generate.cpp:874`, `engine/src/program/generate.cpp:4217-4219`）。未知の引数は stderr に `unknown argument` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4273`）。

## 実行時の動作

フラグが有効なら `FileExpertSource` を初期化し、native GGUF の場所を渡してから pack を開く。pack に `experts.bin` があればそれを読み取り専用で map し、ファイル長・expert layout の整合性を確認する。native layout で `experts.bin` が存在せず `--native` の GGUF が渡されている場合は、検査済みの GGUF shard を map し、必要時に shard 上の slice から expert blob を組み立てる。Windows は `CreateFileMappingW` / `MapViewOfFile`、POSIX 側は `mmap(PROT_READ, MAP_SHARED)` を使う（`engine/src/program/generate.cpp:8621-8628`, `engine/src/core/expert_source.cpp:1499-1523`, `engine/src/core/expert_source.cpp:1570-1580`, `engine/src/core/expert_source.cpp:1600-1638`, `engine/src/core/expert_source.cpp:1640-1665`, `engine/src/core/expert_source.cpp:1801-1805`, `engine/src/core/expert_source.cpp:1806-1809`, `engine/src/core/expert_source.cpp:1820-1869`）。

マップした expert は GPU cache fill や CPU pool の読み出し元になる。フラグ単独では RAM resident copy を要求しないため、ファイルキャッシュが保持できるかによって読み出しが変わる。起動時に stderr へ `experts via mmap` と source が表示される（`engine/src/program/generate.cpp:8645-8647`）。Linux ではこの file tier に I/O prefetch 等が適用される場合があり、設定・既定条件は `STRATA_IO_PREFETCH` 等に左右される（`engine/src/program/generate.cpp:8688-8695`）。

## 適用条件と副作用

- `--shared-expert-arena` と同時指定すると、resident arena 用 backing file との併用として拒否され、stderr に理由を出して終了コード 2 になる（`engine/src/program/generate.cpp:4866-4868`）。
- `--resident-cpu-experts` はこのフラグと静的 `--expert-profile` の両方を必要とする。併用時は GPU cache にない一部 expert を追加で RAM に保持でき、マップは再読み込み用 fallback として残る（`engine/src/program/generate.cpp:4870-4872`, `engine/include/strata/core/expert_source.hpp:774-785`）。
- `--resident-experts` は parser 内で `mmap_experts` と resident CPU copy 等をまとめて有効にする。`--resident-budget-gib` / `--ram-experts-gb` の正値も mmap と RAM copy を選び、0 は mmap のみの SSD expert mode にする。`--ssd-experts` も mmap を選び RAM copy を無効にする（`engine/src/program/generate.cpp:4221-4228`, `engine/src/program/generate.cpp:4236-4257`）。これらを重ねたときの最終設定は引数を処理した順序の代入に従う。
- Metal build では compile-time 経路で `mmap_experts` が true にされるため、フラグの有無にかかわらず同じ file source が選ばれる（`engine/src/program/generate.cpp:5336-5341`）。
- arena を選んだ場合でも、許可された RAM 不足 fallback が発生すると、このフラグを内部で有効にして file source へ切り替える経路がある。明示指定時とは別の自動 fallback であり、RAM 不足の扱いは `STRATA_ARENA_RAM_FALLBACK` 等にも依存する（`engine/src/program/generate.cpp:8595-8605`, `engine/src/program/generate.cpp:8871-8911`）。
- mmap は expert データのコピーを最初から確保せず、ファイルを読み取り専用で開いて map する。ファイルを見つけられない、サイズや layout が合わない、mapping に失敗する場合は open が失敗し、通常の mmap 経路ではエラーを stderr に出して終了コード 1 となる（`engine/src/core/expert_source.cpp:1500-1523`, `engine/src/core/expert_source.cpp:1600-1633`, `engine/src/core/expert_source.cpp:1640-1657`, `engine/src/program/generate.cpp:8631-8643`）。

## 出力とエラー

明示指定で mmap source を開いた後、stderr に `experts via mmap (--mmap-experts; ...)` を出す。source を開けない場合はエラー内容を stderr に出し終了コード 1。RAM 不足で arena から自動 fallback した場合はその旨を stderr に出し、`--serve` では stdout にも通知する（`engine/src/program/generate.cpp:8645-8647`, `engine/src/program/generate.cpp:8876-8889`）。

## 根拠

- `engine/src/program/generate.cpp:874`, `engine/src/program/generate.cpp:4217-4219`: 既定値と parser 登録。
- `engine/src/program/generate.cpp:4866-4872`, `engine/src/program/generate.cpp:4221-4257`: incompatibility validation と関連フラグの設定。
- `engine/src/program/generate.cpp:5336-5341`, `engine/src/program/generate.cpp:8619-8647`: Metal 経路、source の選択・起動時表示。
- `engine/src/core/expert_source.cpp:1499-1580`, `engine/src/core/expert_source.cpp:1600-1665`, `engine/src/core/expert_source.cpp:1801-1869`: pack/ GGUF の mmap と open validation。
- `engine/src/program/generate.cpp:8871-8911`: arena の RAM 不足時に file source へ切り替える経路。

調査ではソースの parser と実装を確認した。GPU 実行や既存バイナリの `--help` は実行していないため、実機での性能差・OS cache の保持量はこの文書では測定していない。
