# `strata-hy4-metal --cold-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--cold-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデル全体を Metal バッファへラップする通常経路を避け、expert 部分を必要時に読み込む cold-expert モードを強制します。モデルファイルが Metal の最大バッファ長または推奨作業セットに対して大きい場合は、このオプションを省略しても自動で同じモードになります。parser は `force_cold` を設定し、モデル読込時のモード判定へ渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1544,1617-1618,234-238`）。

## 使い方

```sh
# モデルの expert を cold-expert モードで読み込んで、トークン列から生成
strata-hy4-metal --model model.strata --tokens ids.txt --gen 128 --cold-experts
```

`--model` と `--tokens` はこのコマンドの入力指定例です。`--cold-experts` 自体は値を取りません。モデル読込を行う `--serve` 経路でも parser 後に共通のモデル読込が通るため、このフラグが適用されます（同: `1504-1515,1589,1611-1622`）。

## 値と既定値

- 真偽フラグで、値・短縮別名はありません。指定すると `force_cold = true` になります。複数回指定しても同じ真偽値を設定するだけです（同: `1490,1504-1506,1544`）。
- 指定しない場合の `force_cold` は `false` です。ただし、ファイル長を 16,384 byte 単位に切り上げた `len` が `maxBufferLength` を超える場合、または推奨作業セットが 0 より大きくファイルサイズがその 88% を超える場合は、自動的に cold-expert モードになります（同: `234-238`）。
- parser にこのフラグ固有の値検証はありません。値を続けて渡す構文ではなく、後続の未認識引数は unknown flag として扱われます（同: `1544,1604-1608`）。

## 実行時の動作

モデル読込時に `cold_experts = force_cold || 条件による自動判定` とします。通常モードではモデル全体を read-only/private で `mmap` し、全体を Metal buffer に wrap します。cold-expert モードでは Section 1 の trunk のみを mmap / wrap し、Section 4 の expert 本体は全体 wrap の対象から外します（同: `214-255`）。

Runner は cold-expert モードで最大 expert サイズを 4 KiB 単位に丸めた slot を持つ GPU 側 LRU cache を確保し、directory の hotness 順から最大 512 expert を起動時に先読みします。モデル層の router が選んだ expert の cache miss は `pread` でモデルファイルから cache へ読み込み、該当層の MoE kernel にはその cache を渡します（同: `637-679,898-961,1168-1174`）。

キャッシュ容量の初期予算は推奨作業セット・既割当量から 4 GiB の余裕を引き、余裕がない場合は 2 GiB とします。`STRATA_METAL_EXP_CACHE_GB` が空でない場合は `atof` の結果を 10^9 倍した値で予算を置き換えます。その後、会話 KV の追加割当見込みを差し引き、Metal の最大バッファ長などで上限を調整し、少なくとも 512 expert 分を確保する下限処理があります（同: `639-659`）。この環境変数の数値形式・境界値について、当該コード内に追加の検証は確認できません。

他の実行設定との相互作用として、`--chunk` を正の値で指定しない場合の既定 chunk は cold-expert モードで 2048、それ以外は 4096 です。正の `--chunk` 指定はこの既定値を置き換えます。これは `--serve` の `ServeOpts` と通常実行の Runner 構築の双方で使われます（同: `1642-1644,1708-1715`）。`--load-only` を併用した場合はモデル読込後に終了するため、後段の Runner 初期化による expert cache 確保・先読みには進みません（同: `1630-1636,1713-1715`）。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal 実装です。指定するとモデルファイルを読み取り専用 mmap し、expert の miss 時に `pread` を行い、Metal に LRU cache buffer を確保します。モデルを変更する処理はこの経路では確認できません（同: `228-255,637-679,939-960`）。
- cold-expert モードでは Engram の非同期準備条件から除外され、prefill の 7 層ごとの command buffer batching 条件からも除外されます（同: `1304-1311,1322-1328`）。
- モデル読込時に trunk の mmap が失敗すると `mmap sec1 failed`、通常モードで全体 mmap が失敗すると `mmap failed` が読込エラーになります。呼び出し元は `load: <理由>` を stderr に出し、終了コード 1 で戻ります（同: `239-252,1617-1622`）。cold mode の初期 cache 先読みは読み込みサイズが一致した場合だけ slot 登録しますが、後続の miss 読込では `pread` の戻り値を検査していません。短い読み込み時の回復動作・エラー通知はこの箇所から確認できません（同: `663-675,939-960`）。
- cold mode 選択時は stderr に trunk mmap の概要が出力され、Runner 初期化後に cache 容量・slot 数・先読み数も出力されます（同: `245-255,677-679`）。

## 根拠

- parser 登録と未知引数処理: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1544,1604-1609`。
- 指定値のモデル読込への受け渡し、自動判定、通常/cold の mmap 差: `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-255,1617-1622`。
- LRU cache の予算、環境変数、初期先読み、cache miss の `pread` と MoE 呼出し: `engine/src/hy4flash/metal/hy4_metal_main.cpp:637-679,898-961,1168-1174`。
- chunk 既定値、Engram・prefill batching との条件、`--load-only` の早期終了: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1304-1311,1322-1328,1630-1636,1642-1644,1708-1715`。
- 文書配置と scope: `docs/cli/README.md:1358-1367` では `strata-hy4-metal` の Metal 節に `strata-hy4/metal/--cold-experts.md` が登録されています。
