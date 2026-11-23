# `--engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--engram` |
| 別名 | なし |
| 値 | Engram shard の `.strata` ファイルパス（文字列） |

## 役割

Hy4-Flash モデルに対応する Engram shard を指定する。指定した shard を読み込み、モデルの4つの Engram 層でトークン列から求めた row ID の行データを取得して推論へ加える。オフライン推論と `--serve` の両方で同じ値が使われる。

## 使い方

```sh
# Metal runner でモデルと Engram shard を指定してトークン列を処理する
strata-hy4-metal --model model.strata --engram engram-q8.strata --tokens prompt.ids

# 同じ shard を使って server モードを起動する
strata-hy4-metal --model model.strata --engram engram-q8.strata --serve
```

## 値と既定値

- 値は `--engram` の直後の引数をそのままパスとして受け取る。オプション自体に明示的な既定値はなく、省略時は空文字列のままで、Engram shard を開かない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1509`）。
- `--engram` の値について parser 独自の形式検証やパス存在確認は行わない。初期化時に Strata reader がファイルを開き、Engram shard profile かを検査する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:683-685`、`engine/src/hy4flash/run/hy4_engram.cpp:446-458`）。
- 引数の欠落を検出する専用処理は parser にない。値を省略した場合の安全なエラー動作はソースから確認できないため、省略しないこと。
- 複数回指定時はループ内で後のパスが `engram` 変数を上書きする。別オプション `--no-engram` は独立した真偽値で、指定されると順序にかかわらず `--engram` のパスを初期化に渡さない（同 `main.cpp:1504-1518,1762`）。

## 実行時の動作

`--serve` を使わない場合、runner 初期化時に `--no-engram` が指定されていなければ、指定 shard を `EngramIO::open` に渡す。モデル manifest の Engram metadata は shard の有無にかかわらず読み込まれる。shard が開かれた場合は `engram_ready` が有効になり、対象層の処理でトークン列を hash し、4 module 分の row を shard から取得して Metal の `engram_rows` / `engram_apply` 処理に渡す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:681-705,755-769,816-824,1300-1320`）。

`--serve` の場合はパスを `ServeOpts` に引き継ぎ、server runner の初期化で同じく `--no-engram` の有無を反映して shard を開く（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1647`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-37,239-243`）。

Shard は EngramShard profile である必要がある。読み込み時には model `.strata` の Section 2 seed が利用可能かも確認され、形式・row byte 数・Section 4 SHA が一致する場合に seed が有効になる。seed が使えない場合の代替は shard の page read である（`engine/src/hy4flash/run/hy4_engram.cpp:446-490`）。これはキャッシュ実装の動作であり、CLI 引数の追加検証ではない。

## 相互作用と副作用

- `--no-engram` は Engram shard を使わない指定で、`--engram` より優先される。shard を省略した場合も `engram_ready` は立たず、Engram 層の計算・row fetch は実行されない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1518,1762`、同 `:683-685,1304`）。ただしモデル metadata の読み込みは引き続き行われる（同 `:681-682`）。
- `--engram-cache-mib` は Metal runner が「not used by the Metal runner」と stderr に出す別オプションであり、`--engram` の shard path や Metal の Engram cache 容量を設定するものではない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）。
- Engram row の準備は非同期 prefetch される場合があり、処理時に future の完了を待つ。Shard を指定するとファイル I/O、row/page buffer の割り当て、LRU 等のメモリ利用が発生する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:771-805`、`engine/src/hy4flash/run/hy4_engram.cpp:557-629`）。
- Vision 経路では通常の token row hash 後、画像位置の Engram contribution を無効化する処理がある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:761-764`）。

## 出力とエラー

- shard の open や metadata 読み込みに失敗すると runner 初期化が失敗し、オフライン経路は stderr に `init: <理由>` を出して終了コード 1 を返す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1764`）。shard が EngramShard profile でない場合のエラー文は `not an EngramShard profile: <path>`（`engine/src/hy4flash/run/hy4_engram.cpp:450-453`）。
- 推論中の row fetch に失敗すると、Engram 準備処理から失敗が返り、オフライン経路は stderr に `forward: <理由>` を出して処理を中断する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:782-805,1794-1796`）。行 ID 範囲外、page buffer のメモリ不足、short read などが失敗理由になり得る（`engine/src/hy4flash/run/hy4_engram.cpp:557-563,602,628-629`、`engine/src/hy4flash/run/hy4_engram.h:65-67`）。
- 終了時には Engram の lookup、seed/LRU hit、page read 数・読取量・I/O 時間を stderr に出力する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1982-1984`）。server 経路のプロトコル出力や失敗時の終了コード全体は、このオプションの parser 範囲だけからは一般化できない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1518` — CLI 変数と `--engram` / `--no-engram` の parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1647,1762-1764` — server への値引き継ぎとオフライン初期化、初期化失敗処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-705,755-805,816-824,1300-1320` — metadata・shard の読み込み、row fetch、Metal 層への適用。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:24-37,239-243` — server runner の設定と shard 初期化。
- `engine/src/hy4flash/run/hy4_engram.cpp:446-490,557-629` — shard profile の検査、seed 利用条件、row/page fetch のエラー経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603,1794-1796,1982-1984` — Metal で未使用の cache option、forward エラー、Engram 統計の出力。
