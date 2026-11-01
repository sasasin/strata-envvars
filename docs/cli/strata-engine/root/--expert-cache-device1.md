# `--expert-cache-device1`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--expert-cache-device1` |
| 別名 | なし |
| 値 | 非負の slot 数 `N` または `auto` |

## 役割

primary GPU（通常 CUDA0）の expert cache に入らない expert blob を、helper GPU の最初の tier に常駐させます。通常の device 配置では CUDA1 が対象です。helper は prompt の計算先ではなく、デコード時に担当 expert の行を計算し、その結果を pinned host memory 経由で返します。GPU 間 P2P はこの helper 経路の要件ではありません。parser の help は CUDA1 に N 件または空き容量分を配置すると説明し、実装では `RemoteExperts` に tier を作って各層の処理へ登録します（`src/program/generate.cpp:1127`, `src/program/generate.cpp:7603-7608`, `src/program/generate.cpp:7722-7728`, `src/core/expert_source.cpp:4752-4765`, `src/core/expert_source.cpp:4800-4805`, `src/core/expert_source.cpp:4820-4825`）。

## 使い方

engine の引数として、モデル pack と profile、primary 側 cache とともに指定します。

```text
strata generate --pack /path/to/pack --tokens "1,2,3" --expert-profile /path/to/profile.bin --expert-cache auto --expert-cache-device1 auto
```

`--expert-profile`、`--expert-cache`、`--tokens` はこの例で helper tier を有効にするための関連引数です。engine の形式は `strata generate --pack DIR --tokens LIST [options]` です（`src/program/generate.cpp:930-936`, `src/program/generate.cpp:7607-7611`）。

## 値と既定値

- 省略時は 0 slots（無効）です。options 構造体は device1〜3 の slot 数をゼロ初期化します（`src/program/generate.cpp:676-680`）。
- `N` は `atoi` で整数に変換され、正数の場合に tier を開きます。`0` は無効、負数は `invalid sampling or resource parameter` で終了コード 2 になります。数値の厳密な字句検証は parser にありません（`src/program/generate.cpp:3149-3154`, `src/program/generate.cpp:3968-3975`）。
- `auto` は大きな slot 上限と auto sizing フラグに変換されます。起動時に rank 順の expert blob を実際のサイズと当該 GPU の空き VRAMに基づいて選び、少なくとも 512 MiB を残せる範囲で配置します。これは容量の自動決定であり、性能に基づく調整ではありません（`src/program/generate.cpp:3151-3153`, `src/core/remote_experts.cpp:153-169`, `src/core/remote_experts.cpp:182-185`）。
- 同じ option を複数回指定すると parser のループで後の値が同じ配列要素を上書きします（`src/program/generate.cpp:3003-3008`, `src/program/generate.cpp:3149-3153`）。

## 実行時の動作

`--expert-cache-device1` は device1〜3 共通の parser 分岐で末尾の数字を tier index に変換し、数値と auto flag をそれぞれ保存します（`src/program/generate.cpp:3149-3153`）。remote tier の初期化は device1 が正数のときに始まり、`--expert-profile`、正数化された primary `--expert-cache`、CPU expert pool が揃わなければ拒否されます（`src/program/generate.cpp:7607-7612`）。

single-GPU primary の通常配置では `device1` は可視 CUDA device 1 です。`STRATA_PRIMARY_DEVICE` が非ゼロなら primary 以外の可視 device を順に helper に割り当てます。layer split 併用時は stage が使わない可視 GPU が helper に割り当てられます（`src/program/generate.cpp:3566-3574`, `src/program/generate.cpp:3663-3675`, `src/program/generate.cpp:3738-3752`）。helper は primary cache と重複しない expert を選び、GPU 上の cache に blob を埋めて検証します（`src/core/remote_experts.cpp:160-175`, `src/core/remote_experts.cpp:187-205`）。

通常の prompt は primary 側で処理され、helper cache はデコードの expert 行計算に使われます。serve 中に `STRATA_PREFILL_HELPER_SOURCE` を有効にした場合に限り、prompt が helper cache 内の blob を読み出し元として使う経路もあります（`src/program/generate.cpp:9346-9360`）。`--remote-expert-opt` は別 option で、serve 専用です。device1 cache が有効な場合に helper 最適化を接続します（`src/program/generate.cpp:3155`, `src/program/generate.cpp:3981-3983`, `src/program/generate.cpp:7603-7608`）。

## 適用条件と副作用

- device1 が正数で有効なら、device2/3 は前段 tier が有効である必要があります。device2/3 だけを指定すると resource validation で拒否されます（`src/program/generate.cpp:3970-3975`）。
- `--peer-device` は helper cache と併用できず、`--peer-device` と `--layer-split` の組み合わせも拒否されます（`src/program/generate.cpp:3985-3991`）。
- helper GPU は可視で、primary GPU と異なり、割り当て対象の expert が残っていなければなりません。auto では 512 MiB を残した上で一件も配置できない場合に失敗します。明示数が空き容量を超えて 512 MiB 未満しか残さない場合も失敗します（`src/core/remote_experts.cpp:141-150`, `src/core/remote_experts.cpp:160-185`）。
- 初期化時に helper GPU 上へ expert cache、CUDA stream、GPU 作業バッファを確保し、pinned host staging buffer を作ります。結果は pinned host rows 経由で primary に返ります（`src/core/remote_experts.cpp:187-224`, `src/program/generate.cpp:7685-7687`）。
- 同一 layer に割り当てられた helper expert は CPU pool の担当から除外され、helper が計算します。helper の開始・完了に失敗すると layer の処理を失敗として伝播します（`src/core/expert_source.cpp:4752-4765`, `src/core/expert_source.cpp:4800-4825`）。

## 出力とエラー

初期化成功時は stderr に helper の CUDA ordinal、追加 expert 数、GiB、pinned host rows 経由で結果を返す旨を表示します（`src/program/generate.cpp:7685-7687`）。無効な resource 値、device1 を伴わない device2/3、必要な profile/cache/pool の不足は終了コード 2 です（`src/program/generate.cpp:3970-3975`, `src/program/generate.cpp:7607-7611`）。helper GPU の不可視、空き容量不足、cache 確保・blob 読み込み・検証など初期化失敗はエラーを stderr に出して終了コード 1 になります（`src/core/remote_experts.cpp:141-150`, `src/core/remote_experts.cpp:172-205`, `src/program/generate.cpp:7677-7687`）。option の値が末尾にない場合は `<option> needs a value` を stderr に出し終了コード 2 です（`src/program/generate.cpp:3005-3007`）。

## 根拠

- parser の help と値受理: `src/program/generate.cpp:1123-1135`, `src/program/generate.cpp:3145-3157`
- 値 validation と関連条件: `src/program/generate.cpp:3968-3991`, `src/program/generate.cpp:7607-7612`
- primary/helper の device 割り当て: `src/program/generate.cpp:3566-3574`, `src/program/generate.cpp:3663-3675`, `src/program/generate.cpp:3738-3752`
- helper cache の sizing・確保・失敗: `src/core/remote_experts.cpp:141-205`, `src/core/remote_experts.cpp:207-239`
- expert 行の実行と host 側への結果統合: `src/core/expert_source.cpp:4752-4825`, `src/program/generate.cpp:7722-7728`

範囲: ソース checkout と parser/help 実装を調査しました。GPU の実機がないため、device ごとの driver 挙動、実際の空き VRAM、性能差は確認していません。Release binary の help は実行していません。
