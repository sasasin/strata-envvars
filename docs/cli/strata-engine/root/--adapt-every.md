# `strata --adapt-every`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのルート引数） |
| オプション | `--adapt-every` |
| 別名 | なし |
| 値 | 整数。適応間隔（検証ラウンドまたは serve の window 数）。0 以下は適応 tier を無効にする条件として扱われる |

## 役割

GPU の専門家（expert）キャッシュに空き枠があるとき、ルーティング実績をもとに常駐する expert を入れ替える適応 tier の実行間隔を指定する。通常の speculative decode では検証ラウンド数、serve の一部では window 数を基準にする。実際に tier が働くには `--adapt-swaps` も正であり、GPU 側に全 expert が常駐していないなどの条件を満たす必要がある（`engine/src/program/generate.cpp:1043-1049,14906-14907,21949-21954`）。

## 使い方

```sh
# 各 8 検証ラウンドの間隔で適応する
strata --native MODEL.gguf --adapt-every 8

# 静的な GPU 常駐構成にする（適応を無効化）
strata --native MODEL.gguf --adapt-every 0
```

`MODEL.gguf` は利用するモデルのパスに置き換える。例はエンジンの通常のモデル引数にこのオプションを加える形を示す。

## 値と既定値

- 値を必ず 1 個取る。値を省略すると parser の `next()` が `--adapt-every needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3837-3842,4053`）。
- 既定値は `4`（`engine/src/program/generate.cpp:1043-1046`）。正の値を interval として利用する。0 以下では適応用 usage 集計の初期化や適応処理が抑止され、tier は無効扱いになる（`engine/src/program/generate.cpp:11706,11723-11724,14906-14907`）。
- parser は `std::atoi` で変換し、値の範囲や数値形式を独自に検証しない（`engine/src/program/generate.cpp:4053`）。したがって数値として読めない文字列は `atoi` の結果 0 となり、適応が無効になる。負数も正の interval ではなく無効側として扱われる。整数の上限や範囲エラーはこの parser からは確認できない。
- 適応の実効間隔は、指定値のまま固定とは限らない。明示指定がなく speculative mode（`--spec >= 2`）のとき、環境変数 `STRATA_SPEC_ADAPT_EVERY` と `STRATA_SPEC_ADAPT_WARM` がともに条件を満たせば、最初の warm-up ラウンドだけ短い間隔を使う（`engine/src/program/generate.cpp:5072-5082`）。
- GPU expert cache の占有率が 15〜65% の条件では、適応が有効で値を明示していなければ `--adapt-every` の実効既定値を `2` にする（`engine/src/program/generate.cpp:12066-12085,14858-14871`）。明示値はこの補正で上書きされない。この分岐は `--adapt-swaps` と `--adapt-decay` の未指定値も変更する。

## 実行時の動作

parser は値を `o.adapt_every` に設定し、コマンドラインで指定されたことを `o.adapt_every_given` に記録する（`engine/src/program/generate.cpp:4053`）。これにより speculative warm-up と 15〜65% cache coverage の適応既定値補正が、明示値を保持できる（`engine/src/program/generate.cpp:5076-5082,12073-12080`）。

適応 tier が有効な経路では、expert routing の使用量を集計し、interval ごとに実績を snapshot して適応処理へ渡す。snapshot 時には累積 usage を `--adapt-decay` の係数で減衰させる（`engine/src/program/generate.cpp:15245-15251`）。適応処理は入れ替え候補を計算し、保留中の入れ替えがあれば新しい処理を開始しない（`engine/src/program/generate.cpp:15253-15257`）。通常の speculative decode は `adapt_iv(rounds)` を使って interval を判定する（`engine/src/program/generate.cpp:21949-21954,22953-22959`）。

一部の serve loop では interval を window 数で数える（`engine/src/program/generate.cpp:15701-15712,17144-17152`）。`--batch-groups` の pipelined path は `STRATA_PIPE_ADAPT_EVERY` から別の interval を読み、その値を使うため、`--adapt-every` の値がその path の周期を直接決めない（`engine/src/program/generate.cpp:17902-17920`）。

## 適用条件と副作用

- 適応は `adapt_every > 0` かつ `adapt_swaps > 0` のとき有効判定される。expert が全て常駐している、または GPU 側に入れ替え可能な常駐枠がない場合などは、usage 集計・入れ替えが行われない（`engine/src/program/generate.cpp:11706,14906-14907`）。
- `--adapt-every 0` は静的 residency の指定として help にも記載されている（`engine/src/program/generate.cpp:1397-1399`）。この値は適応 tier を無効にするため、`--expert-profile-save` が必要とする適応 tier の条件を満たさず、serve 時には保存を行わない旨の stderr メッセージが出る（`engine/src/program/generate.cpp:14996-15004`）。
- `--adapt-async` を使う場合も、適応 tier が無効なら asynchronous tier は成立せず、無効理由として「the adaptive tier is off」が設定される（`engine/src/program/generate.cpp:11717-11732`）。
- HIP の AMD iGPU で `STRATA_IO_PREFETCH` が有効なとき、適応 tier も有効なら既知の GPU reset 警告を stderr に出すが、そのまま処理を続ける（`engine/src/program/generate.cpp:8660-8666`）。
- 適応処理に必要な交換バッファを確保できない場合、`--adapt-swaps` による容量縮小を試し、それも失敗するとエラーを stderr に出して終了コード 1 で戻る。この失敗経路は interval の値ではなく適応 tier 全体の条件に依存する（`engine/src/program/generate.cpp:12102-12110`）。

## 出力とエラー

適応が動作した generate 経路では、終了時の標準出力に入れ替えた expert 数と interval を表示する（`engine/src/program/generate.cpp:25208-25210`）。serve の asynchronous tier では起動時に interval として stderr に表示する（`engine/src/program/generate.cpp:15510-15517`）。適応 tier が無効な場合は tier off として状態表示される（`engine/src/program/generate.cpp:11717-11724,12117-12123`）。

値の欠落は終了コード 2、交換バッファ確保の失敗は該当経路で終了コード 1 となる。値の負数や不正な数値文字列について、専用の validation error は parser にない（`engine/src/program/generate.cpp:3839-3842,4053,12102-12110`）。

## 根拠

- `engine/src/program/generate.cpp:1043-1054` — interval の初期値と適応 tier の関連設定。
- `engine/src/program/generate.cpp:3837-3842,4053` — 引数欠落時の処理と parser の変換・明示指定記録。
- `engine/src/program/generate.cpp:5072-5082,12066-12085,14858-14871` — speculative warm-up と cache coverage による未指定時の interval 調整。
- `engine/src/program/generate.cpp:15245-15257,21949-21954` — routing 使用量の減衰、snapshot、interval ごとの適応開始。
- `engine/src/program/generate.cpp:14906-14907,14996-15004,12102-12110` — 適用条件、関連する保存条件、失敗経路。

調査範囲は索引で `strata-engine` の `root/` parser として指定された `engine/src/program/generate.cpp`。この文書では同リポジトリ内の別 backend parser の挙動を統合していない。
