# `--threads`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-load` |
| コマンド | `strata-load` |
| オプション | `--threads` |
| 別名 | なし |
| 値 | 整数。読み込み worker 数の指定 |

## 役割

expert arena を読み込む `strata-load` の layer 読み込みに使う worker 数を指定します。parser は値を整数に変換し、`load_experts` へ渡します。実装では layer を atomic counter で worker に割り当てます。

## 使い方

```sh
strata-load --file experts.bin --threads 4
```

## 値と既定値

- 省略時は 8 です。
- 値の取得は `std::atoi` によるため、明示的な数値形式・範囲検証はありません。数値として先頭部分を解釈できない文字列は 0 になり、`--threads` の直後に値がない場合は `--threads needs a value` を stderr に出して終了コード 2 で終了します。
- 読み込み関数は 1 未満を 1 に補正します。したがって `0` や負数でも読み込みは 1 worker で行われますが、最終の成功メッセージには補正前の指定値が表示されます。
- 同じオプションを複数回指定した場合、引数走査中に変数を順次代入するため最後の値が使われます。

## 実行時の動作

`--threads` は `load_experts(..., threads, chunk)` に渡され、`load_experts_ranges` を経由します。読み込み関数は `threads - 1` 個の `std::thread` を作成し、呼び出し元スレッドも worker として処理に参加します。各 worker は次の layer を atomic counter から取得し、その layer のデータを chunk ごとにファイルから読み込みます。完了後、成功時の `loaded ... with %d threads ...` 行には parser が保持する `threads` の値が出ます。

`--layers` の既定値は 2 で、worker が処理を分担する単位も layer です。そのため既定の layer 数では同時に担当できる layer は最大 2 つです。指定 thread 数が layer 数を超えると、余分な worker も生成されますが、処理する layer が割り当てられないことがあります。各 worker は chunk サイズの読み込み buffer を用意するため、thread 数を増やすと worker 側の buffer 確保も増えます。

## 適用条件と副作用

- `--threads` はファイルから arena への読み込み部分に適用されます。`--stream` が指定された場合の後続の host-to-device stream 計測には、この値は渡されません。
- デフォルトでは読み込み先に pinned arena を確保します。`--threads` はこの確保方法を変更しません。`--no-pin` 指定時は代わりに `malloc` が使われます。
- thread 数は上限・CPU 数との照合を受けません。多数を指定した場合の resource 使用量について、CLI 側に追加の制限処理は確認できません。

## 出力とエラー

- 読み込み成功時、thread 数は完了統計行に表示されます。これは補正前の CLI 指定値です。
- ファイルを開けない、seek に失敗する、chunk の短い読み込みが起きる場合、worker が error を記録します。読み込み関数は `load_experts: ...` を stderr に出し、CLI は `loading the experts failed: ...` を stderr に出して終了コード 1 で終了します。
- `--threads` の不正値自体を拒否する専用エラー経路はありません。thread 作成などの実行時失敗について、CLI 独自のエラー処理はこの経路では確認できません。

## 根拠

- `src/core/load_main.cpp:14-18` — CLI の変数初期値（`threads = 8`）。
- `src/core/load_main.cpp:24-43` — 手動 parser、`--threads` の `atoi` 変換、help・未知引数の処理。
- `src/core/load_main.cpp:45-47` — `--file` 必須検査と layer 数からの arena byte 数計算。
- `src/core/load_main.cpp:52-70` — pinned / malloc の確保分岐、読み込み呼び出し、失敗出力と終了コード。
- `src/core/load_main.cpp:73-75` — 成功統計行に渡す thread 数。
- `src/core/pinned.cu:681-685` — layer range を作り `load_experts_ranges` へ転送。
- `src/core/pinned.cu:838-846` — 1 未満の thread 数を 1 に補正。
- `src/core/pinned.cu:856-880, 932-935` — worker ごとの buffer、layer の割当、worker 作成と join。
- `src/core/pinned.cu:865-870, 888-906, 937-942` — file open、seek、short-read の失敗処理。

調査範囲は上記 revision の parser と読み込み実装です。CLI `--help` は実行せず、ソース内の help 文字列を確認しました。異なる build 構成での実行時 thread 作成上限や OS 固有の制約は調査していません。
