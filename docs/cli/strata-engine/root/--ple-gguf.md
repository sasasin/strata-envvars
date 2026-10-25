# `--ple-gguf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（`src/program/generate.cpp` の `strata generate` 引数 parser） |
| オプション | `--ple-gguf` |
| 別名 | なし |
| 値 | PLE/n-gram tensor `per_layer_token_embd.weight` を含む GGUF ファイルのパス |

## 役割

PLE（Per-Layer Embedding）テーブルを含む GGUF shard を指定します。通常の pack 実行では PLE テーブルが pack に含まれないため、この指定がないと通常推論を開始できません。指定したファイルは起動時に開かれ、table の行は prompt や verify window の処理で参照されます（`src/program/generate.cpp:4023-4054`, `src/core/verify.cpp:2897-2918`）。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --ple-gguf /models/ple-shard.gguf
```

これはエンジン引数の例です。`--tokens` はこのエンジンで必要な token ID 入力です（`src/program/generate.cpp:806-812`, `src/program/generate.cpp:2416-2421`）。実際には利用モデルに対応する pack と PLE shard のパスに置き換えてください。

## 値と既定値

- parser は次の argv 要素をそのまま文字列として `ple_gguf` に格納します。パス形式や存在確認は parser 時点では行いません（`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2473`）。値を省略すると「`--ple-gguf needs a value`」を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。
- 既定値は空文字列です。通常の実行では `--no-ple` を指定しない限り PLE shard が必須で、未指定ならエラーを出して終了コード 2 になります（`src/program/generate.cpp:436-437`, `src/program/generate.cpp:3290-3300`）。
- `--native` 使用時は例外的に、明示指定がなく `--no-ple` でもない場合、モデル shard 群から `per_layer_token_embd.weight` を持つ shard を探して値を補います。見つからない場合や `--no-ple` を指定した場合は `--native requires --ple-gguf` エラーで終了コード 2 です（`src/program/generate.cpp:3247-3261`）。
- 指定値について、GGUF の読込、tensor の有無、shape、対応する tensor 型・必要な metadata、ファイル内の tensor 範囲を検査します。条件を満たさないと open に失敗します（`src/kernels/ngram.cpp:255-305`, `src/kernels/ngram.cpp:314-338`）。

## 実行時の動作

1. 通常実行では指定ファイルを `PleTable::open` に渡し、table の情報とデータを用意します（`src/program/generate.cpp:4033-4054`, `src/kernels/ngram.cpp:255-268`）。
2. `per_layer_token_embd.weight` が存在しない、shape が想定外、未対応の型、I8 table に必要な形式・正の scale metadata がない、または tensor の範囲・サイズが不整合の場合、エラー文字列を stderr に出して初期化を中断します。起動側は終了コード 1 を返します（`src/kernels/ngram.cpp:263-295`, `src/kernels/ngram.cpp:314-338`, `src/program/generate.cpp:4052-4055`）。
3. 初期化後は、PLE が ready で対象 stage が PLE を使う verify window に対し、入力 token から n-gram row index を作り、指定 table から row を gather します（`src/core/verify.cpp:2897-2918`, `src/core/verify.cpp:2990-2998`）。したがって、ファイル内容は単なる補助 metadata ではなく、推論時に参照する PLE tensor 本体です。
4. `--native` では PLE key の native 演算も有効化されます。指定したファイルが `general.architecture = strata-ple` の PLE 専用 GGUF でなければ、既定の native dense shard 群へ PLE ファイルも追加されます（`src/program/generate.cpp:3263-3281`）。

## 適用条件と副作用

- `--no-ple` と `--ple-gguf` は相互排他です。両方指定すると明示エラーで終了コード 2 になります。`--no-ple` は診断用 ablation として扱われ、通常実行の代替設定ではありません（`src/program/generate.cpp:3290-3300`, `src/program/generate.cpp:816-818`）。
- table の読み取り方法は別 option `--ple-io` が制御します。`--ple-gguf` 自体は I/O mode を選びません。`PleTable::open` は指定ファイルを開いて検証し、direct mode では table の data offset を得た後に mapping を閉じ、row reader にファイルを渡します（`src/program/generate.cpp:4033-4054`, `src/kernels/ngram.cpp:339-354`）。
- 指定した GGUF が複数 tensor を持つ場合、PLE tensor がそのファイルの範囲内に収まるかを検査します。tensor 単独ファイルの場合は data section 全体と tensor サイズが一致することも要求します（`src/kernels/ngram.cpp:306-338`）。
- PLE を有効にすると起動時に table を開き、実行中は PLE row の読み込みを行います。I/O の負荷、RAM 使用量、ストレージ上の配置に関する挙動は `--ple-io` やファイルシステム等に依存するため、この option 単独の性能効果は断定できません。

## 出力とエラー

- PLE table の open に失敗すると、エラー文字列を stderr に出し、初期化側は終了コード 1 を返します（`src/program/generate.cpp:4052-4055`）。
- PLE 構築完了後、table が ready なら stderr に行数と指定パスを含む `PLE on, table ... rows of ...` を出します。ready でなければエラーを出して終了コード 1 です（`src/program/generate.cpp:5237-5244`）。
- 値なし、未指定、`--no-ple` との併用は終了コード 2 の引数エラーです（`src/program/generate.cpp:2418-2420`, `src/program/generate.cpp:3290-3300`）。

## 根拠

- 索引上の scope は CMake 生成のネイティブ推論エンジン `strata-engine/root` です。索引は `--ple-gguf` をこの階層の予定文書として掲載しています（`docs/cli/README.md:1128-1134`, `docs/cli/README.md:1249-1254`）。
- parser と値なし処理: `src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2473`。
- 未指定時の必須条件と `--native` の補完・相互作用: `src/program/generate.cpp:3247-3281`, `src/program/generate.cpp:3290-3300`。
- GGUF の検証・読み込み: `src/kernels/ngram.cpp:255-305`, `src/kernels/ngram.cpp:314-354`。
- 実行時の row 準備・取得と起動時表示: `src/core/verify.cpp:2897-2918`, `src/core/verify.cpp:2990-2998`, `src/program/generate.cpp:5237-5244`。

## 調査範囲

この文書は上記 commit のソース parser・関連する `PleTable` 実装・verify 経路に基づきます。同一 revision の既存 CLI バイナリによる `--help` 表示や Release artifact は確認していません。OS/backend ごとのファイル I/O 実装や実機性能は調査・実行していません。
