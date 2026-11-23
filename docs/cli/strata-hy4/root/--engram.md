# `--engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--engram` |
| 別名 | なし |
| 値 | Engram shard のファイルパス（文字列） |

## 役割

Hy4-Flash のモデル実行で使う Engram shard を指定します。CUDA/HIP の通常実行と `--serve` のどちらにも渡され、初期化時に shard を開けると Engram の検索行を読み込める状態になります。省略時は shard を開かず、`--no-engram` を指定した場合もこの値は使われません。

## 使い方

```sh
# トークン ID ファイルを使った通常実行
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 128

# サーバーモードで同じ shard を指定
strata-hy4 --serve --model SQ64.strata --engram Engram-Q8.strata

# 値を指定していても Engram shard の利用を無効にする
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --no-engram --tokens ids.txt
```

## 値と既定値

値は次の引数をそのまま文字列として受け取ります。parser では拡張子やパスの存在を検証しません。指定を省略すると空文字列のままになり、Runner 初期化時に shard を開きません。複数回指定した場合は最後の `--engram` の値が残ります。`--no-engram` は別の真偽フラグで、コマンドライン上の順序にかかわらず有効なら shard のパスを空にして初期化します（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,375-384,483-494,703-705`）。

値を省略すると parser は `ERR --engram needs a value` を stdout に出して終了コード 2 で終了します。未知のオプションも終了コード 2 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-384,498-505`）。

## 実行時の動作

通常実行では `--engram` の値が Runner の `init` に渡されます。`--serve` では同じパスが `ServeOpts` に格納され、serve 側の Runner 初期化にも渡ります。どちらの経路でも `--no-engram` が優先されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-564,703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:43-49,314-317`）。

Runner はまずモデル shard から Engram のメタデータを読みます。その後、Engram path が空でない場合だけ `EngramIO::open` を呼び、shard を開いて Engram 検索を有効にします。したがって `--no-engram` はモデル側のメタデータ読み込みを省く指定ではなく、別 shard の読み込み・検索を止める指定です（`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`）。

`EngramIO::open` はファイルを開き、profile が `EngramShard` であることと section 4 の配置を確認します。モデルに埋め込まれた section 2 の seed が shard の section 4 と一致し、形式・行サイズ・範囲の条件を満たす場合は seed を使います。条件を満たさない seed は採用されず、LRU cache を構築して shard からの読み込みを行います（`engine/src/hy4flash/run/hy4_engram.cpp:446-503`）。

## 適用条件と副作用

`--engram` 自体に parser 側の範囲検証はありません。通常実行では `EngramIO::open` が shard の読み込みや profile・section 配置を検証し、失敗すると Runner 初期化が失敗します。Engram shard を指定した場合、LRU cache 用メモリを確保し、推論時には shard のページを読み込みます。cache の既定行数は RAM 制約に応じて調整され、`HY4_ENGRAM_CACHE_MIB` が設定されていればその値から行数を計算します（`engine/src/hy4flash/run/hy4_graph.hip.h:1660-1676`）。

## 出力とエラー

通常実行の Runner 初期化に失敗すると `init: <理由>` を stderr に出して終了コード 1、serve では `ERR init: <理由>` を protocol 出力に送り、終了コード 1 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:314-317`）。shard の open 時にはファイル読み込みエラー、EngramShard 以外の profile、section 4 の非 4 KiB 配置などが失敗理由になり得ます（`engine/src/hy4flash/run/hy4_engram.cpp:450-460`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347,375-384,483-494` — 値の保持、引数不足時の処理、`--engram` と `--no-engram` の parser 定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-564,703-705` — serve 用設定への転送、通常実行の Runner 初期化、失敗時の出力。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-49,314-317` — serve 側設定と初期化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676` — モデル metadata の読み込み、任意 shard の open、cache 行数。
- `engine/src/hy4flash/run/hy4_engram.cpp:446-503` — shard の読み込み・profile/配置の確認、seed と LRU の条件。
