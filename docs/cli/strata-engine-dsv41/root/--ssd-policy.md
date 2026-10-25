# `--ssd-policy`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（独立したエンジン CLI、サブコマンドなし） |
| オプション | `--ssd-policy` |
| 別名 | なし |
| 値 | `lru`、`lfu`、`lfulru` のいずれかを意図した文字列値 |

## 役割

RAM 上の expert store が容量不足時にどの expert slot を置き換えるかを指定します。この store はモデルファイルから読み込んだ expert を独自の RAM slot に保持し、CPU lane の読み出しなどに使います。オプション名に `ssd` とありますが、ここで選ぶのは SSD の設定ではなく RAM store の置換ポリシーです（`src/dsv41/ds4_model.hpp:37-41`、`src/dsv41/ds4_store.hpp:1-16`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ssd-policy lfu --ids 1,2,3
```

`--pack` と推論入力など、通常の起動に必要な引数も指定します。ヘルプの使用法では `--ssd-policy lru|lfu|lfulru` と記載されています（`src/dsv41/ds4_main.cpp:85-93`）。

## 値と既定値

- `lru` は内部値 `0`、`lfu` は `1`、`lfulru` は `2` に変換されます（`src/dsv41/ds4_main.cpp:1218-1221`）。
- 省略時の `Options::ssd_policy` は `0`、すなわち `lru` です（`src/dsv41/ds4_model.hpp:41`）。
- parser は値を文字列として取得し、`lfu` と `lfulru` 以外をすべて `0` にします。したがって、空文字や未知の文字列もエラーにならず `lru` 相当になります。値の形式を検証する処理はありません（`src/dsv41/ds4_main.cpp:1200-1208,1218-1221`）。
- 値を省略して次の引数がない場合は `--ssd-policy needs a value` を stderr に出し、終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。同じ option を複数回指定した場合は parser が各回代入するため、最後の指定が残ります（`src/dsv41/ds4_main.cpp:1200-1221`）。

## 実行時の動作

model load 時に RAM store の設定へポリシーを渡します。環境変数 `DS4_STORE_POLICY` が設定されている場合は、その文字列を `atoi` で整数化した値が CLI の値より優先されます。未設定なら `--ssd-policy` の内部値が使われます（`src/dsv41/ds4_model.cu:4487-4494`）。そのため CLI で選択しても、この環境変数がある場合は CLI 値が適用されません。

slot を置き換えるとき、LRU は最後に触れた時刻 `tick` の小さい slot を優先します。LRU 以外は expert の decayed hit count (`heat`) を主スコアにし、同点時の順序付けに `tick` の微小値を加えます。LFU の heat は expert へのアクセスで増え、該当 layer の 240 access ごとに 0.97 倍されます（`src/dsv41/ds4_store.hpp:389-396,480-509`）。

現行コードでは `lfulru` は内部値 `2` になりますが、store の enum には `kLru=0` と `kLfu=1` しかなく、スコア選択は `kLru` かどうかの判定です。したがって `2` は「LRU 以外」の LFU スコア経路を通り、`lfu` と同じ扱いになります。help と値の対応付けは `lfulru` を示しますが、別個の「LFU の後に LRU」という処理はこの store のスコア計算では確認できません（`src/dsv41/ds4_store.hpp:48,389-396,480-509`）。

## 適用条件と副作用

この設定が効果を持つのは RAM store が初期化される場合です。store 容量は `--ssd-cache` の値を使いますが、環境変数 `DS4_STORE_GB` が設定されていればそちらで上書きされます。実際に store を初期化するのは容量が正で、pack が GGUF であり、model の layer が存在し、先頭 layer の形式が MXFP4 で、`file_experts` が有効な場合です。それ以外ではポリシーを使う store は作られません（`src/dsv41/ds4_model.cu:4457-4468,4470-4472`）。容量の自動値・上限などは `--ssd-cache` 側の設定で決まり、この option 自体は容量を変更しません（`src/dsv41/ds4_model.hpp:37-41`）。

store は固定 arena を予約し、slot を必要に応じて commit します。ポリシーは読み込み済み・ready・pin されておらず GPU から可視でもない slot の置換候補選びに使われます。使用中や GPU 可視の slot は候補から除外されます（`src/dsv41/ds4_store.hpp:11-16,73-108,480-509`）。これは store の RAM 使用・expert cache の保持内容に影響します。`--no-expert-cache` と同じ設定ではなく、このオプションは RAM store の置換順だけを指定します（`src/dsv41/ds4_main.cpp:1218-1223`、`src/dsv41/ds4_model.cu:2750-2777`）。

store 初期化に失敗すると `ds4: --ssd-cache: the store could not start` を stderr に出して store を作らず戻ります。呼び出し側は `init_store()` の戻り値を確認しないため、この経路だけで model load を失敗させる処理はありません（`src/dsv41/ds4_model.cu:2775-2778,4524-4529`）。

## 出力とエラー

- 未知の option は `unknown option ...` と usage を stderr に出し、終了コード `2` です。`--ssd-policy` の値が未知である場合はこの経路にはならず、LRU にフォールバックします（`src/dsv41/ds4_main.cpp:1218-1221,1266-1272`）。
- store が初期化できた場合、stderr に RAM store の slot 数・容量・policy の数値・reader thread 数・読み出し方式を表示します。policy 表示は文字列ではなく内部数値です（`src/dsv41/ds4_model.cu:4522-4537`）。
- 本文書はソース checkout の parser と利用箇所を調査したものです。同一 revision の既存実行ファイルによる `--help` 照合やビルド・実行は行っていません。

## 根拠

- CLI 使用法と parser、値の変換・欠落値・未知 option の処理: `src/dsv41/ds4_main.cpp:85-93,1200-1221,1266-1272`
- 値の既定値と store の役割: `src/dsv41/ds4_model.hpp:37-41`
- 環境変数による優先と store の適用条件: `src/dsv41/ds4_model.cu:4457-4472,4487-4494`
- 置換スコア、heat の更新、候補 slot の条件: `src/dsv41/ds4_store.hpp:48,389-396,480-509`
- 初期化失敗・起動時の診断出力: `src/dsv41/ds4_model.cu:4522-4537`
